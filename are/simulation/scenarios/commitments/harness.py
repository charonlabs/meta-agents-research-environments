#!/usr/bin/env python3
"""
Commitment Tracking Evaluation Harness

This harness evaluates an AI assistant's ability to track, update, and manage
commitments across an 8-turn conversation scenario.

To use with a real LLM:
1. Subclass AgentInterface and implement call_agent()
2. Pass your implementation to run_evaluation()

Example:
    class OpenAIAgent(AgentInterface):
        def call_agent(self, prompt: str) -> str:
            # Call OpenAI API here
            return response
    
    harness = CommitmentHarness(OpenAIAgent())
    results = harness.run_evaluation()
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# SCENARIO SPECIFICATION
# =============================================================================

COMMITMENT_FLOW: List[Dict[str, Any]] = [
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
                "due_datetime": "2026-03-06 23:59:00",
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
                "start_datetime": "2026-03-09 10:00:00",
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
                "due_datetime": "2026-03-08 17:00:00",
                "description_keywords": ["design", "docs", "review"],
                "optional": True,
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
                "new_due_datetime": "2026-03-05 17:00:00",
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
                "new_start_datetime": "2026-03-09 14:00:00",
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
                    "budget analysis",
                    "design docs",
                ],
                "should_not_include": [
                    "standup",
                ],
            }
        },
        "notification_keywords": ["commitments", "budget", "design"],
        "commitment_type": "summary_request",
    },
]

# =============================================================================
# AGENT INTERFACE
# =============================================================================

class AgentInterface(ABC):
    """
    Abstract interface for AI agent implementations.
    
    Users should subclass this and implement call_agent() to connect to
    their LLM of choice (OpenAI, Anthropic, local model, etc.).
    """
    
    @abstractmethod
    def call_agent(self, prompt: str) -> str:
        """
        Send a prompt to the agent and return its response.
        
        Args:
            prompt: The full prompt including system message and user message
            
        Returns:
            The agent's response as a string
        """
        pass

class StubAgent(AgentInterface):
    """
    Stub implementation that raises an informative error.
    
    Replace this with a real implementation to test actual LLMs.
    """
    
    def call_agent(self, prompt: str) -> str:
        raise NotImplementedError(
            "StubAgent.call_agent() must be replaced with a real implementation.\n"
            "To use this harness:\n"
            "1. Subclass AgentInterface\n"
            "2. Implement call_agent() to call your LLM API\n"
            "3. Pass your implementation to CommitmentHarness()\n"
            "\n"
            "Example:\n"
            "    class MyAgent(AgentInterface):\n"
            "        def call_agent(self, prompt: str) -> str:\n"
            "            # Call OpenAI/Anthropic/etc. here\n"
            "            return response_text\n"
        )

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Commitment:
    """Represents a tracked commitment (reminder or calendar event)."""
    id: str
    commitment_type: str  # "reminder" or "event"
    title: str
    due_datetime: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    notes: str = ""
    optional: bool = False
    cancelled: bool = False

@dataclass
class TurnResult:
    """Results from evaluating a single turn."""
    turn: int
    parsed: bool
    parsing_error: Optional[str] = None
    expected: str = ""
    observed_actions: List[Dict[str, Any]] = field(default_factory=list)
    passed: bool = False
    issues: List[str] = field(default_factory=list)

# =============================================================================
# RESPONSE PARSER
# =============================================================================

class ResponseParser:
    """Parses and validates agent responses against the expected JSON schema."""
    
    @staticmethod
    def parse_response(response: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Parse agent response, attempting to extract valid JSON.
        
        Args:
            response: Raw agent response string
            
        Returns:
            Tuple of (parsed_json, error_message)
            If parsing succeeds, returns (json_dict, None)
            If parsing fails, returns (None, error_message)
        """
        # Try to parse first line as JSON
        first_line = response.strip().split('\n')[0].strip()
        
        try:
            data = json.loads(first_line)
            return data, None
        except json.JSONDecodeError:
            pass
        
        # Try to parse entire response as JSON
        try:
            data = json.loads(response.strip())
            return data, None
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        if matches:
            try:
                data = json.loads(matches[0])
                return data, "JSON extracted from code block (penalty applied)"
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object in the response
        json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_obj_pattern, response, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if 'actions' in data:
                    return data, "JSON extracted heuristically (penalty applied)"
            except json.JSONDecodeError:
                continue
        
        return None, f"Failed to parse JSON from response: {response[:100]}..."
    
    @staticmethod
    def validate_schema(data: Dict[str, Any]) -> List[str]:
        """
        Validate that parsed JSON matches expected schema.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if 'actions' not in data:
            errors.append("Missing required 'actions' field")
            return errors
        
        if not isinstance(data['actions'], list):
            errors.append("'actions' must be a list")
            return errors
        
        valid_action_types = {
            'create_reminder', 'create_event', 'update_reminder',
            'update_event', 'cancel_event', 'confirm', 'summary'
        }
        
        for i, action in enumerate(data['actions']):
            if not isinstance(action, dict):
                errors.append(f"Action {i} must be a dictionary")
                continue
            
            if 'action_type' not in action:
                errors.append(f"Action {i} missing 'action_type'")
                continue
            
            action_type = action['action_type']
            if action_type not in valid_action_types:
                errors.append(f"Action {i} has invalid action_type: {action_type}")
            
            # Validate required fields based on action type
            if action_type == 'create_reminder':
                if 'title' not in action:
                    errors.append(f"Action {i} (create_reminder) missing 'title'")
                if 'due_datetime' not in action:
                    errors.append(f"Action {i} (create_reminder) missing 'due_datetime'")
            
            elif action_type == 'create_event':
                if 'title' not in action:
                    errors.append(f"Action {i} (create_event) missing 'title'")
                if 'start_datetime' not in action:
                    errors.append(f"Action {i} (create_event) missing 'start_datetime'")
                if 'end_datetime' not in action:
                    errors.append(f"Action {i} (create_event) missing 'end_datetime'")
            
            elif action_type in ['update_reminder', 'update_event', 'cancel_event']:
                if 'title' not in action and 'id' not in action:
                    errors.append(f"Action {i} ({action_type}) missing 'title' or 'id'")
        
        return errors

# =============================================================================
# AGENT STATE MANAGER
# =============================================================================

class AgentState:
    """Maintains the current state of tracked commitments."""
    
    def __init__(self):
        self.commitments: Dict[str, Commitment] = {}
        self._next_id = 1
    
    def _generate_id(self) -> str:
        """Generate a unique ID for a commitment."""
        id_str = f"commitment_{self._next_id}"
        self._next_id += 1
        return id_str
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for matching."""
        return title.lower().strip()
    
    def find_by_title(self, title: str) -> Optional[Commitment]:
        """Find a commitment by title (case-insensitive)."""
        normalized = self._normalize_title(title)
        for commitment in self.commitments.values():
            if self._normalize_title(commitment.title) == normalized:
                return commitment
        return None
    
    def apply_action(self, action: Dict[str, Any]) -> None:
        """Apply an action to update agent state."""
        action_type = action.get('action_type', '')
        
        if action_type == 'create_reminder':
            commitment_id = action.get('id', self._generate_id())
            self.commitments[commitment_id] = Commitment(
                id=commitment_id,
                commitment_type='reminder',
                title=action.get('title', ''),
                due_datetime=action.get('due_datetime'),
                notes=action.get('notes', ''),
                optional=action.get('optional', False)
            )
        
        elif action_type == 'create_event':
            commitment_id = action.get('id', self._generate_id())
            self.commitments[commitment_id] = Commitment(
                id=commitment_id,
                commitment_type='event',
                title=action.get('title', ''),
                start_datetime=action.get('start_datetime'),
                end_datetime=action.get('end_datetime'),
                attendees=action.get('attendees', []),
                notes=action.get('notes', '')
            )
        
        elif action_type == 'update_reminder':
            # Find by title or id
            commitment = None
            if 'id' in action:
                commitment = self.commitments.get(action['id'])
            elif 'title' in action:
                commitment = self.find_by_title(action['title'])
            
            if commitment:
                if 'due_datetime' in action:
                    commitment.due_datetime = action['due_datetime']
                if 'notes' in action:
                    commitment.notes = action['notes']
        
        elif action_type == 'update_event':
            commitment = None
            if 'id' in action:
                commitment = self.commitments.get(action['id'])
            elif 'title' in action:
                commitment = self.find_by_title(action['title'])
            
            if commitment:
                if 'start_datetime' in action:
                    commitment.start_datetime = action['start_datetime']
                if 'end_datetime' in action:
                    commitment.end_datetime = action['end_datetime']
                if 'attendees' in action:
                    commitment.attendees = action['attendees']
        
        elif action_type == 'cancel_event':
            commitment = None
            if 'id' in action:
                commitment = self.commitments.get(action['id'])
            elif 'title' in action:
                commitment = self.find_by_title(action['title'])
            
            if commitment:
                commitment.cancelled = True
    
    def get_active_commitments(self) -> List[Commitment]:
        """Get all non-cancelled commitments."""
        return [c for c in self.commitments.values() if not c.cancelled]

