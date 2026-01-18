"""Multi-turn commitment tracking scenario testing obligation management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.calendar import DATETIME_FORMAT, CalendarApp
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.apps.reminder import ReminderApp
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import Action, EventRegisterer, EventType

logger = logging.getLogger(__name__)

# Scenario timezone configuration
SCENARIO_TIMEZONE = ZoneInfo("America/New_York")
TIMESTAMP_TOLERANCE_SECONDS = 2.0


def parse_dt(dt_str: str, tz: ZoneInfo = SCENARIO_TIMEZONE) -> datetime:
    """Parse YYYY-MM-DD HH:MM:SS string into timezone-aware datetime.
    
    Args:
        dt_str: Datetime string in format YYYY-MM-DD HH:MM:SS
        tz: Timezone to use (defaults to scenario timezone)
        
    Returns:
        Timezone-aware datetime object
    """
    naive_dt = datetime.strptime(dt_str, DATETIME_FORMAT)
    return naive_dt.replace(tzinfo=tz)


def to_timestamp(dt: datetime | str) -> float:
    """Convert datetime or string to UTC timestamp.
    
    Args:
        dt: Either a datetime object or YYYY-MM-DD HH:MM:SS string
        
    Returns:
        UTC POSIX timestamp as float
    """
    if isinstance(dt, str):
        dt = parse_dt(dt)
    return dt.timestamp()


def normalize_datetime(value: Any) -> datetime | None:
    """Normalize various datetime representations to timezone-aware datetime.
    
    Args:
        value: Can be datetime, float timestamp, or string
        
    Returns:
        Timezone-aware datetime or None if conversion fails
    """
    try:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(value, str):
            return parse_dt(value)
        return None
    except Exception as e:
        logger.warning(f"Failed to normalize datetime {value}: {e}")
        return None


# Multi-turn commitment flow with explicit, implicit, updates, and cancellations
# All datetimes are in scenario timezone (America/New_York) and use year 2026
COMMITMENT_FLOW: list[dict[str, Any]] = [
    {
        "turn": 1,
        "delay": 10,
        "user_message": (
            "Hey! Can you help me track some commitments this week? "
            "First, I promised Sarah I'd send her the Q1 budget analysis by end of day Friday. "
            "Can you make sure I don't forget?"
        ),
        "expected_actions": {
            "reminder": {
                "title": "Send Q1 budget analysis to Sarah",
                "due_datetime": "2026-03-06 23:59:00",  # Friday EOD (scenario timezone)
                "description_keywords": ["budget", "analysis", "Sarah"],
            }
        },
        "notification_keywords": ["budget", "friday", "reminder"],
        "commitment_type": "explicit_reminder",
    },
    {
        "turn": 2,
        "delay": 45,
        "user_message": (
            "Also, I need to schedule a team standup for Monday at 10am UTC. "
            "It should be 30 minutes. Add the whole engineering team."
        ),
        "expected_actions": {
            "calendar": {
                "title": "Team Standup",
                "start_datetime": "2026-03-09 10:00:00",  # Monday (scenario timezone)
                "end_datetime": "2026-03-09 10:30:00",
                "attendees": ["engineering team"],
            }
        },
        "notification_keywords": ["standup", "monday", "scheduled"],
        "commitment_type": "explicit_calendar",
    },
    {
        "turn": 3,
        "delay": 60,
        "user_message": (
            "Oh, and I'll try to review the design docs over the weekend if I get a chance. "
            "Nothing urgent, but would be good to have a note about it."
        ),
        "expected_actions": {
            "reminder": {
                "title": "Review design docs",
                "due_datetime": "2026-03-08 17:00:00",  # Sunday afternoon (scenario timezone)
                "description_keywords": ["design", "docs", "review"],
                "optional": True,  # Implicit commitment
            }
        },
        "notification_keywords": ["design docs", "weekend"],
        "commitment_type": "implicit_reminder",
    },
    {
        "turn": 4,
        "delay": 50,
        "email": {
            "sender": "sarah@company.com",
            "subject": "Budget Analysis Timeline Change",
            "content": (
                "Hi! Actually, can you send the budget analysis by Thursday afternoon instead? "
                "We moved up the board meeting. Thanks!"
            ),
        },
        "expected_actions": {
            "reminder_update": {
                "original_title": "Send Q1 budget analysis to Sarah",
                "new_due_datetime": "2026-03-05 17:00:00",  # Thursday afternoon (scenario timezone)
            }
        },
        "notification_keywords": ["budget", "thursday", "moved"],
        "commitment_type": "update_reminder",
    },
    {
        "turn": 5,
        "delay": 55,
        "user_message": (
            "Just saw Sarah's email about moving the deadline. Can you update that commitment?"
        ),
        "expected_actions": {
            "confirmation": True,
        },
        "notification_keywords": ["updated", "thursday"],
        "commitment_type": "acknowledge_update",
    },
    {
        "turn": 6,
        "delay": 60,
        "user_message": (
            "Actually, the team standup on Monday needs to be pushed to 2pm UTC instead. "
            "10am won't work for the west coast folks."
        ),
        "expected_actions": {
            "calendar_update": {
                "original_title": "Team Standup",
                "new_start_datetime": "2026-03-09 14:00:00",  # Monday 2pm (scenario timezone)
                "new_end_datetime": "2026-03-09 14:30:00",
            }
        },
        "notification_keywords": ["standup", "2pm", "rescheduled"],
        "commitment_type": "reschedule_meeting",
    },
    {
        "turn": 7,
        "delay": 45,
        "email": {
            "sender": "manager@company.com",
            "subject": "Skip This Week's Standup",
            "content": (
                "Team - let's cancel Monday's standup. We're all heads-down on the release. "
                "We'll resume next week."
            ),
        },
        "expected_actions": {
            "calendar_cancel": {
                "title": "Team Standup",
            }
        },
        "notification_keywords": ["standup", "cancelled"],
        "commitment_type": "cancel_meeting",
    },
    {
        "turn": 8,
        "delay": 50,
        "user_message": (
            "Can you give me a summary of all my current commitments? "
            "I want to make sure I'm not missing anything."
        ),
        "expected_actions": {
            "summary": {
                "should_include": [
                    "budget analysis",  # Updated to Thursday
                    "design docs",  # Optional weekend task
                ],
                "should_not_include": [
                    "standup",  # Cancelled
                ],
            }
        },
        "notification_keywords": ["commitments", "budget", "design"],
        "commitment_type": "summary_request",
    },
]


@register_scenario("commitment_tracking")
class CommitmentTrackingScenario(Scenario):
    """
    Multi-turn scenario testing a model's ability to:
    - Record explicit commitments (schedule meeting, set reminder)
    - Track implicit commitments (soft promises like "I'll try to...")
    - Update commitments when circumstances change
    - Cancel commitments when no longer needed
    - Summarize active commitments accurately
    
    Partial credit is possible based on how many commitment operations succeed.
    """

    start_time: float | None = 0
    duration: float | None = 900  # 15 minutes to allow for 8 turns

    def init_and_populate_apps(self, *args, **kwargs) -> None:
        """Initialize apps with minimal initial state."""
        agui = AgentUserInterface()
        email_app = EmailClientApp()
        calendar_app = CalendarApp()
        reminder_app = ReminderApp()

        # Send a brief intro email to set context
        email_app.add_email(
            Email(
                sender="assistant-intro@company.com",
                recipients=[email_app.user_email],
                subject="Welcome to Your Commitment Tracker",
                content=(
                    "Hi! I'm here to help you track your commitments and obligations. "
                    "Just let me know what you need to remember, and I'll make sure "
                    "you stay on top of everything."
                ),
                email_id="commitment-tracking-intro",
            )
        )

        self.apps = [agui, email_app, calendar_app, reminder_app]

    def build_events_flow(self) -> None:
        """Define the multi-turn conversation with various commitment operations."""
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)
        calendar_app = self.get_typed_app(CalendarApp)
        reminder_app = self.get_typed_app(ReminderApp)

        events = []
        previous_anchor = None

        with EventRegisterer.capture_mode():
            for idx, turn in enumerate(COMMITMENT_FLOW):
                delay = turn["delay"]
                
                # User message or incoming email
                if "user_message" in turn:
                    user_event = agui.send_message_to_agent(
                        content=turn["user_message"]
                    ).depends_on(previous_anchor, delay_seconds=delay)
                    events.append(user_event)
                    previous_anchor = user_event.with_type(EventType.ENV)
                
                elif "email" in turn:
                    email_data = turn["email"]
                    email_event = email_app.send_email_to_user(
                        Email(
                            sender=email_data["sender"],
                            recipients=[email_app.user_email],
                            subject=email_data["subject"],
                            content=email_data["content"],
                            email_id=f"commitment-tracking-turn-{idx+1}",
                        )
                    ).depends_on(previous_anchor, delay_seconds=delay)
                    events.append(email_event)
                    previous_anchor = email_event.with_type(EventType.ENV)

                # Set up oracle expectations for different commitment types
                commitment_type = turn["commitment_type"]
                expected = turn["expected_actions"]

                if commitment_type in ["explicit_reminder", "implicit_reminder"]:
                    reminder_data = expected["reminder"]
                    oracle_reminder = (
                        reminder_app.add_reminder(
                            title=reminder_data["title"],
                            due_datetime=reminder_data["due_datetime"],
                            description=" ".join(reminder_data["description_keywords"]),
                        )
                        .oracle()
                        .depends_on(previous_anchor, delay_seconds=15)
                    )
                    events.append(oracle_reminder)
                
                elif commitment_type == "explicit_calendar":
                    cal_data = expected["calendar"]
                    oracle_calendar = (
                        calendar_app.add_calendar_event(
                            title=cal_data["title"],
                            start_datetime=cal_data["start_datetime"],
                            end_datetime=cal_data["end_datetime"],
                            attendees=cal_data["attendees"],
                        )
                        .oracle()
                        .depends_on(previous_anchor, delay_seconds=15)
                    )
                    events.append(oracle_calendar)
                
                elif commitment_type == "reschedule_meeting":
                    # Oracle for updating the calendar event
                    cal_update = expected["calendar_update"]
                    # We expect the agent to delete old and create new or update existing
                    oracle_reschedule = (
                        calendar_app.add_calendar_event(
                            title=cal_update["original_title"],
                            start_datetime=cal_update["new_start_datetime"],
                            end_datetime=cal_update["new_end_datetime"],
                            attendees=["engineering team"],
                        )
                        .oracle()
                        .depends_on(previous_anchor, delay_seconds=20)
                    )
                    events.append(oracle_reschedule)

        self.events = events

    def validate(self, env) -> ScenarioValidationResult:
        """
        Validate commitment tracking across multiple dimensions.
        Award partial credit based on successful operations.
        Uses tolerant timestamp comparisons and robust event-log inspection.
        """
        # Define all expected checks upfront for deterministic scoring
        EXPECTED_CHECKS = [
            "budget_reminder_created",
            "budget_reminder_updated",
            "standup_created",
            "standup_rescheduled",
            "standup_cancelled",
            "implicit_reminder_tracked",
            "summary_provided",
        ]
        
        results: dict[str, bool] = {check: False for check in EXPECTED_CHECKS}
        issues: list[str] = []

        try:
            calendar_app = env.get_app("CalendarApp")
            reminder_app = env.get_app("ReminderApp")
            
            # Helper to compare timestamps with tolerance
            def timestamps_match(actual: Any, expected_str: str) -> bool:
                """Compare timestamp with tolerance for clock skew."""
                try:
                    actual_dt = normalize_datetime(actual)
                    expected_dt = parse_dt(expected_str)
                    if actual_dt and expected_dt:
                        diff = abs(actual_dt.timestamp() - expected_dt.timestamp())
                        return diff < TIMESTAMP_TOLERANCE_SECONDS
                    return False
                except Exception as e:
                    logger.warning(f"Timestamp comparison failed: {e}")
                    return False

            # Check Turn 1: Explicit reminder for budget analysis
            try:
                budget_reminders = [
                    r for r in reminder_app.reminders.values()
                    if "budget" in r.title.lower() and "sarah" in r.title.lower()
                ]
                if budget_reminders:
                    results["budget_reminder_created"] = True
                    # Check if updated to Thursday (Turn 4-5)
                    thursday_updated = any(
                        timestamps_match(r.due_datetime, "2026-03-05 17:00:00")
                        for r in budget_reminders
                    )
                    results["budget_reminder_updated"] = thursday_updated
                    if not thursday_updated:
                        issues.append("Budget reminder not updated to Thursday afternoon as requested.")
                else:
                    issues.append("Budget analysis reminder for Sarah not created.")
            except Exception as e:
                logger.error(f"Budget reminder validation error: {e}")
                issues.append(f"Budget reminder check failed: {str(e)[:50]}")

            # Check Turn 2 & 7: Team standup meeting (should be created, rescheduled, then cancelled)
            try:
                standup_events = [
                    e for e in calendar_app.events.values()
                    if "standup" in e.title.lower()
                ]
                
                # Check event log to see if standup was ever created
                agent_calendar_actions = self._get_agent_actions(
                    env, ["add_calendar_event", "update_calendar_event"]
                )
                standup_created = any(
                    "standup" in str(self._safe_get_arg(act, "title", "")).lower()
                    for act in agent_calendar_actions
                )
                results["standup_created"] = standup_created
                
                # Should be cancelled (Turn 7) so should not exist in final state
                if not standup_events:
                    results["standup_cancelled"] = True
                else:
                    issues.append("Standup meeting still exists but should have been cancelled.")
            except Exception as e:
                logger.error(f"Standup validation error: {e}")
                issues.append(f"Standup check failed: {str(e)[:50]}")

            # Check Turn 3: Implicit design docs reminder (optional but good to track)
            try:
                design_reminders = [
                    r for r in reminder_app.reminders.values()
                    if "design" in r.title.lower() and "doc" in r.title.lower()
                ]
                results["implicit_reminder_tracked"] = len(design_reminders) > 0
            except Exception as e:
                logger.error(f"Design docs reminder validation error: {e}")
                issues.append(f"Design docs check failed: {str(e)[:50]}")

            # Check Turn 6: Standup rescheduled to 2pm (check event log)
            try:
                rescheduled_action_found = False
                for action in agent_calendar_actions:
                    title = self._safe_get_arg(action, "title", "")
                    start_time = self._safe_get_arg(action, "start_datetime", "")
                    if "standup" in str(title).lower():
                        # Look for 2pm (14:00) in the start time
                        if "14:00" in str(start_time) or timestamps_match(start_time, "2026-03-09 14:00:00"):
                            rescheduled_action_found = True
                            break
                
                results["standup_rescheduled"] = rescheduled_action_found
                if not rescheduled_action_found and standup_created:
                    issues.append("Standup was not rescheduled to 2pm as requested.")
            except Exception as e:
                logger.error(f"Standup reschedule validation error: {e}")
                issues.append(f"Standup reschedule check failed: {str(e)[:50]}")

            # Check Turn 8: Summary request - verify agent provided summary
            try:
                agent_messages = self._get_agent_actions(env, ["send_message_to_user"])
                summary_found = False
                
                for action in agent_messages:
                    content = str(self._safe_get_arg(action, "content", "")).lower()
                    # Look for summary-like messages mentioning commitments
                    if any(keyword in content for keyword in ["commitment", "summary", "current", "tracking"]):
                        has_budget = "budget" in content
                        # Summary should mention active commitments (budget, possibly design)
                        # but not cancelled ones (standup)
                        if has_budget:
                            summary_found = True
                            break
                
                results["summary_provided"] = summary_found
                if not summary_found:
                    issues.append("Agent did not provide a commitment summary when requested.")
            except Exception as e:
                logger.error(f"Summary validation error: {e}")
                issues.append(f"Summary check failed: {str(e)[:50]}")

        except Exception as exc:
            logger.exception("Critical validation error")
            return ScenarioValidationResult(
                success=False,
                rationale=f"Critical validation error: {str(exc)}",
                exception=exc,
            )

        # Calculate partial credit score
        total_checks = len(EXPECTED_CHECKS)
        passed_checks = sum(results.values())
        success_rate = passed_checks / total_checks if total_checks > 0 else 0

        # Consider it a success if >= 60% of checks pass
        success = success_rate >= 0.6

        if success:
            rationale = (
                f"Commitment tracking successful. "
                f"Passed {passed_checks}/{total_checks} checks ({success_rate:.0%}). "
            )
            if issues:
                rationale += f"Minor issues: {' '.join(issues[:2])}"
        else:
            rationale = (
                f"Commitment tracking incomplete. "
                f"Only {passed_checks}/{total_checks} checks passed ({success_rate:.0%}). "
                f"Issues: {' '.join(issues[:3])}"
            )

        return ScenarioValidationResult(
            success=success,
            rationale=rationale,
        )

    def _get_agent_actions(self, env, function_names: list[str]) -> list[Any]:
        """Safely extract agent actions from event log with robust inspection."""
        actions = []
        try:
            for event in env.event_log.list_view():
                # Robust type checking
                event_type = getattr(event, "event_type", None)
                if event_type != EventType.AGENT:
                    continue
                
                action = getattr(event, "action", None)
                if action is None:
                    continue
                
                # Handle both Action objects and dict-like structures
                if isinstance(action, Action):
                    func_name = getattr(action, "function_name", "")
                elif hasattr(action, "get"):
                    func_name = action.get("function_name", "")
                else:
                    continue
                
                if func_name in function_names:
                    actions.append(action)
        except Exception as e:
            logger.warning(f"Error extracting agent actions: {e}")
        
        return actions
    
    def _safe_get_arg(self, action: Any, key: str, default: Any = None) -> Any:
        """Safely extract argument from action object."""
        try:
            if isinstance(action, Action):
                return getattr(action, "args", {}).get(key, default)
            elif hasattr(action, "args"):
                args = getattr(action, "args", {})
                if hasattr(args, "get"):
                    return args.get(key, default)
                return getattr(args, key, default)
            elif hasattr(action, "get"):
                args = action.get("args", {})
                if hasattr(args, "get"):
                    return args.get(key, default)
            return default
        except Exception as e:
            logger.warning(f"Error extracting arg '{key}': {e}")
            return default
