# Email Calendar Manager Scenario

## Overview

This scenario demonstrates a complex, realistic workflow where an AI agent must monitor incoming emails and automatically create calendar events based on the meeting requests found in those emails. The scenario simulates real-world conditions where emails arrive dynamically over time, requiring the agent to process each one and take appropriate action.

## Scenario Description

The agent is tasked with managing a user's calendar by:
1. Monitoring incoming emails as they arrive
2. Parsing meeting requests from email content
3. Extracting relevant details (date, time, attendees, location)
4. Creating appropriate calendar events with all necessary information
5. Handling various types of meetings (team meetings, client calls, recurring meetings, etc.)

## Email Sequence

The scenario includes 5 emails that arrive one at a time:

1. **Team Meeting Request** (arrives at t=15s)
   - From: Alice Chen
   - Details: Monday at 2 PM for 1 hour, Q4 planning discussion
   - Attendees: Alice, Carol, David
   - Location: Conference Room B

2. **Client Call Request** (arrives at t=30s)
   - From: Bob Martinez (external client)
   - Details: Wednesday between 10 AM - 12 PM, 30 minutes needed
   - Attendees: Bob Martinez
   - Purpose: Project updates

3. **Weekly Standup Reminder** (arrives at t=50s)
   - From: Alice Chen
   - Details: Every Tuesday at 9 AM for 1 hour, starting this week
   - Attendees: Alice, Carol, David, Emma, and the user
   - Purpose: Weekly team synchronization

4. **Conference Room Booking** (arrives at t=70s)
   - From: Facilities
   - Details: Thursday 3 PM - 5 PM
   - Location: Conference Room Alpha
   - Purpose: Product presentation

5. **Meeting Reschedule** (arrives at t=90s)
   - From: David Kim
   - Details: Move Friday 2 PM meeting to next Friday same time
   - Duration: 1 hour
   - Purpose: 1-on-1 discussion

## Success Criteria

The agent successfully completes the scenario if it:
- Creates at least 4 calendar events
- Includes appropriate titles for meetings
- Reads/accesses the incoming emails
- Adds attendees to calendar events when mentioned
- Extracts correct timing information from emails

## Apps Used

- **AgentUserInterface**: User-agent communication
- **EmailClientApp**: Email management and inbox access
- **CalendarApp**: Calendar event creation and management
- **ContactsApp**: Contact information for meeting participants

## Running the Scenario

### Oracle Mode (for testing)
```bash
uv run are-run -s email_calendar_manager -a default --oracle-mode
```

### With Real Agent (GPT-5-mini)
```bash
uv run are-run -s email_calendar_manager -a responses --model gpt-5-mini --provider openai
```

### Python Direct Execution
```bash
python -m are.simulation.scenarios.scenario_email_calendar_manager.scenario
```

## Duration

The scenario runs for 600 seconds (10 minutes) to allow enough time for:
- The agent to process each incoming email
- Create calendar events with appropriate details
- Handle all 5 meeting requests

## Complexity Level

**Advanced** - This scenario requires the agent to:
- Parse natural language descriptions of meetings
- Extract structured information (dates, times, attendees)
- Manage multiple concurrent tasks
- Handle different meeting types appropriately
- Demonstrate understanding of calendar scheduling concepts

## Educational Value

This scenario is useful for:
- Testing email-to-calendar automation capabilities
- Evaluating natural language understanding
- Assessing multi-app coordination skills
- Demonstrating realistic office automation workflows
- Training agents on dynamic, time-based task handling