# =============================================================================
# VALIDATOR
# =============================================================================

class CommitmentValidator:
    """Validates agent behavior against expected outcomes."""
    
    @staticmethod
    def validate_turn(
        turn_spec: Dict[str, Any],
        agent_state: AgentState,
        actions: List[Dict[str, Any]],
        response_data: Optional[Dict[str, Any]]
    ) -> TurnResult:
        """
        Validate a single turn against expected outcomes.
        
        Args:
            turn_spec: The turn specification from COMMITMENT_FLOW
            agent_state: Current agent state after applying actions
            actions: List of actions taken by the agent
            response_data: Full parsed response data
            
        Returns:
            TurnResult with validation details
        """
        result = TurnResult(turn=turn_spec['turn'], parsed=True)
        expected = turn_spec.get('expected_actions', {})
        commitment_type = turn_spec.get('commitment_type', '')
        
        # Build expected description
        result.expected = f"{commitment_type}: {json.dumps(expected, indent=2)}"
        result.observed_actions = actions
        
        issues = []
        
        # Validate based on commitment type
        if commitment_type == 'explicit_reminder':
            issues.extend(CommitmentValidator._validate_reminder_creation(
                expected.get('reminder', {}), agent_state
            ))
        
        elif commitment_type == 'explicit_calendar':
            issues.extend(CommitmentValidator._validate_event_creation(
                expected.get('calendar', {}), agent_state
            ))
        
        elif commitment_type == 'implicit_reminder':
            issues.extend(CommitmentValidator._validate_reminder_creation(
                expected.get('reminder', {}), agent_state
            ))
        
        elif commitment_type == 'update_reminder':
            issues.extend(CommitmentValidator._validate_reminder_update(
                expected.get('reminder_update', {}), agent_state
            ))
        
        elif commitment_type == 'acknowledge_update':
            issues.extend(CommitmentValidator._validate_acknowledgment(
                actions, response_data
            ))
        
        elif commitment_type == 'reschedule_meeting':
            issues.extend(CommitmentValidator._validate_event_update(
                expected.get('calendar_update', {}), agent_state
            ))
        
        elif commitment_type == 'cancel_meeting':
            issues.extend(CommitmentValidator._validate_cancellation(
                expected.get('calendar_cancel', {}), agent_state
            ))
        
        elif commitment_type == 'summary_request':
            issues.extend(CommitmentValidator._validate_summary(
                expected.get('summary', {}), agent_state, response_data
            ))
        
        result.issues = issues
        result.passed = len(issues) == 0
        
        return result
    
    @staticmethod
    def _validate_reminder_creation(
        expected: Dict[str, Any],
        agent_state: AgentState
    ) -> List[str]:
        """Validate that a reminder was created correctly."""
        issues = []
        title = expected.get('title', '')
        
        commitment = agent_state.find_by_title(title)
        if not commitment:
            # Check if it's optional
            if not expected.get('optional', False):
                issues.append(f"Missing required reminder: '{title}'")
            return issues
        
        if commitment.commitment_type != 'reminder':
            issues.append(f"'{title}' should be a reminder, not {commitment.commitment_type}")
        
        # Validate due datetime
        expected_due = expected.get('due_datetime')
        if expected_due and commitment.due_datetime:
            if not CommitmentValidator._datetimes_match(expected_due, commitment.due_datetime):
                issues.append(
                    f"'{title}' due datetime mismatch: "
                    f"expected {expected_due}, got {commitment.due_datetime}"
                )
        
        # Validate keywords in description/notes
        keywords = expected.get('description_keywords', [])
        notes_lower = commitment.notes.lower()
        title_lower = commitment.title.lower()
        combined = notes_lower + " " + title_lower
        for keyword in keywords:
            if keyword.lower() not in combined:
                issues.append(f"'{title}' missing keyword '{keyword}' in title or notes")
        
        return issues
    
    @staticmethod
    def _validate_event_creation(
        expected: Dict[str, Any],
        agent_state: AgentState
    ) -> List[str]:
        """Validate that a calendar event was created correctly."""
        issues = []
        title = expected.get('title', '')
        
        commitment = agent_state.find_by_title(title)
        if not commitment:
            issues.append(f"Missing required event: '{title}'")
            return issues
        
        if commitment.commitment_type != 'event':
            issues.append(f"'{title}' should be an event, not {commitment.commitment_type}")
        
        # Validate start/end times
        expected_start = expected.get('start_datetime')
        expected_end = expected.get('end_datetime')
        
        if expected_start and commitment.start_datetime:
            if not CommitmentValidator._datetimes_match(expected_start, commitment.start_datetime):
                issues.append(
                    f"'{title}' start time mismatch: "
                    f"expected {expected_start}, got {commitment.start_datetime}"
                )
        
        if expected_end and commitment.end_datetime:
            if not CommitmentValidator._datetimes_match(expected_end, commitment.end_datetime):
                issues.append(
                    f"'{title}' end time mismatch: "
                    f"expected {expected_end}, got {commitment.end_datetime}"
                )
        
        # Validate attendees
        expected_attendees = expected.get('attendees', [])
        if expected_attendees:
            attendees_lower = [a.lower() for a in commitment.attendees]
            for exp_attendee in expected_attendees:
                if not any(exp_attendee.lower() in a for a in attendees_lower):
                    issues.append(f"'{title}' missing attendee containing '{exp_attendee}'")
        
        return issues
    
    @staticmethod
    def _validate_reminder_update(
        expected: Dict[str, Any],
        agent_state: AgentState
    ) -> List[str]:
        """Validate that a reminder was updated correctly."""
        issues = []
        original_title = expected.get('original_title', '')
        
        commitment = agent_state.find_by_title(original_title)
        if not commitment:
            issues.append(f"Reminder '{original_title}' not found for update")
            return issues
        
        # Validate new due datetime
        new_due = expected.get('new_due_datetime')
        if new_due and commitment.due_datetime:
            if not CommitmentValidator._datetimes_match(new_due, commitment.due_datetime):
                issues.append(
                    f"'{original_title}' update failed: "
                    f"expected {new_due}, got {commitment.due_datetime}"
                )
        
        return issues
    
    @staticmethod
    def _validate_event_update(
        expected: Dict[str, Any],
        agent_state: AgentState
    ) -> List[str]:
        """Validate that an event was updated correctly."""
        issues = []
        original_title = expected.get('original_title', '')
        
        commitment = agent_state.find_by_title(original_title)
        if not commitment:
            issues.append(f"Event '{original_title}' not found for update")
            return issues
        
        # Validate new start/end times
        new_start = expected.get('new_start_datetime')
        new_end = expected.get('new_end_datetime')
        
        if new_start and commitment.start_datetime:
            if not CommitmentValidator._datetimes_match(new_start, commitment.start_datetime):
                issues.append(
                    f"'{original_title}' start time update failed: "
                    f"expected {new_start}, got {commitment.start_datetime}"
                )
        
        if new_end and commitment.end_datetime:
            if not CommitmentValidator._datetimes_match(new_end, commitment.end_datetime):
                issues.append(
                    f"'{original_title}' end time update failed: "
                    f"expected {new_end}, got {commitment.end_datetime}"
                )
        
        return issues
    
    @staticmethod
    def _validate_cancellation(
        expected: Dict[str, Any],
        agent_state: AgentState
    ) -> List[str]:
        """Validate that an event was cancelled."""
        issues = []
        title = expected.get('title', '')
        
        commitment = agent_state.find_by_title(title)
        if not commitment:
            # Check if it was deleted entirely (also acceptable)
            return issues
        
        if not commitment.cancelled:
            issues.append(f"Event '{title}' should be cancelled but is still active")
        
        return issues
    
    @staticmethod
    def _validate_acknowledgment(
        actions: List[Dict[str, Any]],
        response_data: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Validate that the agent acknowledged an update."""
        issues = []
        
        # Check for confirm action
        has_confirm = any(a.get('action_type') == 'confirm' for a in actions)
        
        # Check for acknowledgment in natural language summary
        has_acknowledgment = False
        if response_data and 'natural_language_summary' in response_data:
            summary = response_data['natural_language_summary'].lower()
            ack_keywords = ['updated', 'changed', 'moved', 'rescheduled', 'confirmed']
            has_acknowledgment = any(kw in summary for kw in ack_keywords)
        
        if not has_confirm and not has_acknowledgment:
            issues.append("Agent did not acknowledge the update")
        
        return issues
    
    @staticmethod
    def _validate_summary(
        expected: Dict[str, Any],
        agent_state: AgentState,
        response_data: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Validate the summary of commitments."""
        issues = []
        
        should_include = expected.get('should_include', [])
        should_not_include = expected.get('should_not_include', [])
        
        # Build summary text from agent response
        summary_text = ""
        if response_data:
            if 'natural_language_summary' in response_data:
                summary_text += response_data['natural_language_summary']
            
            # Also check summary action
            for action in response_data.get('actions', []):
                if action.get('action_type') == 'summary':
                    summary_text += " " + action.get('notes', '')
        
        # Also include active commitment titles
        active = agent_state.get_active_commitments()
        for commitment in active:
            summary_text += " " + commitment.title
        
        summary_lower = summary_text.lower()
        
        # Check should_include
        for item in should_include:
            if item.lower() not in summary_lower:
                issues.append(f"Summary missing required item: '{item}'")
        
        # Check should_not_include
        for item in should_not_include:
            if item.lower() in summary_lower:
                issues.append(f"Summary incorrectly includes: '{item}'")
        
        return issues
    
    @staticmethod
    def _datetimes_match(expected: str, actual: str) -> bool:
        """
        Check if two datetime strings match (with some flexibility).
        
        Handles various formats and allows slight differences.
        """
        try:
            # Try parsing as datetime
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M",
            ]
            
            expected_dt = None
            actual_dt = None
            
            for fmt in formats:
                try:
                    expected_dt = datetime.strptime(expected, fmt)
                    break
                except ValueError:
                    continue
            
            for fmt in formats:
                try:
                    actual_dt = datetime.strptime(actual, fmt)
                    break
                except ValueError:
                    continue
            
            if expected_dt and actual_dt:
                # Allow up to 1 hour difference
                diff = abs((expected_dt - actual_dt).total_seconds())
                return diff <= 3600
            
            # Fallback to string comparison
            return expected.strip() == actual.strip()
        
        except Exception:
            return expected.strip() == actual.strip()

