COMMITMENT_FLOW = [
    {
        "turn": 1,
        "delay": 0,
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
        "delay": 3,
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
        "delay": 3,
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
        "delay": 3,
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
        "delay": 3,
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
        "delay": 3,
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
        "delay": 3,
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
        "delay": 3,
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
    {
        "turn": 9,
        "delay": 3,
        "user_message": "That's all for now. You can stop.",
        "expected_actions": {"completion": True},
        "commitment_type": "end_scenario",
    }
]