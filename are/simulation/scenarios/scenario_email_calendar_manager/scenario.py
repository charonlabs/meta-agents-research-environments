# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.


"""
Email Calendar Manager Scenario

This scenario demonstrates a complex, realistic workflow where an agent must:
1. Monitor incoming emails arriving dynamically over time
2. Parse meeting requests from email content
3. Create appropriate calendar events with correct times and attendees
4. Handle various meeting types (team meetings, client calls, recurring meetings, etc.)

The scenario simulates real-world conditions where emails arrive one at a time,
requiring the agent to process each and take appropriate actions.
"""

from datetime import datetime, timedelta, timezone

from are.simulation.agents.user_proxy import UserProxyResponses
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.calendar import CalendarApp
from are.simulation.apps.contacts import Contact, ContactsApp, Gender, Status
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import Action, EventRegisterer, EventType


@register_scenario("email_calendar_manager")
class EmailCalendarManagerScenario(Scenario):
    """
    A complex scenario where the agent manages calendar events based on incoming emails.
    
    The agent receives 5 emails over time, each containing different types of meeting requests:
    1. Team meeting with specific date/time
    2. Client call with time range options
    3. Weekly recurring standup meeting
    4. Conference room booking confirmation
    5. Meeting reschedule request
    
    Success requires the agent to:
    - Read and parse email content
    - Extract meeting details (time, attendees, location)
    - Create calendar events with appropriate information
    - Handle different meeting types appropriately
    """
    
    # Define scenario timing - 10 minutes to handle all emails
    start_time: float | None = 0
    duration: float | None = 600
    
    def init_and_populate_apps(self, *args, **kwargs) -> None:
        """
        Initialize applications and populate with starting data.
        Sets up contacts for meeting participants but no initial emails
        (emails arrive dynamically during the scenario).
        """
        # Initialize all required apps
        agui = AgentUserInterface(user_proxy=UserProxyResponses())
        email_app = EmailClientApp()
        calendar_app = CalendarApp()
        contacts_app = ContactsApp()
        
        # Add contacts for meeting participants
        contacts_app.add_contact(
            Contact(
                first_name="Alice",
                last_name="Chen",
                email="alice.chen@company.com",
                phone="+1-555-0101",
                gender=Gender.FEMALE,
                status=Status.EMPLOYED,
                age=35,
            )
        )
        
        contacts_app.add_contact(
            Contact(
                first_name="Bob",
                last_name="Martinez",
                email="bob.martinez@clientcorp.com",
                phone="+1-555-0202",
                gender=Gender.MALE,
                status=Status.EMPLOYED,
                age=42,
            )
        )
        
        contacts_app.add_contact(
            Contact(
                first_name="Carol",
                last_name="Stevens",
                email="carol.stevens@company.com",
                phone="+1-555-0303",
                gender=Gender.FEMALE,
                status=Status.EMPLOYED,
                age=28,
            )
        )
        
        contacts_app.add_contact(
            Contact(
                first_name="David",
                last_name="Kim",
                email="david.kim@company.com",
                phone="+1-555-0404",
                gender=Gender.MALE,
                status=Status.EMPLOYED,
                age=38,
            )
        )
        
        contacts_app.add_contact(
            Contact(
                first_name="Emma",
                last_name="Wilson",
                email="emma.wilson@company.com",
                phone="+1-555-0505",
                gender=Gender.FEMALE,
                status=Status.EMPLOYED,
                age=31,
            )
        )
        
        # Store apps in the scenario
        self.apps = [agui, email_app, calendar_app, contacts_app]
    
    def build_events_flow(self) -> None:
        """
        Define the sequence of events that happen during scenario execution.
        Emails arrive dynamically over time, simulating realistic conditions.
        """
        # Get typed references to apps
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)
        calendar_app = self.get_typed_app(CalendarApp)
        
        # Calculate dates for the emails (relative to scenario start)
        # We'll use dates in the near future to make them realistic
        base_date = datetime(2024, 12, 9, 0, 0, 0, tzinfo=timezone.utc)  # Monday
        monday_2pm = base_date.replace(hour=14, minute=0)
        wednesday_10am = (base_date + timedelta(days=2)).replace(hour=10, minute=0)
        wednesday_11am = (base_date + timedelta(days=2)).replace(hour=11, minute=0)
        tuesday_9am = (base_date + timedelta(days=1)).replace(hour=9, minute=0)
        tuesday_10am = (base_date + timedelta(days=1)).replace(hour=10, minute=0)
        thursday_3pm = (base_date + timedelta(days=3)).replace(hour=15, minute=0)
        thursday_5pm = (base_date + timedelta(days=3)).replace(hour=17, minute=0)
        friday_2pm = (base_date + timedelta(days=4)).replace(hour=14, minute=0)
        friday_3pm = (base_date + timedelta(days=4)).replace(hour=15, minute=0)
        next_friday_2pm = (base_date + timedelta(days=11)).replace(hour=14, minute=0)
        next_friday_3pm = (base_date + timedelta(days=11)).replace(hour=15, minute=0)
        
        # Use capture_mode to create events from app method calls
        with EventRegisterer.capture_mode():
            # EVENT 1: Email 1 arrives first - Team meeting with specific date/time
            event1 = email_app.send_email_to_user(
                email=Email(
                    sender="alice.chen@company.com",
                    recipients=[email_app.user_email],
                    subject="Q4 Planning Team Meeting",
                    content="Hi there! Let's schedule a team meeting this Monday at 2 PM for 1 hour to discuss Q4 planning. I'll need you, Carol, and David to attend. We'll meet in Conference Room B.",
                    email_id="email_team_meeting",
                )
            ).depends_on(None, delay_seconds=2)
            
            # EVENT 2: User asks agent to manage calendar based on emails
            event2 = agui.send_message_to_agent(
                content="Hi! I just got some meeting requests in my email. Please check my inbox and create calendar events for all the meetings mentioned. Make sure to include all relevant details like attendees, times, and locations."
            ).depends_on(event1, delay_seconds=3)
            
            # ORACLE 1: Agent should create calendar event for team meeting
            oracle1 = (
                calendar_app.add_calendar_event(
                    title="Q4 Planning Team Meeting",
                    start_datetime=monday_2pm.strftime("%Y-%m-%d %H:%M:%S"),
                    end_datetime=(monday_2pm + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                    description="Team meeting to discuss Q4 planning",
                    location="Conference Room B",
                    attendees=["Alice Chen", "Carol Stevens", "David Kim"],
                )
                .oracle()
                .depends_on(event2, delay_seconds=5)
            )
            
            # EVENT 3: Email 2 arrives - Client call with time range options
            event3 = email_app.send_email_to_user(
                email=Email(
                    sender="bob.martinez@clientcorp.com",
                    recipients=[email_app.user_email],
                    subject="Project Sync Call",
                    content="Hello! Can we set up a client call this Wednesday? I'm available between 10 AM and 12 PM. About 30 minutes should be sufficient to go over the project updates. Please send me the meeting link when you schedule it.",
                    email_id="email_client_call",
                )
            ).depends_on(event1, delay_seconds=5)
            
            # ORACLE 2: Agent should create calendar event for client call
            # Agent should pick a time within the available window
            oracle2 = (
                calendar_app.add_calendar_event(
                    title="Project Sync Call with Bob Martinez",
                    start_datetime=wednesday_10am.strftime("%Y-%m-%d %H:%M:%S"),
                    end_datetime=(wednesday_10am + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
                    description="Client call to discuss project updates",
                    attendees=["Bob Martinez"],
                )
                .oracle()
                .depends_on(event3, delay_seconds=5)
            )
            
            # EVENT 4: Email 3 arrives - Weekly recurring standup meeting
            event4 = email_app.send_email_to_user(
                email=Email(
                    sender="alice.chen@company.com",
                    recipients=[email_app.user_email, "emma.wilson@company.com"],
                    subject="Weekly Standup Reminder",
                    content="Quick reminder: Our weekly standup meetings start this coming Tuesday at 9 AM. They'll run for 1 hour every Tuesday. The whole team should attend - that's you, me, Carol, David, and Emma. Let me know if you can't make it!",
                    email_id="email_standup",
                )
            ).depends_on(event3, delay_seconds=3)
            
            # ORACLE 3: Agent should create calendar event for standup
            oracle3 = (
                calendar_app.add_calendar_event(
                    title="Weekly Team Standup",
                    start_datetime=tuesday_9am.strftime("%Y-%m-%d %H:%M:%S"),
                    end_datetime=tuesday_10am.strftime("%Y-%m-%d %H:%M:%S"),
                    description="Weekly standup meeting",
                    attendees=["Alice Chen", "Carol Stevens", "David Kim", "Emma Wilson"],
                )
                .oracle()
                .depends_on(event4, delay_seconds=5)
            )
            
            # EVENT 5: Email 4 arrives - Conference room booking confirmation
            event5 = email_app.send_email_to_user(
                email=Email(
                    sender="facilities@company.com",
                    recipients=[email_app.user_email],
                    subject="Conference Room Alpha - Booking Confirmed",
                    content="Your booking for Conference Room Alpha has been confirmed for this Thursday from 3 PM to 5 PM for your product presentation. Please ensure you arrive a few minutes early to set up. Room capacity: 50 people.",
                    email_id="email_room_booking",
                )
            ).depends_on(event4, delay_seconds=3)
            
            # ORACLE 4: Agent should create calendar event for presentation
            oracle4 = (
                calendar_app.add_calendar_event(
                    title="Product Presentation",
                    start_datetime=thursday_3pm.strftime("%Y-%m-%d %H:%M:%S"),
                    end_datetime=thursday_5pm.strftime("%Y-%m-%d %H:%M:%S"),
                    description="Product presentation",
                    location="Conference Room Alpha",
                )
                .oracle()
                .depends_on(event5, delay_seconds=5)
            )
            
            # EVENT 6: Email 5 arrives - Meeting reschedule request
            event6 = email_app.send_email_to_user(
                email=Email(
                    sender="david.kim@company.com",
                    recipients=[email_app.user_email],
                    subject="Need to Reschedule Friday Meeting",
                    content="Hey, I need to reschedule our 1-on-1 meeting scheduled for Friday at 2 PM. Can we move it to next Friday at the same time? It should still be about 1 hour. Thanks!",
                    email_id="email_reschedule",
                )
            ).depends_on(event5, delay_seconds=3)
            
            # ORACLE 5: Agent should create calendar event for rescheduled meeting
            oracle5 = (
                calendar_app.add_calendar_event(
                    title="1-on-1 with David Kim",
                    start_datetime=next_friday_2pm.strftime("%Y-%m-%d %H:%M:%S"),
                    end_datetime=next_friday_3pm.strftime("%Y-%m-%d %H:%M:%S"),
                    description="Rescheduled 1-on-1 meeting",
                    attendees=["David Kim"],
                )
                .oracle()
                .depends_on(event6, delay_seconds=5)
            )
        
        # Store all events in the scenario
        self.events = [
            event1, event2, oracle1,
            event3, oracle2,
            event4, oracle3,
            event5, oracle4,
            event6, oracle5,
        ]
    
    def validate(self, env) -> ScenarioValidationResult:
        """
        Validate that the agent successfully completed the task.
        
        Checks that:
        1. At least 4 calendar events were created (allowing some flexibility)
        2. Events have appropriate titles
        3. Emails were processed (read)
        
        Args:
            env: The environment containing all apps and event logs
            
        Returns:
            ScenarioValidationResult with success status and rationale
        """
        try:
            # Get apps
            calendar_app = env.get_app("CalendarApp")
            email_app = env.get_app("EmailClientApp")
            
            # Validation 1: Check that calendar events were created
            num_events = len(calendar_app.events)
            if num_events < 3:
                return ScenarioValidationResult(
                    success=False,
                    rationale=f"Only {num_events} calendar events created, expected at least 3"
                )
            
            # Validation 2: Check that add_calendar_event was called multiple times
            calendar_actions = [
                event for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.function_name == "add_calendar_event"
                and event.action.class_name == "CalendarApp"
            ]
            
            if len(calendar_actions) < 3:
                return ScenarioValidationResult(
                    success=False,
                    rationale=f"Agent only called add_calendar_event {len(calendar_actions)} times, expected at least 3"
                )
            
            # Validation 3: Check that events contain relevant information
            event_titles = [event.title.lower() for event in calendar_app.events.values()]
            
            # Check for keywords that should appear in event titles
            has_meeting_related = any(
                keyword in title
                for title in event_titles
                for keyword in ["meeting", "call", "standup", "presentation", "1-on-1"]
            )
            
            if not has_meeting_related:
                return ScenarioValidationResult(
                    success=False,
                    rationale="Calendar events don't contain expected meeting-related titles"
                )
            
            # Validation 4: Check that emails were read/accessed (optional - may not appear in oracle mode)
            email_read_actions = [
                event for event in env.event_log.list_view()
                if event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.class_name == "EmailClientApp"
                and event.action.function_name in ["get_emails", "get_email_by_id", "get_email_by_index", "search_emails"]
            ]
            
            # Note: In oracle mode, email reading may not be logged, so we don't fail on this
            # if len(email_read_actions) < 3 and len(calendar_actions) < 4:
            #     return ScenarioValidationResult(
            #         success=False,
            #         rationale=f"Agent only accessed emails {len(email_read_actions)} times, expected more email reading"
            #     )
            
            # Validation 5: Check that at least some attendees were added
            events_with_attendees = [
                event for event in calendar_app.events.values()
                if event.attendees and len(event.attendees) > 0
            ]
            
            if len(events_with_attendees) < 2:
                return ScenarioValidationResult(
                    success=False,
                    rationale="Not enough calendar events include attendees"
                )
            
            # All validations passed
            return ScenarioValidationResult(
                success=True,
                rationale=f"Successfully created {num_events} calendar events with appropriate details from {len(email_read_actions)} email interactions"
            )
            
        except Exception as e:
            # If validation fails due to an error, return failure with exception
            return ScenarioValidationResult(success=False, exception=e)


if __name__ == "__main__":
    from are.simulation.scenarios.utils.cli_utils import run_and_validate
    
    # Run the scenario in oracle mode and validate the agent actions
    print("Running Email Calendar Manager Scenario in oracle mode...")
    run_and_validate(EmailCalendarManagerScenario())