# =============================================================================
# SCORING SYSTEM
# =============================================================================

class Scorer:
    """Calculates weighted scores from validation results."""
    
    WEIGHTS = {
        'commitment_extraction': 0.30,
        'update_correctness': 0.25,
        'cancellation_handling': 0.15,
        'conditional_logic': 0.15,
        'summary_accuracy': 0.15,
    }
    
    @staticmethod
    def calculate_score(results: List[TurnResult]) -> Tuple[float, str]:
        """
        Calculate overall score from turn results.
        
        Returns:
            Tuple of (score 0-100, rationale string)
        """
        scores = {
            'commitment_extraction': 0.0,
            'update_correctness': 0.0,
            'cancellation_handling': 0.0,
            'conditional_logic': 0.0,
            'summary_accuracy': 0.0,
        }
        
        # Count turns by category
        extraction_turns = [1, 2, 3]  # Turns that create commitments
        update_turns = [4, 5, 6]      # Turns that update commitments
        cancel_turns = [7]             # Turns that cancel
        conditional_turns = [3]        # Conditional/optional commitments
        summary_turns = [8]            # Summary turn
        
        # Calculate extraction score
        extraction_results = [r for r in results if r.turn in extraction_turns]
        if extraction_results:
            passed = sum(1 for r in extraction_results if r.passed)
            scores['commitment_extraction'] = passed / len(extraction_results)
        
        # Calculate update score
        update_results = [r for r in results if r.turn in update_turns]
        if update_results:
            passed = sum(1 for r in update_results if r.passed)
            scores['update_correctness'] = passed / len(update_results)
        
        # Calculate cancellation score
        cancel_results = [r for r in results if r.turn in cancel_turns]
        if cancel_results:
            passed = sum(1 for r in cancel_results if r.passed)
            scores['cancellation_handling'] = passed / len(cancel_results)
        
        # Calculate conditional logic score
        conditional_results = [r for r in results if r.turn in conditional_turns]
        if conditional_results:
            passed = sum(1 for r in conditional_results if r.passed)
            scores['conditional_logic'] = passed / len(conditional_results)
        
        # Calculate summary score
        summary_results = [r for r in results if r.turn in summary_turns]
        if summary_results:
            passed = sum(1 for r in summary_results if r.passed)
            scores['summary_accuracy'] = passed / len(summary_results)
        
        # Calculate weighted total
        total_score = sum(
            scores[category] * Scorer.WEIGHTS[category]
            for category in scores
        ) * 100
        
        # Build rationale
        rationale_parts = []
        for category, weight in Scorer.WEIGHTS.items():
            score_pct = scores[category] * 100
            rationale_parts.append(
                f"{category.replace('_', ' ').title()}: "
                f"{score_pct:.0f}% (weight: {weight*100:.0f}%)"
            )
        
        rationale = "\n  ".join(rationale_parts)
        
        return total_score, rationale

