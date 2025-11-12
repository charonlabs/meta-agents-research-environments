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
class CompletionsAction:
    raw_tool_call: dict[str, Any]
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    rationale: str
    skipped_ids: list[str]

def _parse_completions_output(output: dict| None) -> CompletionsAction:
    if output is None:
        raise JsonParsingAgentError("Could not parse the completions output due to missing output.")
    tc = output["tool_calls"][0]
    if "reasoning_details" in output:
        rationale = output["reasoning_details"][0]["text"]
    else:
        rationale = output["reasoning_content"]
    tool_name = tc["function"]["name"]
    call_id = tc["id"]
    raw_tool_call = output
    if len(output["tool_calls"]) > 1:
        skipped_ids = [tc["id"] for tc in output["tool_calls"][1:]]
    else:
        skipped_ids = []
    
    try:
        arguments = json.loads(tc["function"]["arguments"])
    except json.JSONDecodeError as e:
        raise JsonParsingAgentError(f"Could not parse the arguments due to invalid JSON: {e}")
    except Exception as e:
        raise JsonParsingAgentError(f"Could not parse the arguments due to unexpected error: {e}")

    return CompletionsAction(
        raw_tool_call=raw_tool_call,
        tool_name=tool_name,
        call_id=call_id,
        arguments=arguments,
        rationale=rationale,
        skipped_ids=skipped_ids,
    )


def get_observation_log(
    timestamp: float,
    content: str,
    agent_id: str,
    call_id: str,
    attachments: list[Attachment] | None = None,
    skipped_ids: list[str] = [],
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
        skipped_ids=skipped_ids,
    )


class CompletionsActionExecutor(BaseActionExecutor):
    def __init__(
        self, tools: dict[str, Tool] | None = None, use_custom_logger: bool = True
    ):
        super().__init__(use_custom_logger=use_custom_logger)
        self.tools = tools if tools is not None else {}
        self.tool_parser = _parse_completions_output
        self.action_token = "Action:"
        self.thought_token = "Thought:"


    def extract_action(self, llm_output: dict) -> AgentAction:  # pyright: ignore[reportIncompatibleMethodOverride]
        return AgentAction(
            rationale="",
            action=None,
            action_type=None,
            responses_output=[llm_output]
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
        assert action.responses_output is not None
        completions_output = action.responses_output[0]
        completions_action = self.tool_parser(completions_output)
        tool_name = completions_action.tool_name
        app_name, action_name = (
            tool_name.split("__")
            if "__" in tool_name
            else (
                tool_name,
                None,
            )
        )
        return ParsedAction(
            tool_name=tool_name,
            app_name=app_name,
            arguments=completions_action.arguments,
            rationale=completions_action.rationale,
            action_name=action_name,
            call_id=completions_action.call_id,
            raw_tool_call=completions_action.raw_tool_call,
            skipped_ids=completions_action.skipped_ids,
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
                    parsed_action.skipped_ids,
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
