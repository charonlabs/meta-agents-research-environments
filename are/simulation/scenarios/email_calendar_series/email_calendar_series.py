"""Sequential email-to-calendar coordination scenario."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.calendar import DATETIME_FORMAT, CalendarApp
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import Action, EventRegisterer, EventType


def _timestamp(dt_str: str) -> float:
    """Helper to convert a DATETIME_FORMAT string into a UTC timestamp."""
    return datetime.strptime(dt_str, DATETIME_FORMAT).replace(tzinfo=timezone.utc).timestamp()


EMAIL_EVENT_FLOW: list[dict[str, Any]] = [
    {
        "email_id": "email-calendar-series-budget-review",
        "sender": "finance-ops@lumenicorp.com",
        "subject": "Budget Review with Finance Leadership",
        "content": (
            "Please schedule a budget review on Tuesday, March 4th at 15:00 UTC for one hour. "
            "Invite Dana Chao and flag it with the 'Finance' tag so I remember to prepare numbers."
        ),
        "calendar": {
            "title": "Budget Review with Finance Leadership",
            "start_datetime": "2025-03-04 15:00:00",
            "end_datetime": "2025-03-04 16:00:00",
            "tag": "Finance",
            "description": "Quarterly budget review requested by finance operations.",
            "location": "Conference Room 3A",
            "attendees": ["Dana Chao"],
        },
        "notification_phrase": "Budget review scheduled for March 4 at 15:00 UTC.",
        "notification_keywords": ["budget review", "march 4", "15:00"],
    },
    {
        "email_id": "email-calendar-series-engineering-sync",
        "sender": "platform-leads@lumenicorp.com",
        "subject": "Urgent Platform Stability Sync",
        "content": (
            "We need a platform stability sync on Wednesday, March 5th at 09:30 UTC. "
            "Book 45 minutes, tag it as 'Engineering', and include the platform leads DL."
        ),
        "calendar": {
            "title": "Platform Stability Sync",
            "start_datetime": "2025-03-05 09:30:00",
            "end_datetime": "2025-03-05 10:15:00",
            "tag": "Engineering",
            "description": "Platform stability status review with engineering leads.",
            "location": "Zoom",
            "attendees": ["platform-leads@lumenicorp.com"],
        },
        "notification_phrase": "Platform stability sync is on the calendar for March 5 at 09:30 UTC.",
        "notification_keywords": ["stability sync", "march 5", "09:30"],
    },
    {
        "email_id": "email-calendar-series-product-handoff",
        "sender": "product@lumenicorp.com",
        "subject": "Product Roadmap Handoff",
        "content": (
            "Can you block a product roadmap handoff working session for Thursday, March 6th starting at 13:00 UTC? "
            "Make it a two-hour working session, add the product managers, and tag with 'Product'."
        ),
        "calendar": {
            "title": "Product Roadmap Handoff Working Session",
            "start_datetime": "2025-03-06 13:00:00",
            "end_datetime": "2025-03-06 15:00:00",
            "tag": "Product",
            "description": "Working session to hand off roadmap priorities to delivery teams.",
            "location": "Hybrid - Teams Bridge",
            "attendees": ["product@lumenicorp.com"],
        },
        "notification_phrase": "Scheduled the product roadmap handoff on March 6 at 13:00 UTC.",
        "notification_keywords": ["roadmap handoff", "march 6", "13:00"],
    },
]


@register_scenario("email_calendar_series")
class EmailCalendarSeriesScenario(Scenario):
    """Scenario where the agent must process sequential emails and coordinate calendar updates."""

    start_time: float | None = 0
    duration: float | None = 1800

    def init_and_populate_apps(self, *args, **kwargs) -> None:
        """Initialize apps with default state following primer best practices."""
        agui = AgentUserInterface()
        email_app = EmailClientApp()
        calendar_app = CalendarApp()

        # Provide a friendly heads-up email in the inbox to reinforce context before events begin.
        email_app.add_email(
            Email(
                sender="chief-of-staff@lumenicorp.com",
                recipients=[email_app.user_email],
                subject="Heads-up on incoming scheduling requests",
                content=(
                    "Expect several teams to email in the next hour with scheduling needs. "
                    "Please handle each request and keep me updated."
                ),
                email_id="email-calendar-series-headsup",
            )
        )

        self.apps = [agui, email_app, calendar_app]

    def build_events_flow(self) -> None:
        """Define the timeline of user prompts, incoming emails, and oracle expectations."""
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)
        calendar_app = self.get_typed_app(CalendarApp)

        events = []
        with EventRegisterer.capture_mode():
            kickoff = agui.send_message_to_agent(
                content=(
                    "Morning! Please watch for scheduling emails and keep the calendar organized. "
                    "Let me know once each request is handled."
                )
            ).depends_on(None, delay_seconds=10)
            events.append(kickoff)

            previous_anchor = kickoff

            for index, flow in enumerate(EMAIL_EVENT_FLOW):
                email_event = email_app.send_email_to_user(
                    Email(
                        sender=flow["sender"],
                        recipients=[email_app.user_email],
                        subject=flow["subject"],
                        content=flow["content"],
                        email_id=flow["email_id"],
                    )
                ).depends_on(previous_anchor, delay_seconds=60 if index else 30)
                events.append(email_event)

                calendar_kwargs = flow["calendar"]
                oracle_calendar = (
                    calendar_app.add_calendar_event(
                        title=calendar_kwargs["title"],
                        start_datetime=calendar_kwargs["start_datetime"],
                        end_datetime=calendar_kwargs["end_datetime"],
                        tag=calendar_kwargs["tag"],
                        description=calendar_kwargs["description"],
                        location=calendar_kwargs["location"],
                        attendees=calendar_kwargs["attendees"],
                    )
                    .oracle()
                    .depends_on(email_event, delay_seconds=20)
                )
                events.append(oracle_calendar)

                oracle_notify = (
                    agui.send_message_to_user(content=flow["notification_phrase"])
                    .oracle()
                    .depends_on(oracle_calendar, delay_seconds=15)
                )
                events.append(oracle_notify)

                previous_anchor = email_event.with_type(EventType.ENV)

        self.events = events

    def validate(self, env) -> ScenarioValidationResult:
        """Check that calendar events were added correctly and user notifications were sent."""
        try:
            calendar_app = env.get_app("CalendarApp")
            events = list(calendar_app.events.values())

            calendar_checks: list[str] = []
            for flow in EMAIL_EVENT_FLOW:
                calendar_spec = flow["calendar"]
                expected_start = _timestamp(calendar_spec["start_datetime"])
                expected_end = _timestamp(calendar_spec["end_datetime"])
                attendees_expected = set(calendar_spec["attendees"])

                matches = [
                    event
                    for event in events
                    if event.title == calendar_spec["title"]
                    and abs(event.start_datetime - expected_start) < 1
                    and abs(event.end_datetime - expected_end) < 1
                    and event.tag == calendar_spec["tag"]
                    and event.location == calendar_spec["location"]
                    and set(event.attendees) == attendees_expected
                ]

                if matches:
                    calendar_checks.append("")
                else:
                    calendar_checks.append(
                        f"Missing or incorrect calendar entry for '{calendar_spec['title']}'."
                    )

            notifications_expected = [
                [keyword.lower() for keyword in flow.get("notification_keywords", [])]
                or [flow["calendar"]["title"].lower()]
                for flow in EMAIL_EVENT_FLOW
            ]
            agent_notifications = [
                event
                for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.function_name == "send_message_to_user"
            ]

            notification_results: list[str] = []
            for keywords in notifications_expected:
                if any(
                    all(
                        keyword in str(agent_event.action.args.get("content", "")).lower()
                        for keyword in keywords
                    )
                    for agent_event in agent_notifications
                ):
                    notification_results.append("")
                else:
                    notification_results.append(
                        "User notification missing key details: "
                        + ", ".join(f"'{keyword}'" for keyword in keywords)
                        + "."
                    )

            issues = [issue for issue in calendar_checks + notification_results if issue]
            success = not issues

            rationale = "All scheduling requests handled correctly." if success else " ".join(issues)
            return ScenarioValidationResult(success=success, rationale=rationale)

        except Exception as exc:  # pragma: no cover - defensive validation
            return ScenarioValidationResult(success=False, exception=exc)

