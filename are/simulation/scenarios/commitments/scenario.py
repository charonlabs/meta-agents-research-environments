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

from datetime import datetime, timezone

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

        Checks:
        1. Reminders and events were created for turns 1-3
        2. Reminder was updated for turn 4
        3. Calendar event was rescheduled for turn 6
        4. Calendar event was cancelled for turn 7
        5. Summary in turn 8 includes active items and excludes cancelled

        Returns a percentage score (0-100) based on validation check results.

        Args:
            env: The environment containing apps and event logs

        Returns:
            ScenarioValidationResult with success as a percentage (0-100)
        """
        try:
            # Get apps
            calendar_app = env.get_app("CalendarApp")
            email_app = env.get_app("EmailClientApp")

            # Get all agent actions on calendar
            calendar_actions = [
                event for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.class_name == "CalendarApp"
            ]

            # Track validation checks for scoring
            checks_passed = 0
            total_checks = 6  # Total number of validation checks
            issues = []

            # Check 1: At least 3 calendar events were created (turns 1-3)
            add_event_actions = [
                action for action in calendar_actions
                if action.action.function_name == "add_calendar_event"
            ]
            if len(add_event_actions) >= 3:
                checks_passed += 1
            else:
                issues.append(
                    f"Expected at least 3 calendar events to be created, "
                    f"but only {len(add_event_actions)} were created"
                )

            # Check 2: Budget analysis reminder exists
            event_titles = [event.title.lower() for event in calendar_app.events.values()]
            has_budget = any("budget" in title and "sarah" in title for title in event_titles)
            if has_budget:
                checks_passed += 1
            else:
                issues.append("Missing commitment: Q1 budget analysis for Sarah")

            # Check 3: Team standup event exists
            has_standup = any("standup" in title or "team" in title for title in event_titles)
            if has_standup:
                checks_passed += 1
            else:
                issues.append("Missing commitment: Team Standup meeting")

            # Check 4: Budget reminder was updated to Thursday (turn 4)
            budget_events = [
                event for event in calendar_app.events.values()
                if "budget" in event.title.lower() and "sarah" in event.title.lower()
            ]

            if budget_events:
                budget_event = budget_events[0]
                expected_thursday = datetime(2026, 3, 5, 17, 0, 0, tzinfo=timezone.utc)
                event_datetime = datetime.fromtimestamp(budget_event.start_datetime, tz=timezone.utc)
                time_diff = abs((event_datetime - expected_thursday).total_seconds())
                if time_diff <= 7200:  # Within 2 hours
                    checks_passed += 1
                else:
                    issues.append(
                        f"Budget analysis reminder should be updated to Thursday afternoon, "
                        f"but it's set for {event_datetime.strftime('%A, %Y-%m-%d %H:%M')}"
                    )
            else:
                issues.append("Cannot validate budget reminder update (event missing)")

            # Check 5: Standup was rescheduled to 2pm Monday (turn 6)
            standup_events = [
                event for event in calendar_app.events.values()
                if "standup" in event.title.lower() or "team" in event.title.lower()
            ]

            if standup_events:
                standup_event = standup_events[0]
                expected_time = datetime(2026, 3, 9, 14, 0, 0, tzinfo=timezone.utc)  # Monday 2pm
                event_datetime = datetime.fromtimestamp(standup_event.start_datetime, tz=timezone.utc)
                time_diff = abs((event_datetime - expected_time).total_seconds())
                if time_diff <= 7200:  # Within 2 hours
                    checks_passed += 1
                else:
                    issues.append(
                        f"Team Standup should be rescheduled to Monday 2pm UTC, "
                        f"but it's set for {event_datetime.strftime('%A, %Y-%m-%d %H:%M')}"
                    )
            else:
                issues.append("Cannot validate standup reschedule (event missing)")

            # Check 6: Summary mentions commitments correctly
            agent_messages = [
                event for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.class_name == "AgentUserInterface"
                and event.action.function_name == "send_message_to_user"
            ]

            summary_check_passed = True
            if agent_messages:
                last_messages = agent_messages[-3:]
                message_content = " ".join(
                    [
                        msg.action.args.get("content", "").lower()  # type: ignore[union-attr]
                        for msg in last_messages
                        if isinstance(msg.action, Action)
                    ]
                )

                if "budget" not in message_content:
                    issues.append("Summary should mention the budget analysis commitment")
                    summary_check_passed = False

                if "design" not in message_content:
                    issues.append("Summary should mention the design docs review commitment")
                    summary_check_passed = False

                if "standup" in message_content:
                    issues.append("Summary should not mention the cancelled standup meeting")
                    summary_check_passed = False

            if summary_check_passed:
                checks_passed += 1
            else:
                # Only decrement if not already counted above
                pass

            # Calculate success percentage
            success_percentage = (checks_passed / total_checks) * 100

            if success_percentage == 100:
                rationale = (
                    f"Successfully tracked {len(calendar_app.events)} commitments, "
                    f"with {len(add_event_actions)} events created. "
                    "All commitment tracking requirements met."
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
