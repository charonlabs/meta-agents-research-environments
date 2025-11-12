import os
from typing import Any

from langsmith.wrappers import wrap_openai
from litellm.exceptions import APIError, AuthenticationError
from openai import OpenAI
from openai.types.chat import ChatCompletion

from are.simulation.agents.llm.llm_engine import LLMEngine, LLMEngineException
from are.simulation.agents.llm.openai.openai_responses_engine import OpenAIModelConfig


class OpenAICompletionsEngine(LLMEngine):
    """
    A class that extends the LLMEngine to provide a specific implementation for the OpenAI Completions SDK.
    Attributes:
        model_config (OpenAIModelConfig): The configuration for the model.
    """

    def __init__(self, model_config: OpenAIModelConfig):
        super().__init__(model_config.model_name)
        api_key = model_config.api_key
        self.client = wrap_openai(OpenAI(api_key=api_key, base_url=model_config.endpoint))
        self.model_config = model_config

        self.mock_response = None
        if model_config.provider == "mock":
            self.mock_response = """Thought: Good choice, this is a mock, so I can't do anything. Let's return the result.
Action:
{
  "action": "_mock",
  "action_input": "Mock result"
}<end_action>
"""

    def chat_completion(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        messages: list[dict[str, Any]],
        stop_sequences=[],
        **kwargs,
    ) -> dict:
        try:
            tools = kwargs.get("tools", [])
            tool_choice = kwargs.get("tool_choice", "required")
            if len(tools) == 0:
                tool_choice = "auto"

            extra_body = {}
            if self.model_config.model_name.startswith("gpt-5"):
                extra_body["reasoning_effort"] = self.model_config.reasoning_effort
            elif self.model_config.model_name.startswith("openrouter/polaris"):
                extra_body["reasoning"] = {"effort": self.model_config.reasoning_effort}

            def stream_completions(history: list[dict]) -> tuple[str, str, list[dict]]:
                """
                Returns a tuple of the final response, reasoning, and tool calls.
                """
                stream = self.client.chat.completions.create(
                    model=self.model_config.model_name,
                    messages=history, # type: ignore
                    stream=True,
                    temperature=1.0,
                    max_tokens=1024 * 32,
                    tools=tools, # type: ignore
                    parallel_tool_calls=False,
                    tool_choice=tool_choice,
                    extra_body=extra_body,
                )
                final_response = ""
                reasoning = ""
                tool_calls = []
                started_reasoning = False
                for chunk in stream:
                    outchunk = ""
                    delta = chunk.choices[0].delta

                    rchunk = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
                    if rchunk:
                        if not started_reasoning:
                            print("\n\n**Reasoning**\n\n")
                            started_reasoning = True
                        reasoning += rchunk
                        outchunk = rchunk
                    else:
                        tcchunk = getattr(delta, "tool_calls", None)
                        if tcchunk:
                            if started_reasoning:
                                    started_reasoning = False
                            tool_calls += tcchunk
                            outchunk = ""
                        else:
                            cchunk = getattr(delta, "content", None)
                            if cchunk:
                                if started_reasoning:
                                    print("\n\n**Response**\n\n")
                                    started_reasoning = False
                                final_response += cchunk
                                outchunk = cchunk
                    print(outchunk, end="")
                
                return final_response, reasoning, tool_calls

            final_response, reasoning, tool_calls = stream_completions(messages)

            if self.model_config.model_name.startswith("kimi"):
                assistant_message = construct_assistant_message(final_response, reasoning, construct_tool_calls(tool_calls))
            else:   
                assistant_message = construct_assistant_message(final_response, construct_reasoning_details(reasoning), construct_tool_calls(tool_calls))

            return assistant_message
        except (AuthenticationError, APIError) as e:
            raise LLMEngineException("Auth error in openai.") from e
        except ValueError as e:
            raise LLMEngineException("No tools provided.") from e

def construct_tool_calls(tool_calls: list[Any]) -> list[dict]:
    parsed_tool_calls = []
    curr = {"function": {"arguments": ""}}
    id = ""
    for item in tool_calls:
        item_dict = item.model_dump()
        if item_dict["id"]:
            if id != "":
                parsed_tool_calls.append(curr)
                curr = {"function": { "arguments": ""}}
            id = item_dict["id"]
            curr["id"] = id
        if item_dict["function"]["name"]:
            curr["function"]["name"] = item_dict["function"]["name"]
        curr["function"]["arguments"] += item_dict["function"]["arguments"]
    parsed_tool_calls.append(curr)
    return parsed_tool_calls
def construct_reasoning_details(reasoning: str) -> list[dict]:
    return [{
        "type": "reasoning.text",
        "text": reasoning,
        "format": "unknown",
        "index": 0
    }]

def construct_assistant_message(final_response: str, reasoning_details: list[dict] | str, tool_calls: list[dict]) -> dict:
    if isinstance(reasoning_details, str):
        return {
        "content": final_response,
        "role": "assistant",
        "tool_calls": tool_calls,
        "reasoning_content": reasoning_details
    }
    return {
        "content": final_response,
        "role": "assistant",
        "tool_calls": tool_calls,
        "reasoning_details": reasoning_details
    }