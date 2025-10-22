from collections import defaultdict
import json
import random
from typing import Any
import time
import uuid

from openai.types.responses import Response
from openai.resources.responses.responses import _make_tools as make_responses_tools
from are.simulation.agents.agent_log import ErrorLog, LLMInputLog, LLMOutputThoughtActionLog, ObservationLog, SystemPromptLog, TaskLog, ThoughtLog, ToolCallLog, RationaleLog
from are.simulation.agents.default_agent.base_agent import BaseAgent, convert_plan_fact_messages_to_user, get_offset_from_time_config_mode
from are.simulation.agents.llm.openai.openai_responses_engine import OpenAIResponsesEngine, OpenAIModelConfig
from are.simulation.agents.default_agent.tools.responses_action_executor import ResponsesActionExecutor

from datetime import datetime, timezone

from are.simulation.exceptions import InvalidActionAgentError

def format_message(
    message_dict: dict[str, Any],
    message_type: str,
    content: str,
    i: int | None = None,
    timestamp: float | None = None,
) -> str:
    template = message_dict.get(message_type)
    if template is None:
        raise ValueError(f"Unknown message type: {message_type}")

    if message_type in ["facts", "plan"]:
        content = convert_plan_fact_messages_to_user(content)

    format_args = {"content": content}
    if "{i}" in template:
        if i is None:
            raise ValueError(f"Message type '{message_type}' requires 'i' parameter")
        format_args["i"] = str(i)

    if "{timestamp}" in template:
        if timestamp is None:
            raise ValueError(
                f"Message type '{message_type}' requires 'timestamp' parameter"
            )
        format_args["timestamp"] = datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")

    return template.format(**format_args)

