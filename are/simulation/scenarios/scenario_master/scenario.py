from dataclasses import dataclass, field
from typing import Any
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.app import App
from are.simulation.scenarios.scenario import Scenario
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.scenarios.validation_result import ScenarioValidationResult
from are.simulation.tool_utils import OperationType, app_tool, data_tool
from are.simulation.types import AbstractEnvironment, EventRegisterer, event_registered
from are.simulation.utils import get_state_dict, type_check

@dataclass
class KVStoreApp(App):
    """
    A simple key-value store app.
    """
    name: str | None = "KVStore"
    store: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        super().__init__(self.name)

    def get_state(self) -> dict[str, Any]:
        return get_state_dict(self, ["store"])

    def load_state(self, state_dict: dict[str, Any]):
        self.store = state_dict.get("store", {})

    def reset(self):
        super().reset()
        self.store = {}

    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.WRITE)
    def set(self, key: str, value: str) -> None:
        """
        Set a value at a given key.
        :param key: The key to set the value at.
        :param value: The value to set.
        :returns: None.
        """
        self.store[key] = value

    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.READ)
    def get(self, key: str) -> str:
        """
        Get a value at a given key.
        :param key: The key to get the value from.
        :returns: The value at the given key.
        """
        if key not in self.store:
            raise KeyError(f"Key {key} not found in store")
        return self.store.get(key, "")

    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.WRITE)
    def delete(self, key: str) -> None:
        """
        Delete a value at a given key.
        :param key: The key to delete the value from.
        :returns: None.
        """
        if key not in self.store:
            raise KeyError(f"Key {key} not found in store")
        del self.store[key]

    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.READ)
    def get_all(self) -> dict[str, str]:
        """
        Get all values in the store.
        :returns: A dictionary of all values in the store.
        """
        return self.store

@register_scenario("scenario_kv_demo")
class ScenarioKVDemo(Scenario):

    start_time: float | None = 0
    duration: float | None = 300

    def init_and_populate_apps(self, *args, **kwargs) -> None:
        kv_app = KVStoreApp()

        aui = AgentUserInterface()

        kv_app.set("name", "John Doe")
        kv_app.set("age", "20")
        kv_app.set("city", "New York")

        self.apps = [kv_app, aui]

    def build_events_flow(self) -> None:
        kv_app = self.get_typed_app(KVStoreApp, "KVStore")
        aui = self.get_typed_app(AgentUserInterface)
        with EventRegisterer.capture_mode():
            event1 = aui.send_message_to_agent(
                content="Change the user's name to 'Jane Doe', and then verify it. Respond with a report of the previous name and what it was changed to."
            ).depends_on(None, delay_seconds=1)
            oracle1 = kv_app.get_all().oracle().depends_on(event1, delay_seconds=1)
            oracle2 = kv_app.set("name", "Jane Doe").oracle().depends_on(oracle1, delay_seconds=1)
            oracle3 = kv_app.get("name").oracle().depends_on(oracle2, delay_seconds=1)

        self.events = [event1, oracle1, oracle2, oracle3]

    def validate(self, env: AbstractEnvironment) -> ScenarioValidationResult:
        try:
            kv_app = env.get_app("KVStore")

            name = kv_app.get("name")
            if name != "Jane Doe":
                return ScenarioValidationResult(success=False, exception=Exception("Name not changed"))
            return ScenarioValidationResult(success=True)
        except Exception as e:
            return ScenarioValidationResult(success=False, exception=e)

if __name__ == "__main__":
    from are.simulation.scenarios.utils.cli_utils import run_and_validate

    run_and_validate(ScenarioKVDemo())