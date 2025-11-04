# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.


import json
import pprint
from dataclasses import dataclass
from typing import Any, Callable

from openai.types.responses import Response

from are.simulation.agents.agent_log import (
    BaseAgentLog,
    ObservationLog,
    RationaleLog,
    ToolCallLog,
)
from are.simulation.agents.llm.types import MMObservation
from are.simulation.agents.multimodal import Attachment
from are.simulation.exceptions import (
    JsonExecutionAgentError,
    JsonParsingAgentError,
    LoggedError,
    UnavailableToolAgentError,
)
from are.simulation.tool_box import get_tool_description_with_args
from are.simulation.tools import Tool

from .action_executor import AgentAction, BaseActionExecutor, ParsedAction


@dataclass
class ResponsesAction:
    raw_tool_call: dict[str, Any]
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    raw_reasoning: list[dict[str, Any]]
    rationale: str

def _parse_responses_output(output: list[dict[str, Any]] | None) -> ResponsesAction:
    if output is None:
        raise JsonParsingAgentError("Could not parse the responses output due to missing output.")
    raw_reasoning = []
    rationale = ""
    tool_name = ""
    call_id = ""
    arguments = {}
    raw_tool_call = {}
    for block in output:
        match block["type"]:
            case "reasoning":
                block.pop("status")
                raw_reasoning.append(block)
                for item in block["summary"]:
                    rationale += item["text"] + "\n\n"
            case "function_call":
                raw_tool_call = block
                tool_name = block["name"]
                call_id = block["call_id"]
                try:
                    arguments = json.loads(block["arguments"])
                except json.JSONDecodeError as e:
                    raise JsonParsingAgentError(f"Could not parse the arguments due to invalid JSON: {e}")
                except Exception as e:
                    raise JsonParsingAgentError(f"Could not parse the arguments due to unexpected error: {e}")
                arguments = block["arguments"]
            case _:
                raise JsonParsingAgentError(f"Unknown block type: {block['type']}")
    if rationale == "":
        rationale = "No thoughts needed."
    return ResponsesAction(
        raw_tool_call=raw_tool_call,
        tool_name=tool_name,
        call_id=call_id,
        arguments=arguments,
        raw_reasoning=raw_reasoning,
        rationale=rationale,
    )


def get_observation_log(
    timestamp: float,
    content: str,
    agent_id: str,
    call_id: str,
    attachments: list[Attachment] | None = None,
) -> ObservationLog:
    if not content and not attachments:
        return ObservationLog(
            content="No observation", timestamp=timestamp, agent_id=agent_id
        )
    return ObservationLog(
        content=content.strip(),
        attachments=attachments or [],
        timestamp=timestamp,
        agent_id=agent_id,
        call_id=call_id,
    )