class ResponsesBaseAgent(BaseAgent):

    def __init__(self, **kwargs: Any):
        if "llm_engine" not in kwargs:
            kwargs["llm_engine"] = OpenAIResponsesEngine(OpenAIModelConfig(
                model_name="gpt-5-mini",
            ))
        assert isinstance(kwargs["llm_engine"], OpenAIResponsesEngine), "llm_engine must be an instance of OpenAIResponsesEngine"
        if "action_executor" not in kwargs:
            kwargs["action_executor"] = ResponsesActionExecutor()
        assert isinstance(kwargs["action_executor"], ResponsesActionExecutor), "action_executor must be an instance of ResponsesActionExecutor"
        self.oai_tools: list[dict[str, Any]] = []
        self.previous_response_id: str | None = None
        self.use_api_state = kwargs.get("use_api_state", False)
        super().__init__(**kwargs)

    def init_tools(self):
        tool_values = [tool for tool in self.tools.values()]

        if self.shuffle_tools:
            self.logger.debug(f"Shuffling tools with seed {self.shuffle_seed}")
            shuffle_tools_rng = random.Random(self.shuffle_seed)
            shuffle_tools_rng.shuffle(tool_values)

        self.oai_tools = [t.app_tool.to_open_ai_responses() for t in tool_values]  # pyright: ignore[reportAttributeAccessIssue]
        self.action_executor.update_tools(self.tools)
        return tool_values

    def build_history_from_logs(
        self, exclude_log_types: list[str] = [], until_last_assistant: bool = False
    ) -> list[dict[str, Any]]:
        """
        Build the history of messages from the logs, ensuring a specific order of steps.
        :param exclude_log_types: List of log types to exclude from the history.
        :return: List[Dict[str, str]] - List of messages.
        """
        history = []
        id_output_step = 0
        last_assistant_log_id = 0

        if until_last_assistant:
            for i, log in enumerate(reversed(self.logs)):
                if log.get_type() == "tool_call":
                    last_assistant_log_id = len(self.logs) - i - 1
                    break

        for i, log in enumerate(self.logs):
            role = log.get_type()
            timestamp = log.timestamp
            if role in ["observation", "error"]:
                id_output_step += 1

            if role in exclude_log_types or i < last_assistant_log_id:
                continue

            if isinstance(log, ErrorLog) and log.error == "MaxIterationsAgentError":
                continue

            if (
                isinstance(log, ErrorLog)
                and log.error == "PromptTooLongException"
                and self.handle_prompt_too_long
            ):
                attachments_for_llm = None
                prev_observation_log = None
                for prev_log in self.logs[i::-1]:
                    if isinstance(prev_log, ObservationLog):
                        prev_observation_log = prev_log
                        break
                if prev_observation_log is not None:
                    content = repr(prev_observation_log.content)
                    trunc_content = content[:100] + "\n[...]\n" + content[-100:]
                    self.logger.debug(
                        f"Prompt too long: Removing the observation from the previous step because it possibly flooded the context. Here is the truncated observation (first 100 + [...] + last 100 chars):\n{trunc_content}"
                    )
                    exception = (
                        log.exception
                        + f"\nObservation was removed because it possibly flooded the context. Truncated observation (first 100 + [...] + last 100 chars):\n{trunc_content}"
                    )
                    history.pop()
                    content_for_llm = f"Error: {log.error}\nException: {exception}\nCategory: {log.category}"  # so that we don't modify the log each time we call build_history_from_logs
                else:
                    content_for_llm = log.get_content_for_llm()
            elif isinstance(log, TaskLog):
                content_for_llm = log.get_content_for_llm_no_attachment()
                if not content_for_llm:
                    # If there is no content, we don't want to include the task in the history
                    continue
                attachments_for_llm = log.get_attachments_for_llm()
            elif isinstance(log, ObservationLog):
                # Include attachments only if this log is in our selected attachment_logs
                content_for_llm = log.get_content_for_llm_no_attachment()
                attachments_for_llm = log.get_attachments_for_llm()
                content = format_message(
                    message_dict=self.message_dict,
                    message_type=role,
                    content=content_for_llm or "",
                    i=id_output_step,
                    timestamp=timestamp,
                )
                formatted_attachments = [
                    a.to_openai_json() for a in attachments_for_llm
                ]
                obs = {
                   "type": "function_call_output",
                   "call_id": log.call_id,
                   "output": [
                    {
                        "type": "input_text",
                        "text": content    
                    },
                    *formatted_attachments,
                   ]
                }
                history.append(obs)
                continue
            elif isinstance(log, ToolCallLog):
                history.append(log.raw_tool_call)
                continue
            elif isinstance(log, RationaleLog):
                assert log.raw_reasoning is not None
                history.extend(log.raw_reasoning)
                continue
            elif isinstance(log, LLMOutputThoughtActionLog):
                content_for_llm = None
                attachments_for_llm = None
            elif isinstance(log, SystemPromptLog):
                history.append({"role": "developer", "content": log.content})
                continue
            else:
                content_for_llm = log.get_content_for_llm()
                attachments_for_llm = None

            if (
                role not in self.role_dict
                or role in exclude_log_types
                or (
                    (content_for_llm is None or content_for_llm == "")
                    and attachments_for_llm is None
                )
            ):
                continue
            
            formatted_attachments = []
            if attachments_for_llm is not None:
                formatted_attachments = [
                    a.to_openai_json() for a in attachments_for_llm
                ]

            content = format_message(
                message_dict=self.message_dict,
                message_type=role,
                content=content_for_llm or "",
                i=id_output_step,
                timestamp=timestamp,
            )
            
            history.append({
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": content,
                    },
                    *formatted_attachments,
                ]
            })
        return history

    def step(self):
        """
        Perform one step in the ReAct framework: the agent thinks, acts, and observes the result.
        The errors are raised here, they are caught and logged in the run() method.
        """
        # 1. Build the history messages from the logs to prompt the LLM
        if not self.use_api_state:
            agent_memory = self.build_history_from_logs(
                exclude_log_types=["thought", "action"]
            )
        else:
            agent_memory = self.build_history_from_logs(
                exclude_log_types=["thought", "action", "rationale"], until_last_assistant=True
            )
        prompt = agent_memory.copy()

        self.append_agent_log(
            LLMInputLog(
                content=prompt, timestamp=self.make_timestamp(), agent_id=self.agent_id
            )
        )

        # 2. Call the model to generate the next rationale and action
        # We don't put empty string as a default value, because it can cause an infinite loop if Metagen returns an empty string
        # For example when the input prompt is too long
        if self.simulated_generation_time_config is not None:
            # We pause the environment for the generation of a thought/action
            if self.pause_env is None:
                raise ValueError("pause_env is not set")
            self.pause_env()

        format_try_count: int = 0
        llm_output = None
        metadata = {}
        llm_response: Response | None = None

        start_time = time.perf_counter()

        if (("content" in prompt[-1] and "ERROR" in prompt[-1]["content"] and "candidates" in prompt[-1]["content"])
        or ("output" in prompt[-1] and "error" in prompt[-1]["output"][0]["text"] and "candidates" in prompt[-1]["output"][0]["text"])):
            self.logger.warning("Server error. Retrying...")
            llm_output = "ERROR - please try again."
        else:
            while llm_output is None or (
                self.retry_llm_call_on_error
            ):
                if llm_output is not None:
                    self.logger.warning(
                        f"LLM did not return a valid output: {llm_output}.\nRetrying..."
                    )
                    self.log_error(
                        InvalidActionAgentError(
                            f"The LLM output was not formatted correctly: {llm_output}"
                        )
                    )
                llm_response = self.llm_engine(
                    prompt,
                    stop_sequences=["<end_action>", "Observation:"],
                    additional_trace_tags=["action"],
                    schema=self.decoding_schema,
                    tools=self.oai_tools,
                    previous_response_id=self.previous_response_id,
                )
                assert isinstance(llm_response, Response), "llm_response must be an instance of Response"
                if self.use_api_state:
                    self.previous_response_id = llm_response.id
                llm_output = "\n".join([str(item.model_dump()) for item in llm_response.output if not item.type == "reasoning"])
                metadata = llm_response.usage.model_dump() if llm_response.usage is not None else {}
                format_try_count += 1
                if llm_output:
                    break
                # This is a failsafe from infinite loop issues that can happen when the input prompt is too long
                if format_try_count > self.invalid_format_retries:
                    break

        end_time = time.perf_counter()
        completion_duration = end_time - start_time

        # Resume the environment after the generation of a thought/action if needed
        if self.simulated_generation_time_config is not None:
            if self.resume_env is None:
                raise ValueError("resume_env is not set")

            offset = get_offset_from_time_config_mode(
                time_config=self.simulated_generation_time_config,
                completion_duration=completion_duration,
            )
            self.logger.debug(f"Resuming environment with {offset} offset")
            self.resume_env(offset)

        

        if format_try_count > self.invalid_format_retries:
            raise InvalidActionAgentError(
                f"LLM did not return a valid output after {format_try_count} iterations: {llm_output}"
            )

        if llm_output is None:
            raise InvalidActionAgentError(
                f"The LLM output was not formatted correctly: {llm_output} - did not contain {self.action_token} or {self.thought_token}"
            )
        assert llm_response is not None

        # 3. Extract the rationale and the action from the LLM output
        try:
            agent_action = self.action_executor.extract_action(  # pyright: ignore[reportCallIssue]
                llm_output=llm_response
            )
        except Exception as e:
            self.logger.error(f"Error while extracting action: {e}")
            self.logger.debug(f"LLM output: {llm_output}")
            raise e

        parsed_action = self.action_executor.parse_action(agent_action)

        llm_output_pretty = f"Thought: {parsed_action.rationale or ""}\nAction:\n" + "{\n  \"action\": \"" + (parsed_action.tool_name or "") + "\",\n  \"action_input\": " + json.dumps(parsed_action.arguments or {}) + "\n}"
        
        self.logger.debug("===== Output response of the LLM: =====")
        self.logger.debug(llm_output_pretty)

        # DO NOT REMOVE THIS LINE, IT BREAKS REACT LOOP
        self.append_agent_log(
            LLMOutputThoughtActionLog(
                content=llm_output_pretty,
                timestamp=self.make_timestamp(),
                agent_id=self.agent_id,
                prompt_tokens=metadata.get("input_tokens", 0),
                completion_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                reasoning_tokens=metadata["output_tokens_details"].get("reasoning_tokens", 0),
                completion_duration=completion_duration,
            )
        )

        self.append_agent_log(
            ThoughtLog(
                content=parsed_action.rationale or "",
                timestamp=self.make_timestamp(),
                agent_id=self.agent_id,
            )
        )
            
        self.action_executor.execute_parsed_action(
            parsed_action,
            self.append_agent_log,
            self.make_timestamp,
            self.agent_id,
        )

RESPONSES_SYSTEM_PROMPT = """
You are MetaOSSAgent operating within the Meta Agents Research Environments. Work silently to solve the user's task using the tools provided.

Execution protocol:
1. Think through the task step by step in natural language.
2. When you need to act, invoke exactly one tool call using the platform's structured tool calling interface. Do not return JSON blobs manually.
3. Pay close attention to each tool description and only supply the arguments it expects.
4. Conclude by calling the `AgentUserInterface__send_message_to_user` tool when the task is complete or when you must report failure.

Environment rules:
- Communicate with the user only when you are done or require clarification.
- Use the available tools to gather missing information before asking the user.
- Finish all unambiguous parts of the request before asking for clarification.
- Follow the scenario instructions and respect the dynamic state of the environment.
""".strip()