# =============================================================================
# COMMITMENT HARNESS
# =============================================================================

class CommitmentHarness:
    """Main evaluation harness."""
    
    SYSTEM_MESSAGE = """You are a helpful AI assistant that tracks commitments, reminders, and calendar events for users.

When the user tells you about a commitment, task, or event, you must respond with a JSON object on the FIRST LINE of your response following this schema:

{
  "actions": [
    {
      "action_type": "create_reminder" | "create_event" | "update_reminder" | "update_event" | "cancel_event" | "confirm" | "summary",
      "id": "<optional unique identifier>",
      "title": "<commitment title>",
      "due_datetime": "<YYYY-MM-DD HH:MM:SS for reminders>",
      "start_datetime": "<YYYY-MM-DD HH:MM:SS for events>",
      "end_datetime": "<YYYY-MM-DD HH:MM:SS for events>",
      "attendees": ["<list of attendees for events>"],
      "notes": "<additional details>",
      "optional": <true if this is a soft/conditional commitment>
    }
  ],
  "natural_language_summary": "<optional human-readable summary>"
}

Rules:
- The FIRST LINE of your response must be valid JSON
- For create_reminder: include title and due_datetime
- For create_event: include title, start_datetime, end_datetime
- For updates/cancellations: include title or id to identify the item
- You may include additional explanation after a blank line

Current date/time context: Friday, March 6, 2026, 09:00 UTC"""
    
    def __init__(self, agent: AgentInterface):
        self.agent = agent
        self.parser = ResponseParser()
        self.validator = CommitmentValidator()
    
    def _build_prompt(self, turn_spec: Dict[str, Any]) -> str:
        """Build the full prompt for a turn."""
        prompt_parts = [self.SYSTEM_MESSAGE, "\n\n"]
        
        if 'user_message' in turn_spec:
            prompt_parts.append(f"User: {turn_spec['user_message']}")
        elif 'email' in turn_spec:
            email = turn_spec['email']
            prompt_parts.append(
                f"[New email received]\n"
                f"From: {email['sender']}\n"
                f"Subject: {email['subject']}\n"
                f"{email['content']}\n\n"
                f"User: I just received this email. Please update my commitments accordingly."
            )
        
        return "".join(prompt_parts)
    
    def run_evaluation(self) -> Tuple[List[TurnResult], float, str]:
        """
        Run the full evaluation scenario.
        
        Returns:
            Tuple of (turn_results, final_score, rationale)
        """
        agent_state = AgentState()
        turn_results = []
        
        for turn_spec in COMMITMENT_FLOW:
            # Build and send prompt
            prompt = self._build_prompt(turn_spec)
            response = self.agent.call_agent(prompt)
            
            # Parse response
            parsed_data, parse_error = self.parser.parse_response(response)
            
            # Create turn result
            result = TurnResult(turn=turn_spec['turn'], parsed=parsed_data is not None)
            
            if parse_error:
                result.parsing_error = parse_error
            
            if parsed_data:
                # Validate schema
                schema_errors = self.parser.validate_schema(parsed_data)
                if schema_errors:
                    result.issues.extend(schema_errors)
                
                # Apply actions to state
                actions = parsed_data.get('actions', [])
                for action in actions:
                    try:
                        agent_state.apply_action(action)
                    except Exception as e:
                        result.issues.append(f"Error applying action: {e}")
                
                # Validate against expectations
                validation_result = self.validator.validate_turn(
                    turn_spec, agent_state, actions, parsed_data
                )
                
                result.expected = validation_result.expected
                result.observed_actions = validation_result.observed_actions
                result.issues.extend(validation_result.issues)
                result.passed = len(result.issues) == 0
            else:
                result.passed = False
                result.issues.append("Failed to parse response")
            
            turn_results.append(result)
        
        # Calculate final score
        final_score, rationale = Scorer.calculate_score(turn_results)
        
        return turn_results, final_score, rationale