class ResponsesActionExecutor(BaseActionExecutor):
    def __init__(
        self, tools: dict[str, Tool] | None = None, use_custom_logger: bool = True
    ):
        super().__init__(use_custom_logger=use_custom_logger)
        self.tools = tools if tools is not None else {}
        self.tool_parser = _parse_responses_output
        self.action_token = "Action:"
        self.thought_token = "Thought:"


    def extract_action(self, llm_output: Response) -> AgentAction:  # pyright: ignore[reportIncompatibleMethodOverride]
        output = [item.model_dump() for item in llm_output.output]
        return AgentAction(
            rationale="",
            action=None,
            action_type=None,
            responses_output=output
        )

    def execute_action(
        self,
        action: AgentAction,
        append_agent_log: Callable[[BaseAgentLog], None],
        make_timestamp: Callable[[], float],
        agent_id: str,
    ):
        parsed_action = self.parse_action(action)
        return self.execute_parsed_action(
            parsed_action, append_agent_log, make_timestamp, agent_id
        )

    def parse_action(self, action: AgentAction) -> ParsedAction:
        arguments = {}
        try:
            responses_action = self.tool_parser(action.responses_output)
            tool_name = responses_action.tool_name
            app_name, action_name = (
                tool_name.split("__")
                if "__" in tool_name
                else (
                    tool_name,
                    None,
                )
            )
            if isinstance(responses_action.arguments, str):
                arguments = json.loads(responses_action.arguments)
        except Exception as e:
            raise JsonParsingAgentError(
                f"Could not parse the given action: {e} - return was {pprint.pformat(action.responses_output)}"
            )
        return ParsedAction(
            tool_name=tool_name,
            app_name=app_name,
            arguments=arguments,
            rationale=responses_action.rationale,
            action_name=action_name,
            call_id=responses_action.call_id,
            raw_reasoning=responses_action.raw_reasoning,
            raw_tool_call=responses_action.raw_tool_call,
        )

    def execute_parsed_action(
        self,
        parsed_action: ParsedAction,
        append_agent_log: Callable[[BaseAgentLog], None],
        make_timestamp: Callable[[], float],
        agent_id: str,
    ) -> None:
        tool_name = parsed_action.tool_name
        arguments = parsed_action.arguments if parsed_action.arguments else {}
        rationale = parsed_action.rationale
        call_id = parsed_action.call_id or ""
        raw_reasoning = parsed_action.raw_reasoning
        raw_tool_call = parsed_action.raw_tool_call
        if not tool_name:
            raise JsonParsingAgentError(
                "Error: error parsing the tool_name in the action."
            )

        # 1. Log the rationale, action, tool name, and arguments in logs
        if rationale is not None:
            append_agent_log(
                RationaleLog(
                    content=rationale,
                    timestamp=make_timestamp(),
                    agent_id=agent_id,
                    raw_reasoning=raw_reasoning,
                )
            )

        append_agent_log(
            ToolCallLog(
                tool_name=tool_name,
                tool_arguments=arguments,
                timestamp=make_timestamp(),
                agent_id=agent_id,
                call_id=call_id,
                raw_tool_call=raw_tool_call,
            )
        )

        # 2. Execute the tool
        self.logger.debug(f"Calling tool: '{tool_name}' with arguments: {arguments}")
        observation = self.execute_tool_call(
            parsed_action, append_agent_log, make_timestamp
        )

        # 3. Log the observation in logs
        if isinstance(observation, MMObservation):
            append_agent_log(
                get_observation_log(
                    make_timestamp(),
                    observation.content,
                    agent_id,
                    call_id,
                    observation.attachments,
                )
            )
        else:
            append_agent_log(
                get_observation_log(make_timestamp(), str(observation), agent_id, call_id)
            )

        # 4. Log the final answer in logs
        if tool_name == "final_answer":
            self._append_final_answer(
                observation, append_agent_log, make_timestamp, agent_id
            )

    def execute_tool_call(
        self,
        parsed_action: ParsedAction,
        append_agent_log: Callable[[BaseAgentLog], None],
        make_timestamp: Callable[[], float],
    ) -> Any:
        tool_name = parsed_action.tool_name
        arguments = parsed_action.arguments if parsed_action.arguments else {}
        

        if tool_name == "_mock":
            return "Mocked observation"

        if tool_name not in self.tools:
            error_msg = f"Error: unknown tool {tool_name}, should be instead one of {list(self.tools.keys())}."
            self.logger.error(error_msg, exc_info=True)
            raise UnavailableToolAgentError(error_msg)

        try:
            if isinstance(arguments, str):
                observation = self.tools[tool_name](arguments)
            else:
                observation = self.tools[tool_name](**arguments)
            return observation
        except LoggedError as e:
            self.logger.error(e, exc_info=True)
            raise e
        except Exception as e:
            raise JsonExecutionAgentError(
                f"Error in tool call execution: {e}\nYou should only use this tool with a correct input.\n"
                f"As a reminder, this tool's description is the following:\n{get_tool_description_with_args(self.tools[tool_name])}"
            )

    def update_tools(self, tools: dict[str, Tool]):
        self.tools = tools
