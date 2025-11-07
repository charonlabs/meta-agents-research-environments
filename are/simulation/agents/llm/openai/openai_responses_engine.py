import logging
import os
from typing import Any

from langsmith.wrappers import wrap_openai
from litellm.exceptions import APIError, AuthenticationError
from openai import OpenAI
from openai.types.responses import Response, ResponseIncludable
from pydantic import BaseModel

from are.simulation.agents.llm.llm_engine import LLMEngine, LLMEngineException

logger = logging.getLogger(__name__)

class OpenAIModelConfig(BaseModel):
    model_name: str = "gpt-5-mini"
    provider: str | None = "local"
    endpoint: str | None = "https://api.openai.com/v1"
    api_key: str | None = None
    reasoning_effort: str | None = "medium"


class OpenAIResponsesEngine(LLMEngine):
    """
    A class that extends the LLMEngine to provide a specific implementation for the Litellm model.
    Attributes:
        model_config (ModelConfig): The configuration for the model.
    """

    def __init__(self, model_config: OpenAIModelConfig):
        super().__init__(model_config.model_name)
        api_key = os.getenv("OPENAI_API_KEY") or model_config.api_key
        if api_key is None:
            raise EnvironmentError("OPENAI_API_KEY must be set in the environment")
        self.client = wrap_openai(OpenAI(api_key=api_key))
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
    ) -> Response:
        try:
            tools = kwargs.get("tools", [])
            tool_choice = kwargs.get("tool_choice", "required")
            if len(tools) == 0:
                tool_choice = "auto"

            previous_response_id = kwargs.get("previous_response_id", None)
            include: list[ResponseIncludable] = ["reasoning.encrypted_content"] if (previous_response_id is None and not self.model_config.model_name.startswith("gpt-4")) else []
            reasoning = {"summary": "detailed", "effort": self.model_config.reasoning_effort} if not self.model_config.model_name.startswith("gpt-4") else None

            response = self.client.responses.create(
                model=self.model_config.model_name,
                input=messages, # type: ignore
                tools=tools,
                tool_choice=tool_choice,
                include=include,
                parallel_tool_calls=False,
                reasoning=reasoning, # type: ignore
                previous_response_id=previous_response_id,
            )

            return response
        except (AuthenticationError, APIError) as e:
            raise LLMEngineException("Auth error in openai.") from e
        except ValueError as e:
            raise LLMEngineException("No tools provided.") from e