# =============================================================================
# SIMULATED AGENT (For Demo)
# =============================================================================

class SimulatedAgent(AgentInterface):
    """
    Simulated agent that returns pre-defined responses.
    
    This demonstrates the harness functionality without requiring a real LLM.
    """
    
    RESPONSES = [
        # Turn 1: Create budget reminder
        """{
  "actions": [
    {
      "action_type": "create_reminder",
      "id": "reminder_1",
      "title": "Send Q1 budget analysis to Sarah",
      "due_datetime": "2026-03-06 23:59:00",
      "notes": "Q1 budget analysis for Sarah"
    }
  ],
  "natural_language_summary": "I've set a reminder to send the Q1 budget analysis to Sarah by end of day Friday."
}""",
        # Turn 2: Create standup event
        """{
  "actions": [
    {
      "action_type": "create_event",
      "id": "event_1",
      "title": "Team Standup",
      "start_datetime": "2026-03-09 10:00:00",
      "end_datetime": "2026-03-09 10:30:00",
      "attendees": ["engineering team"],
      "notes": "Weekly team standup meeting"
    }
  ],
  "natural_language_summary": "I've scheduled a 30-minute Team Standup for Monday at 10am UTC with the engineering team."
}""",
        # Turn 3: Create optional design docs reminder
        """{
  "actions": [
    {
      "action_type": "create_reminder",
      "id": "reminder_2",
      "title": "Review design docs",
      "due_datetime": "2026-03-08 17:00:00",
      "notes": "Optional: review design docs over the weekend",
      "optional": true
    }
  ],
  "natural_language_summary": "I've added an optional reminder to review design docs over the weekend."
}""",
        # Turn 4: Email about budget deadline change (auto-update)
        """{
  "actions": [
    {
      "action_type": "update_reminder",
      "title": "Send Q1 budget analysis to Sarah",
      "due_datetime": "2026-03-05 17:00:00",
      "notes": "Deadline moved to Thursday afternoon per Sarah's email"
    }
  ],
  "natural_language_summary": "I've updated the budget analysis deadline to Thursday afternoon based on Sarah's email."
}""",
        # Turn 5: Acknowledge the update
        """{
  "actions": [
    {
      "action_type": "confirm"
    }
  ],
  "natural_language_summary": "Yes, I've already updated that commitment. The budget analysis is now due Thursday afternoon instead of Friday."
}""",
        # Turn 6: Reschedule standup
        """{
  "actions": [
    {
      "action_type": "update_event",
      "title": "Team Standup",
      "start_datetime": "2026-03-09 14:00:00",
      "end_datetime": "2026-03-09 14:30:00",
      "notes": "Rescheduled to 2pm UTC for west coast availability"
    }
  ],
  "natural_language_summary": "I've rescheduled the Team Standup to 2pm UTC on Monday."
}""",
        # Turn 7: Cancel standup via email
        """{
  "actions": [
    {
      "action_type": "cancel_event",
      "title": "Team Standup"
    }
  ],
  "natural_language_summary": "I've cancelled Monday's Team Standup per your manager's email."
}""",
        # Turn 8: Summary
        """{
  "actions": [
    {
      "action_type": "summary",
      "notes": "Current commitments: (1) Send Q1 budget analysis to Sarah by Thursday afternoon, March 5th. (2) Review design docs over the weekend (optional)."
    }
  ],
  "natural_language_summary": "You have 2 active commitments: the Q1 budget analysis due Thursday and the optional design docs review. The Team Standup has been cancelled."
}""",
    ]
    
    def __init__(self):
        self.call_count = 0
    
    def call_agent(self, prompt: str) -> str:
        if self.call_count >= len(self.RESPONSES):
            return '{"actions": [], "natural_language_summary": "No more turns."}'
        
        response = self.RESPONSES[self.call_count]
        self.call_count += 1
        return response

