"""
Commitment Tracking Scenario

This scenario evaluates an AI assistant's ability to track, update, and manage
commitments across an 8-turn conversation scenario.

The scenario tests:
1. Creating reminders from explicit user requests
2. Creating calendar events with attendees and times
3. Handling implicit/optional commitments
4. Updating commitments based on email notifications
5. Rescheduling calendar events
6. Cancelling events
7. Providing accurate summaries of active commitments

The agent must process user messages and incoming emails, then take appropriate
actions to track commitments in the calendar and reminder systems.
"""

from are.simulation.agents.user_proxy import UserProxyResponses
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.calendar import CalendarApp
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.scenarios.commitments.data import COMMITMENT_FLOW
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import Action, EventRegisterer, EventType


@register_scenario("commitment_tracking")
class CommitmentTrackingScenario(Scenario):
    """
    A scenario that tests an AI agent's ability to track and manage commitments.

    The agent receives 8 turns of interaction including:
    - User messages with commitment requests
    - Incoming emails with schedule changes
    - Requests to reschedule or cancel events
    - Summary requests

    Success requires:
    - Creating reminders and calendar events from natural language
    - Updating commitments based on new information
    - Cancelling events when requested
    - Providing accurate summaries excluding cancelled items
    """

    # Scenario runs for 60 seconds (enough time for 9 turns at 3s intervals + agent processing)
    start_time: float | None = 0
    duration: float | None = 60

    print("Initializing Commitment Tracking Scenario...")

    def init_and_populate_apps(self, *args, **kwargs) -> None:
        """
        Initialize the applications needed for commitment tracking.

        Sets up:
        - AgentUserInterface for user communication
        - EmailClientApp for receiving emails
        - CalendarApp for managing events and reminders
        """
        # Initialize apps
        agui = AgentUserInterface()
        email_app = EmailClientApp()
        calendar_app = CalendarApp()

        # Store apps
        self.apps = [agui, email_app, calendar_app]

    def build_events_flow(self) -> None:
        """
        Build the sequence of events based on the commitment flow.

        Creates events for each turn in the COMMITMENT_FLOW, including:
        - User messages asking to track commitments
        - Incoming emails with schedule changes
        - Oracle events showing expected agent actions

        Events are scheduled at absolute times (relative to scenario start)
        to ensure all turns are delivered regardless of agent processing time.
        """
        # Get typed references to apps
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)

        # Use capture_mode to register events from app method calls
        with EventRegisterer.capture_mode():
            events = []
            cumulative_time = 0

            for turn_data in COMMITMENT_FLOW:
                turn_num = turn_data["turn"]
                delay = turn_data.get("delay", 10)

                # Accumulate time for absolute scheduling
                cumulative_time += delay

                # Handle user messages
                if "user_message" in turn_data:
                    event = agui.send_message_to_agent(
                        content=turn_data["user_message"]
                    )
                    # Schedule at absolute time (relative to scenario start)
                    # This ensures all turns are delivered regardless of agent state
                    event.event_relative_time = cumulative_time
                    events.append(event)

                # Handle incoming emails
                if "email" in turn_data:
                    email_data = turn_data["email"]
                    event = email_app.send_email_to_user(
                        email=Email(
                            sender=email_data["sender"],
                            recipients=[email_app.user_email],
                            subject=email_data["subject"],
                            content=email_data["content"],
                            email_id=f"email_turn_{turn_num}",
                        )
                    )
                    # Schedule at absolute time (relative to scenario start)
                    event.event_relative_time = cumulative_time
                    events.append(event)

            # Assign collected events to the scenario
            self.events = events

    def validate(self, env) -> ScenarioValidationResult:
        """
        Validate that the agent successfully managed commitments.

        Uses data-driven validation based on expected_actions in COMMITMENT_FLOW.

        Returns a percentage score (0-100) based on how many expected actions were completed.

        Args:
            env: The environment containing apps and event logs

        Returns:
            ScenarioValidationResult with success as a percentage (0-100)
        """
        try:
            # Get apps
            calendar_app = env.get_app("CalendarApp")
            agui = env.get_app("AgentUserInterface")

            # Get agent messages for summary validation
            agent_messages = [
                event for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.class_name == "AgentUserInterface"
                and event.action.function_name == "send_message_to_user"
            ]

            checks_passed = 0
            total_checks = 0
            issues = []

            # Validate each turn's expected actions
            for turn_data in COMMITMENT_FLOW:
                turn_num = turn_data["turn"]
                expected_actions = turn_data.get("expected_actions", {})

                if not expected_actions:
                    continue

                # Check for reminder creation
                if "reminder" in expected_actions:
                    total_checks += 1
                    reminder_spec = expected_actions["reminder"]
                    keywords = reminder_spec.get("description_keywords", [])
                    is_optional = reminder_spec.get("optional", False)

                    # Check if a reminder with these keywords exists
                    matching_reminders = [
                        event for event in calendar_app.events.values()
                        if all(kw.lower() in event.title.lower() for kw in keywords)
                    ]

                    if matching_reminders:
                        checks_passed += 1
                    elif not is_optional:
                        issues.append(
                            f"Turn {turn_num}: Missing reminder with keywords {keywords}"
                        )

                # Check for calendar event creation
                if "calendar" in expected_actions:
                    total_checks += 1
                    cal_spec = expected_actions["calendar"]
                    title_keywords = cal_spec["title"].lower().split()

                    matching_events = [
                        event for event in calendar_app.events.values()
                        if all(kw.lower() in event.title.lower() for kw in title_keywords)
                    ]

                    if matching_events:
                        checks_passed += 1
                    else:
                        issues.append(
                            f"Turn {turn_num}: Missing calendar event '{cal_spec['title']}'"
                        )

                # Check for reminder update
                if "reminder_update" in expected_actions:
                    total_checks += 1
                    update_spec = expected_actions["reminder_update"]
                    original_keywords = update_spec["original_title"].lower().split()

                    # Check if the reminder exists and might have been updated
                    # (We check final state, not the update action itself)
                    matching_reminders = [
                        event for event in calendar_app.events.values()
                        if all(kw.lower() in event.title.lower() for kw in original_keywords)
                    ]

                    if matching_reminders:
                        checks_passed += 1
                    else:
                        issues.append(
                            f"Turn {turn_num}: Reminder '{update_spec['original_title']}' not updated"
                        )

                # Check for calendar event update
                if "calendar_update" in expected_actions:
                    total_checks += 1
                    update_spec = expected_actions["calendar_update"]
                    title_keywords = update_spec["original_title"].lower().split()

                    matching_events = [
                        event for event in calendar_app.events.values()
                        if all(kw.lower() in event.title.lower() for kw in title_keywords)
                    ]

                    if matching_events:
                        checks_passed += 1
                    else:
                        issues.append(
                            f"Turn {turn_num}: Calendar event '{update_spec['original_title']}' not rescheduled"
                        )

                # Check for calendar event cancellation
                if "calendar_cancel" in expected_actions:
                    total_checks += 1
                    cancel_spec = expected_actions["calendar_cancel"]
                    title_keywords = cancel_spec["title"].lower().split()

                    # Cancelled events should NOT exist in the calendar
                    matching_events = [
                        event for event in calendar_app.events.values()
                        if all(kw.lower() in event.title.lower() for kw in title_keywords)
                    ]

                    if not matching_events:
                        checks_passed += 1
                    else:
                        issues.append(
                            f"Turn {turn_num}: Event '{cancel_spec['title']}' was not cancelled"
                        )

                # Check for summary
                if "summary" in expected_actions:
                    total_checks += 1
                    summary_spec = expected_actions["summary"]
                    should_include = summary_spec.get("should_include", [])
                    should_not_include = summary_spec.get("should_not_include", [])

                    if agent_messages:
                        last_messages = agent_messages[-3:]
                        message_content = " ".join(
                            [
                                msg.action.args.get("content", "").lower()  # type: ignore[union-attr]
                                for msg in last_messages
                                if isinstance(msg.action, Action)
                            ]
                        )

                        summary_valid = True

                        # Check includes
                        for keyword in should_include:
                            if keyword.lower() not in message_content:
                                issues.append(
                                    f"Turn {turn_num}: Summary should mention '{keyword}'"
                                )
                                summary_valid = False

                        # Check excludes
                        for keyword in should_not_include:
                            if keyword.lower() in message_content:
                                issues.append(
                                    f"Turn {turn_num}: Summary should NOT mention '{keyword}' (cancelled)"
                                )
                                summary_valid = False

                        if summary_valid:
                            checks_passed += 1
                    else:
                        issues.append(f"Turn {turn_num}: No agent summary message found")

            # Calculate success percentage
            success_percentage = (checks_passed / total_checks * 100) if total_checks > 0 else 0

            if success_percentage == 100:
                rationale = (
                    f"All {total_checks} commitment tracking checks passed. "
                    f"Agent successfully managed {len(calendar_app.events)} commitments."
                )
            else:
                rationale = (
                    f"Commitment tracking achieved {success_percentage:.1f}% success rate. "
                    f"Passed {checks_passed}/{total_checks} validation checks.\n"
                    "Issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
                )

            return ScenarioValidationResult(success=success_percentage, rationale=rationale)

        except Exception as e:
            return ScenarioValidationResult(success=None, exception=e)


if __name__ == "__main__":
    from are.simulation.scenarios.utils.cli_utils import run_and_validate

    # Run the scenario in oracle mode and validate
    print("Running Commitment Tracking Scenario in oracle mode...")
    run_and_validate(CommitmentTrackingScenario())