# =============================================================================
# REPORTING
# =============================================================================

def print_report(results: List[TurnResult], final_score: float, rationale: str):
    """Print a human-readable evaluation report."""
    
    print("=" * 80)
    print("COMMITMENT TRACKING EVALUATION REPORT")
    print("=" * 80)
    print()
    
    # Per-turn results
    for result in results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"Turn {result.turn}: {status}")
        print(f"  Parsed: {result.parsed}")
        
        if result.parsing_error:
            print(f"  Parsing: {result.parsing_error}")
        
        if result.observed_actions:
            print(f"  Actions: {len(result.observed_actions)} action(s) taken")
            for action in result.observed_actions:
                print(f"    - {action.get('action_type', 'unknown')}: {action.get('title', 'N/A')}")
        
        if result.issues:
            print(f"  Issues:")
            for issue in result.issues:
                print(f"    • {issue}")
        
        print()
    
    # Summary statistics
    total_turns = len(results)
    passed_turns = sum(1 for r in results if r.passed)
    failed_turns = total_turns - passed_turns
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Turns: {total_turns}")
    print(f"Passed: {passed_turns}")
    print(f"Failed: {failed_turns}")
    print()
    print(f"FINAL SCORE: {final_score:.1f}/100")
    print()
    print("Score Breakdown:")
    print(f"  {rationale}")
    print()
    
    if final_score >= 90:
        grade = "Excellent"
    elif final_score >= 75:
        grade = "Good"
    elif final_score >= 60:
        grade = "Acceptable"
    else:
        grade = "Needs Improvement"
    
    print(f"Grade: {grade}")
    print("=" * 80)

# =============================================================================
# MAIN CLI
# =============================================================================
def main():
    agent = SimulatedAgent()
    harness = CommitmentHarness(agent)
    
    results, final_score, rationale = harness.run_evaluation()
    
    print_report(results, final_score, rationale)