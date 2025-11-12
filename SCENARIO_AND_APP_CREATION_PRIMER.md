# Meta Agents Research Environments: Scenario and App Creation Primer

## Table of Contents
1. [Overview](#overview)
2. [Understanding Scenarios](#understanding-scenarios)
3. [Creating a Scenario: Step-by-Step Guide](#creating-a-scenario-step-by-step-guide)
4. [Understanding Apps](#understanding-apps)
5. [Creating Custom Apps](#creating-custom-apps)
6. [How Apps Interact with Scenarios](#how-apps-interact-with-scenarios)
7. [Events and Event Flow](#events-and-event-flow)
8. [Validation](#validation)
9. [Complete Examples](#complete-examples)
10. [Best Practices and Common Patterns](#best-practices-and-common-patterns)

---

## Overview

**Meta Agents Research Environments (ARE)** is a simulation framework for testing AI agents in realistic, dynamic environments. The framework consists of:

- **Scenarios**: Complete task definitions that agents must complete, including initial state, dynamic events, and validation logic
- **Apps**: Building blocks that provide specific functionality (like email, calendar, file system) that agents can interact with
- **Events**: Time-based occurrences that drive the scenario forward
- **Environment**: The orchestration layer that manages apps, events, and agent interactions

This primer provides everything you need to create custom scenarios and apps without additional context.

---

## Understanding Scenarios

### What is a Scenario?

A scenario in ARE is a complete simulation setup that includes:

1. **Initial Environment State**: The starting configuration of all apps and data
2. **Available Applications**: Which tools the agent can use (email, calendar, contacts, etc.)
3. **Dynamic Events**: Things that happen during execution (incoming messages, emails, user requests)
4. **Task Definition**: What the agent needs to accomplish
5. **Validation Logic**: How success is measured

### Scenario vs Universe

- **Universe**: A static initial state with baseline data and environmental setup
- **Scenario**: A dynamic simulation that evolves over time from a universe's state at t=0

A universe is optional - scenarios can start from an empty environment.

### Key Scenario Components

```python
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario

@register_scenario("my_scenario_id")  # Unique identifier for registration
class MyScenario(Scenario):
    # Timing configuration
    start_time: float | None = 0              # When the scenario starts (timestamp or 0)
    duration: float | None = 600              # Duration in seconds
    
    # Required methods to implement:
    def init_and_populate_apps(self, *args, **kwargs) -> None:
        """Initialize apps and populate with initial data"""
        pass
    
    def build_events_flow(self) -> None:
        """Define the sequence of events that occur during the scenario"""
        pass
    
    def validate(self, env) -> ScenarioValidationResult:
        """Check if the agent successfully completed the task"""
        pass
```

---

## Creating a Scenario: Step-by-Step Guide

### Step 1: Define the Scenario Class

```python
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.apps.contacts import Contact, ContactsApp, Gender, Status
from are.simulation.types import EventRegisterer, EventType, Action

@register_scenario("email_task_scenario")
class EmailTaskScenario(Scenario):
    """
    A scenario where the agent must read an incoming email and respond appropriately.
    """
    # Define scenario timing
    start_time: float | None = 0
    duration: float | None = 300  # 5 minutes
```

### Step 2: Initialize and Populate Apps

The `init_and_populate_apps` method sets up the initial state of your scenario:

```python
def init_and_populate_apps(self, *args, **kwargs) -> None:
    """
    Initialize applications and populate them with starting data.
    This defines the "universe" or initial state of the scenario.
    """
    # Step 1: Create app instances
    agui = AgentUserInterface()  # Required for agent-user communication
    email_app = EmailClientApp()
    contacts_app = ContactsApp()
    
    # Step 2: Populate apps with initial data
    # Add contacts that will be referenced in the scenario
    contacts_app.add_contact(
        Contact(
            first_name="Alice",
            last_name="Johnson",
            email="alice.johnson@company.com",
            phone="+1-555-0123",
            gender=Gender.FEMALE,
            status=Status.EMPLOYED,
            age=30,
        )
    )
    
    contacts_app.add_contact(
        Contact(
            first_name="Bob",
            last_name="Smith",
            email="bob.smith@company.com",
            phone="+1-555-0456",
            gender=Gender.MALE,
            status=Status.EMPLOYED,
            age=45,
        )
    )
    
    # Add an initial email in the inbox
    email_app.add_email(
        Email(
            sender="alice.johnson@company.com",
            recipients=[email_app.user_email],
            subject="Project Status Update",
            content="Hi, I need the quarterly report by end of day. Can you send it to Bob?",
            email_id="initial_email_1",
        )
    )
    
    # Step 3: Store apps in the scenario
    # Order doesn't matter, but AgentUserInterface should always be included
    self.apps = [agui, email_app, contacts_app]
```

**Key Points:**
- **AgentUserInterface** is required for agent-user communication
- Apps can be populated with initial data to create a realistic starting state
- Use unique IDs for items that will be referenced later (like `email_id`)
- Store the `self.apps` list - this is how the environment knows what apps to register

### Step 3: Build Events Flow

The `build_events_flow` method defines the dynamic events that occur during the scenario:

```python
def build_events_flow(self) -> None:
    """
    Define the sequence of events that happen during scenario execution.
    Events are chained using dependencies to create a timeline.
    """
    # Get typed references to your apps
    agui = self.get_typed_app(AgentUserInterface)
    email_app = self.get_typed_app(EmailClientApp)
    
    # Use capture_mode to create events from app method calls
    # In capture mode, methods return Event objects instead of executing
    with EventRegisterer.capture_mode():
        # EVENT 1: User gives the agent a task
        # depends_on(None, ...) means this is the first event
        event1 = agui.send_message_to_agent(
            content="Please check my emails and handle any urgent requests."
        ).depends_on(None, delay_seconds=5)
        
        # EVENT 2: An email arrives while agent is working
        # depends_on(event1, ...) means this happens after event1
        event2 = email_app.send_email_to_user(
            email=Email(
                sender="bob.smith@company.com",
                recipients=[email_app.user_email],
                subject="Re: Quarterly Report",
                content="I'm ready to receive the report whenever you can send it.",
                email_id="followup_email",
            )
        ).depends_on(event1, delay_seconds=10)
        
        # ORACLE EVENT: Expected agent action
        # Oracle events represent what the agent SHOULD do
        # They're used for validation and training
        oracle1 = (
            email_app.send_email(
                recipients=["bob.smith@company.com"],
                subject="Quarterly Report",
                content="Hi Bob, please find the quarterly report attached.",
            )
            .oracle()  # Mark as oracle event
            .depends_on(event2, delay_seconds=5)
        )
        
        # ORACLE EVENT 2: Agent should inform the user
        oracle2 = (
            agui.send_message_to_user(
                content="I've sent the quarterly report to Bob as requested."
            )
            .oracle()
            .depends_on(oracle1, delay_seconds=2)
        )
    
    # Store the events in the scenario
    self.events = [event1, event2, oracle1, oracle2]
```

**Event Types:**

1. **USER Events** (`EventType.USER`): Actions initiated by the user
2. **ENV Events** (`EventType.ENV`): Events from the environment (incoming emails, messages, etc.)
3. **AGENT Events** (`EventType.AGENT`): Actions the agent takes (oracle events that show expected behavior)
4. **CONDITION Events** (`EventType.CONDITION`): Events triggered by conditions

**Event Dependencies:**

```python
# Start immediately at scenario start
event.depends_on(None, delay_seconds=0)

# Start 5 seconds after the scenario begins
event.depends_on(None, delay_seconds=5)

# Start 10 seconds after event1 completes
event.depends_on(event1, delay_seconds=10)

# Start after both event1 AND event2 complete
event.depends_on([event1, event2], delay_seconds=5)
```

**Capture Mode:**

`EventRegisterer.capture_mode()` is a context manager that:
- Prevents actual execution of app methods
- Returns Event objects instead
- Makes it easy to create events using natural app API calls
- Events created in capture mode default to `EventType.ENV` but can be changed with `.with_type()`

**Oracle Events:**

Oracle events represent the "correct" or "expected" agent behavior:
- Created by calling `.oracle()` on an event
- Used during oracle mode execution to show the agent what it should do
- Used in validation to check if the agent performed the correct actions
- Always have `event_type=EventType.AGENT`

### Step 4: Implement Validation

The `validate` method checks whether the agent successfully completed the task:

```python
def validate(self, env) -> ScenarioValidationResult:
    """
    Validate that the agent completed the scenario successfully.
    
    Args:
        env: The environment containing all apps and event logs
        
    Returns:
        ScenarioValidationResult with success status
    """
    try:
        # Method 1: Check the event log for specific actions
        email_sent = any(
            event.event_type == EventType.AGENT
            and isinstance(event.action, Action)
            and event.action.function_name == "send_email"
            and event.action.class_name == "EmailClientApp"
            and "bob.smith@company.com" in event.action.args.get("recipients", [])
            for event in env.event_log.list_view()
        )
        
        # Method 2: Check app state directly
        email_app = env.get_app("EmailClientApp")
        sent_folder = email_app.folders["sent"]
        
        report_sent = any(
            "quarterly report" in email.subject.lower()
            and "bob.smith@company.com" in email.recipients
            for email in sent_folder.emails
        )
        
        # Combine multiple validation criteria
        success = email_sent and report_sent
        
        # Optional: Provide detailed feedback
        rationale = ""
        if not email_sent:
            rationale += "Agent did not send email to Bob. "
        if not report_sent:
            rationale += "Report was not found in sent folder. "
        
        return ScenarioValidationResult(
            success=success,
            rationale=rationale if not success else "Task completed successfully"
        )
        
    except Exception as e:
        # Always wrap validation in try-catch
        return ScenarioValidationResult(success=False, exception=e)
```

**Validation Patterns:**

1. **Event Log Validation**: Check that specific actions were performed
   ```python
   action_performed = any(
       event.event_type == EventType.AGENT
       and event.action.function_name == "target_function"
       and event.action.class_name == "TargetApp"
       for event in env.event_log.list_view()
   )
   ```

2. **App State Validation**: Check the final state of apps
   ```python
   app = env.get_app("AppName")
   # Check app properties directly
   success = len(app.items) > 0
   ```

3. **Multi-Criteria Validation**: Combine multiple checks
   ```python
   criteria = [
       check_email_sent(),
       check_calendar_updated(),
       check_user_notified()
   ]
   success = all(criteria)
   ```

### Step 5: Register and Run the Scenario

The `@register_scenario` decorator automatically registers your scenario:

```python
@register_scenario("email_task_scenario")
class EmailTaskScenario(Scenario):
    # ... implementation ...
```

**Testing Your Scenario:**

```python
if __name__ == "__main__":
    from are.simulation.scenarios.utils.cli_utils import run_and_validate
    
    # Run the scenario in oracle mode (executes oracle events)
    # and validates the results
    run_and_validate(EmailTaskScenario())
```

**Running with an Agent:**

```bash
# Run scenario with default agent
uv run are-run -s email_task_scenario -a default

# Run with specific model
uv run are-run -s email_task_scenario -a responses --model gpt-5-mini --provider openai
```

---

## Understanding Apps

### What is an App?

An **App** in ARE represents a distinct application or service that agents can interact with. Apps:

- Encapsulate related functionality (e.g., all email operations in EmailClientApp)
- Maintain internal state that evolves during simulation
- Expose tools that agents can call
- Can interact with other apps through protocols
- Support state serialization for reproducibility

### App Architecture

```
App (Base Class)
├── State Management
│   ├── get_state() - Serialize current state
│   ├── load_state() - Restore from serialized state
│   └── reset() - Reset to initial state
├── Tool Registration
│   ├── @app_tool - Tools available to agents
│   ├── @user_tool - Tools for user interactions
│   ├── @env_tool - Tools for environment events
│   └── @data_tool - Tools for data operations
├── Protocol Support
│   ├── get_implemented_protocols() - Declare protocols
│   └── connect_to_protocols() - Connect to other apps
└── Event Integration
    └── @event_registered - Register events for actions
```

### Built-in Apps

ARE includes several pre-built apps:

**Communication Apps:**
- `AgentUserInterface` - Agent-user communication (required in all scenarios)
- `EmailClientApp` - Email management
- `MessagingApp` - Text messaging/chat
- `MessagingAppV2` - Enhanced messaging with additional features

**Data Apps:**
- `ContactsApp` - Contact management
- `CalendarApp` - Calendar and event scheduling

**System Apps:**
- `SandboxLocalFileSystem` - Sandboxed file system operations
- `VirtualFileSystem` - Virtual file system (no actual disk I/O)
- `SystemApp` - System information and operations

**Utility Apps:**
- `ShoppingApp` - E-commerce operations
- `CabApp` - Ride-hailing services
- `ApartmentListingApp` - Real estate listings
- `CityApp` - City information and data

---

## Creating Custom Apps

### Step 1: Define Data Models

Start by defining the data structures your app will use:

```python
from dataclasses import dataclass, field
from enum import Enum
import uuid

class Priority(Enum):
    """Priority levels for tasks"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"

@dataclass
class Task:
    """
    A task in the task management system.
    
    Demonstrates key patterns:
    - Required and optional fields
    - Default value generation (UUID)
    - Enum usage for constrained values
    - Validation in __post_init__
    """
    title: str
    description: str = ""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    priority: Priority = Priority.MEDIUM
    completed: bool = False
    
    def __post_init__(self):
        """Validate data after initialization"""
        if not self.title or len(self.title.strip()) == 0:
            raise ValueError("Task title cannot be empty")
        
        # Handle string-to-enum conversion
        if isinstance(self.priority, str):
            try:
                self.priority = Priority(self.priority)
            except ValueError:
                raise ValueError(f"Invalid priority: {self.priority}")
    
    def __str__(self):
        """String representation for debugging"""
        status = "✓" if self.completed else "○"
        return f"{status} [{self.priority.value}] {self.title}"
```

### Step 2: Create the App Class

```python
from dataclasses import dataclass, field
from typing import Any
from are.simulation.apps.app import App
from are.simulation.tool_utils import app_tool, data_tool, OperationType
from are.simulation.types import event_registered
from are.simulation.utils import get_state_dict, type_check

@dataclass
class TaskManagerApp(App):
    """
    A task management app demonstrating core app patterns.
    
    Key Features:
    - Data storage and management
    - Tool method registration with decorators
    - State persistence and loading
    - Type checking and validation
    - Event registration for environment integration
    """
    
    # App configuration
    name: str | None = "TaskManagerApp"
    tasks: dict[str, Task] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize the app - ALWAYS call super().__init__()"""
        super().__init__(self.name)
```

### Step 3: Implement State Management

State management is crucial for scenario reproducibility:

```python
def get_state(self) -> dict[str, Any]:
    """
    Return the app's current state for persistence.
    Use get_state_dict utility for consistent serialization.
    """
    return get_state_dict(self, ["tasks"])

def load_state(self, state_dict: dict[str, Any]):
    """
    Restore app state from saved data.
    Handle data conversion and validation carefully.
    """
    self.tasks = {}
    tasks_data = state_dict.get("tasks", {})
    
    for task_id, task_data in tasks_data.items():
        # Reconstruct Task objects from saved data
        task = Task(
            title=task_data["title"],
            description=task_data.get("description", ""),
            task_id=task_data.get("task_id", task_id),
            priority=Priority(task_data.get("priority", "Medium")),
            completed=task_data.get("completed", False),
        )
        self.tasks[task_id] = task

def reset(self):
    """Reset app to initial state - important for scenario repeatability"""
    super().reset()
    self.tasks = {}
```

### Step 4: Implement Tool Methods

Tool methods are the primary interface between agents and your app:

```python
@type_check  # Validates parameter types at runtime
@app_tool()  # Registers method as an agent-accessible tool
@data_tool()  # Marks as a data access tool (for analytics)
@event_registered()  # Registers events for environment tracking
def create_task(
    self, 
    title: str, 
    description: str = "", 
    priority: str = "Medium"
) -> str:
    """
    Create a new task in the task management system.
    
    The docstring is critical - it's shown to the agent as tool documentation.
    Be clear, specific, and include all parameter and return information.
    
    :param title: The title of the task (required)
    :param description: Optional description of the task
    :param priority: Priority level (Low, Medium, High, Urgent)
    :returns: The unique task_id of the created task
    """
    # Create and validate the task
    task = Task(title=title, description=description, priority=Priority(priority))
    
    # Store the task
    self.tasks[task.task_id] = task
    
    return task.task_id

@type_check
@app_tool()
@data_tool()
@event_registered(operation_type=OperationType.READ)  # Mark as read operation
def get_tasks(self, completed_only: bool = False) -> list[dict[str, Any]]:
    """
    Retrieve all tasks, optionally filtered by completion status.
    
    :param completed_only: If True, return only completed tasks
    :returns: List of task dictionaries with all task information
    """
    tasks = list(self.tasks.values())
    
    if completed_only:
        tasks = [task for task in tasks if task.completed]
    
    # Return serializable data (not objects)
    return [
        {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority.value,
            "completed": task.completed,
        }
        for task in tasks
    ]

@type_check
@app_tool()
@data_tool()
@event_registered(operation_type=OperationType.WRITE)  # Mark as write operation
def complete_task(self, task_id: str) -> str:
    """
    Mark a task as completed.
    
    :param task_id: The unique identifier of the task to complete
    :returns: Success message
    """
    if task_id not in self.tasks:
        raise KeyError(f"Task {task_id} does not exist")
    
    self.tasks[task_id].completed = True
    return f"Task {task_id} marked as completed"

@type_check
@app_tool()
@data_tool()
@event_registered(operation_type=OperationType.WRITE)
def update_task(
    self,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
) -> str:
    """
    Update an existing task's properties.
    
    :param task_id: The unique identifier of the task to update
    :param title: New title for the task (optional)
    :param description: New description for the task (optional)
    :param priority: New priority level (optional)
    :returns: Success message
    """
    if task_id not in self.tasks:
        raise KeyError(f"Task {task_id} does not exist")
    
    task = self.tasks[task_id]
    
    # Update only provided fields
    if title is not None:
        if not title.strip():
            raise ValueError("Task title cannot be empty")
        task.title = title
    
    if description is not None:
        task.description = description
    
    if priority is not None:
        task.priority = Priority(priority)
    
    return f"Task {task_id} updated successfully"
```

**Tool Decorators Explained:**

1. **`@type_check`**: Validates parameter types at runtime
   - Should be the outermost decorator
   - Prevents type errors from reaching your code

2. **`@app_tool()`**: Registers the method as a tool for agents
   - Makes the method callable by agents
   - Generates tool schema from signature and docstring

3. **`@user_tool()`**: Registers as a user tool (for user interactions)

4. **`@env_tool()`**: Registers as an environment tool (for scenario events)

5. **`@data_tool()`**: Registers as a data tool (for population/analytics)

6. **`@event_registered(operation_type=...)`**: Registers events when the tool is called
   - `OperationType.READ`: Reading/querying data
   - `OperationType.WRITE`: Modifying data
   - `OperationType.DELETE`: Deleting data
   - `OperationType.CREATE`: Creating new data

**Docstring Requirements:**

- Must be clear and detailed - agents read this to understand how to use tools
- Use `:param name: description` format for parameters
- Use `:returns: description` format for return values
- Include all possible parameter values if constrained (e.g., enum values)
- Explain any side effects or state changes

### Step 5: (Optional) Implement Protocols

Apps can implement protocols to allow inter-app communication:

```python
from are.simulation.apps.app import Protocol

class FileSystemApp(App):
    def get_implemented_protocols(self) -> list[Protocol]:
        """Declare which protocols this app implements"""
        return [Protocol.FILE_SYSTEM]
    
    @app_tool()
    def read_file(self, path: str) -> str:
        """Read a file from the file system"""
        # Implementation
        pass

class DocumentApp(App):
    def connect_to_protocols(self, protocols: dict[Protocol, Any]) -> None:
        """Connect to other apps via protocols"""
        if Protocol.FILE_SYSTEM in protocols:
            self.file_system = protocols[Protocol.FILE_SYSTEM]
    
    @app_tool()
    def open_document(self, path: str) -> str:
        """Open a document using the file system"""
        content = self.file_system.read_file(path)
        return f"Opened document: {content}"
```

---

## How Apps Interact with Scenarios

### App Initialization in Scenarios

When creating a scenario, apps are initialized in `init_and_populate_apps`:

```python
def init_and_populate_apps(self, *args, **kwargs) -> None:
    # Create app instances
    task_app = TaskManagerApp()
    email_app = EmailClientApp()
    
    # Populate with initial data
    task_app.create_task(
        title="Review quarterly reports",
        description="Analyze Q3 financial performance",
        priority="High"
    )
    
    # Store for scenario use
    self.apps = [task_app, email_app]
```

### Accessing Apps in Events

In `build_events_flow`, use `get_typed_app` to access apps:

```python
def build_events_flow(self) -> None:
    # Get typed references (provides IDE autocomplete and type checking)
    task_app = self.get_typed_app(TaskManagerApp)
    email_app = self.get_typed_app(EmailClientApp)
    
    with EventRegisterer.capture_mode():
        # Create events using app methods
        event1 = task_app.create_task(
            title="New task",
            priority="High"
        ).depends_on(None, delay_seconds=5)
```

### Accessing Apps in Validation

In `validate`, use `env.get_app` to access apps:

```python
def validate(self, env) -> ScenarioValidationResult:
    try:
        # Access by app name (string)
        task_app = env.get_app("TaskManagerApp")
        
        # Check app state
        tasks = list(task_app.tasks.values())
        success = len(tasks) > 0
        
        return ScenarioValidationResult(success=success)
    except Exception as e:
        return ScenarioValidationResult(success=False, exception=e)
```

### App State Lifecycle

```
1. Initialization (init_and_populate_apps)
   ↓
2. State Snapshot (automatic - preserves initial state)
   ↓
3. Event Execution (build_events_flow)
   ↓
4. Agent Interactions (agent calls app tools)
   ↓
5. Validation (check final state)
   ↓
6. Reset (can restore to initial state for re-runs)
```

---

## Events and Event Flow

### Event Types

```python
from are.simulation.types import EventType

# User-initiated events (user asks agent to do something)
EventType.USER

# Environment events (external occurrences like incoming messages)
EventType.ENV

# Agent actions (what the agent does)
EventType.AGENT

# Condition-based events (triggered when conditions are met)
EventType.CONDITION
```

### Creating Events

**Method 1: Using Capture Mode (Recommended)**

```python
with EventRegisterer.capture_mode():
    # Method calls return Event objects instead of executing
    event = app.some_method(param="value")
    
    # Chain dependencies
    event.depends_on(None, delay_seconds=5)
    
    # Change event type (defaults to ENV in capture mode)
    event.with_type(EventType.USER)
    
    # Mark as oracle event
    oracle_event = app.expected_action().oracle().depends_on(event, delay_seconds=2)
```

**Method 2: Direct Event Creation**

```python
from are.simulation.types import Event

# Create event from function
event = Event.from_function(
    function=app.some_method,
    event_type=EventType.ENV,
    param="value"
)

# Set timing
event.at_absolute_time(100)  # Execute at time 100
# OR
event.depends_on(other_event, delay_seconds=5)
```

### Event Dependencies (DAG)

Events form a Directed Acyclic Graph (DAG) where edges represent dependencies:

```python
# Simple chain: e1 → e2 → e3
e1.depends_on(None, delay_seconds=0)  # Starts immediately
e2.depends_on(e1, delay_seconds=5)    # 5 seconds after e1
e3.depends_on(e2, delay_seconds=10)   # 10 seconds after e2

# Multiple dependencies: e1 and e2 → e3
e3.depends_on([e1, e2], delay_seconds=5)  # Waits for BOTH e1 and e2

# Branching: e1 → e2 and e1 → e3 (parallel)
e2.depends_on(e1, delay_seconds=5)
e3.depends_on(e1, delay_seconds=5)  # e2 and e3 happen in parallel

# Complex DAG:
#     e1
#    /  \
#   e2  e3
#    \  /
#     e4
e2.depends_on(e1, delay_seconds=5)
e3.depends_on(e1, delay_seconds=5)
e4.depends_on([e2, e3], delay_seconds=2)
```

### Event Timing

```python
# Relative time (relative to dependencies)
event.depends_on(prev_event, delay_seconds=10)

# Absolute time (specific timestamp)
event.at_absolute_time(start_time + 100)

# Immediate execution after dependency
event.depends_on(prev_event, delay_seconds=0)

# Start at scenario start
event.depends_on(None, delay_seconds=0)
```

### Oracle Events

Oracle events represent the expected/correct agent behavior:

```python
with EventRegisterer.capture_mode():
    # Environment event (something happens)
    env_event = email_app.send_email_to_user(
        email=Email(...)
    ).depends_on(None, delay_seconds=5)
    
    # Oracle event (what agent should do in response)
    oracle_event = (
        email_app.reply_to_email(
            email_id="...",
            content="Thank you for the information."
        )
        .oracle()  # Mark as oracle event
        .depends_on(env_event, delay_seconds=5)
    )
```

**Oracle Event Uses:**
1. **Oracle Mode Execution**: System executes oracle events to show correct behavior
2. **Training**: Can be used to train agents on correct actions
3. **Validation**: Compare agent actions against oracle events
4. **Debugging**: See what the scenario designer expected to happen

### Conditional Events

Events that trigger when specific conditions are met:

```python
from are.simulation.types import ConditionCheckEvent

# Define a condition function
def condition(env: AbstractEnvironment) -> bool:
    email_app = env.get_app("EmailClientApp")
    inbox = email_app.folders["inbox"]
    return len(inbox.emails) > 5  # True when inbox has more than 5 emails

# Create condition check event
condition_check = ConditionCheckEvent.from_condition(
    condition=condition,
    every_tick=1,  # Check every tick
    timeout=100,   # Give up after 100 ticks
)

# Create event that triggers when condition is met
with EventRegisterer.capture_mode():
    triggered_event = (
        email_app.send_email(
            recipients=["user@example.com"],
            subject="Inbox Full Alert",
            content="Your inbox has more than 5 emails."
        )
        .depends_on(condition_check, delay_seconds=0)
    )

# Add to scenario
self.events = [condition_check, triggered_event]
```

### Validation Events

Special events that check if the agent is performing correctly:

```python
from are.simulation.types import AgentValidationEvent

def validation_function(env: AbstractEnvironment, event: AbstractEvent) -> bool:
    """
    Check if an agent event is valid.
    Returns True if valid, False otherwise.
    """
    # Check if the event is a send_message_to_user action
    if event.action.function_name == "send_message_to_user":
        return True
    return False

validation_event = AgentValidationEvent(
    check_list=[validation_function],
    schedule_every_ticks=1,  # Check every tick
    timeout=20,  # Timeout after 20 ticks
)

# Add to scenario
self.events.append(validation_event)
```

---

## Validation

### Basic Validation Structure

```python
def validate(self, env) -> ScenarioValidationResult:
    """
    Validate scenario completion.
    
    Args:
        env: Environment containing apps and event log
        
    Returns:
        ScenarioValidationResult with success status and optional details
    """
    try:
        # Perform validation checks
        success = check_completion_criteria(env)
        
        return ScenarioValidationResult(success=success)
    
    except Exception as e:
        # Always catch exceptions
        return ScenarioValidationResult(success=False, exception=e)
```

### Validation Pattern 1: Event Log Validation

Check that specific actions were performed by examining the event log:

```python
def validate(self, env) -> ScenarioValidationResult:
    try:
        # Check if agent sent an email
        email_sent = any(
            event.event_type == EventType.AGENT  # Agent action
            and isinstance(event.action, Action)
            and event.action.function_name == "send_email"  # Specific function
            and event.action.class_name == "EmailClientApp"  # Specific app
            and "bob@example.com" in event.action.args.get("recipients", [])  # Check args
            for event in env.event_log.list_view()
        )
        
        return ScenarioValidationResult(success=email_sent)
    
    except Exception as e:
        return ScenarioValidationResult(success=False, exception=e)
```

### Validation Pattern 2: App State Validation

Check the final state of apps:

```python
def validate(self, env) -> ScenarioValidationResult:
    try:
        # Get app
        task_app = env.get_app("TaskManagerApp")
        
        # Check state
        tasks = list(task_app.tasks.values())
        completed_tasks = [t for t in tasks if t.completed]
        
        # Validation criteria
        success = len(completed_tasks) >= 2
        
        return ScenarioValidationResult(success=success)
    
    except Exception as e:
        return ScenarioValidationResult(success=False, exception=e)
```

### Validation Pattern 3: Multi-Criteria with Rationale

Combine multiple checks with detailed feedback:

```python
def validate(self, env) -> ScenarioValidationResult:
    try:
        criteria = []
        rationale_parts = []
        
        # Criterion 1: Email was sent
        email_sent = check_email_sent(env)
        criteria.append(("email_sent", email_sent))
        if not email_sent:
            rationale_parts.append("Email was not sent")
        
        # Criterion 2: Task was completed
        task_completed = check_task_completed(env)
        criteria.append(("task_completed", task_completed))
        if not task_completed:
            rationale_parts.append("Task was not marked complete")
        
        # Criterion 3: User was notified
        user_notified = check_user_notification(env)
        criteria.append(("user_notified", user_notified))
        if not user_notified:
            rationale_parts.append("User was not notified")
        
        # Overall success
        success = all(result for _, result in criteria)
        
        # Build rationale
        rationale = "; ".join(rationale_parts) if not success else "All criteria met"
        
        return ScenarioValidationResult(
            success=success,
            rationale=rationale
        )
    
    except Exception as e:
        return ScenarioValidationResult(success=False, exception=e)
```

### Validation Pattern 4: Content Quality Checks

Validate the quality or content of agent outputs:

```python
def validate(self, env) -> ScenarioValidationResult:
    try:
        email_app = env.get_app("EmailClientApp")
        sent_emails = email_app.folders["sent"].emails
        
        if not sent_emails:
            return ScenarioValidationResult(
                success=False,
                rationale="No emails were sent"
            )
        
        last_email = sent_emails[-1]
        
        # Check content quality
        checks = {
            "has_greeting": any(
                greeting in last_email.content.lower()
                for greeting in ["hello", "hi", "dear"]
            ),
            "has_closing": any(
                closing in last_email.content.lower()
                for closing in ["regards", "sincerely", "thanks"]
            ),
            "is_professional": not any(
                word in last_email.content.lower()
                for word in ["lol", "omg", "wtf"]
            ),
            "sufficient_length": len(last_email.content) >= 50,
        }
        
        success = all(checks.values())
        
        failed_checks = [name for name, passed in checks.items() if not passed]
        rationale = f"Failed checks: {', '.join(failed_checks)}" if failed_checks else "All quality checks passed"
        
        return ScenarioValidationResult(
            success=success,
            rationale=rationale
        )
    
    except Exception as e:
        return ScenarioValidationResult(success=False, exception=e)
```

### Validation Best Practices

1. **Always use try-catch**: Wrap validation in exception handling
2. **Return detailed rationale**: Explain why validation failed
3. **Check multiple criteria**: Don't just check one thing
4. **Validate behavior, not just state**: Check that actions were performed correctly
5. **Be specific**: Check exact values, not just existence
6. **Consider edge cases**: What if agent does something unexpected?

---

## Complete Examples

### Example 1: Simple Email Response Scenario

```python
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.types import EventRegisterer, EventType, Action

@register_scenario("simple_email_response")
class SimpleEmailResponse(Scenario):
    """Agent must read an email and respond appropriately."""
    
    start_time: float | None = 0
    duration: float | None = 300
    
    def init_and_populate_apps(self, *args, **kwargs) -> None:
        agui = AgentUserInterface()
        email_app = EmailClientApp()
        
        # Add an initial email
        email_app.add_email(
            Email(
                sender="boss@company.com",
                recipients=[email_app.user_email],
                subject="Meeting Request",
                content="Can you attend the team meeting tomorrow at 2 PM?",
                email_id="meeting_request",
            )
        )
        
        self.apps = [agui, email_app]
    
    def build_events_flow(self) -> None:
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)
        
        with EventRegisterer.capture_mode():
            # User asks agent to check email
            event1 = agui.send_message_to_agent(
                content="Please check my email and respond to any meeting requests."
            ).depends_on(None, delay_seconds=5)
            
            # Oracle: Agent should reply to the email
            oracle1 = (
                email_app.reply_to_email(
                    email_id="meeting_request",
                    content="Yes, I can attend the meeting at 2 PM tomorrow."
                )
                .oracle()
                .depends_on(event1, delay_seconds=5)
            )
        
        self.events = [event1, oracle1]
    
    def validate(self, env) -> ScenarioValidationResult:
        try:
            # Check if agent replied to the email
            replied = any(
                event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.function_name == "reply_to_email"
                and event.action.args.get("email_id") == "meeting_request"
                for event in env.event_log.list_view()
            )
            
            return ScenarioValidationResult(success=replied)
        
        except Exception as e:
            return ScenarioValidationResult(success=False, exception=e)

if __name__ == "__main__":
    from are.simulation.scenarios.utils.cli_utils import run_and_validate
    run_and_validate(SimpleEmailResponse())
```

### Example 2: Multi-App Task Coordination

```python
@register_scenario("multi_app_coordination")
class MultiAppCoordination(Scenario):
    """Agent must coordinate across email, calendar, and contacts."""
    
    start_time: float | None = 0
    duration: float | None = 600
    
    def init_and_populate_apps(self, *args, **kwargs) -> None:
        from are.simulation.apps.calendar import CalendarApp
        from are.simulation.apps.contacts import ContactsApp, Contact, Gender, Status
        
        agui = AgentUserInterface()
        email_app = EmailClientApp()
        calendar_app = CalendarApp()
        contacts_app = ContactsApp()
        
        # Add contact
        contacts_app.add_contact(
            Contact(
                first_name="Alice",
                last_name="Johnson",
                email="alice@company.com",
                phone="+1-555-0123",
                gender=Gender.FEMALE,
                status=Status.EMPLOYED,
            )
        )
        
        # Add initial email
        email_app.add_email(
            Email(
                sender="alice@company.com",
                recipients=[email_app.user_email],
                subject="Project Meeting",
                content="Let's schedule a project meeting for next week. How about Wednesday at 10 AM?",
                email_id="meeting_proposal",
            )
        )
        
        self.apps = [agui, email_app, calendar_app, contacts_app]
    
    def build_events_flow(self) -> None:
        from are.simulation.apps.calendar import CalendarApp
        
        agui = self.get_typed_app(AgentUserInterface)
        email_app = self.get_typed_app(EmailClientApp)
        calendar_app = self.get_typed_app(CalendarApp)
        
        with EventRegisterer.capture_mode():
            # User asks agent to handle meeting request
            event1 = agui.send_message_to_agent(
                content="Please check my email from Alice and schedule the meeting she proposed."
            ).depends_on(None, delay_seconds=5)
            
            # Oracle: Agent should add calendar event
            oracle1 = (
                calendar_app.add_calendar_event(
                    title="Project Meeting with Alice",
                    start_datetime="2024-01-17 10:00:00",
                    end_datetime="2024-01-17 11:00:00",
                    description="Project meeting as requested by Alice"
                )
                .oracle()
                .depends_on(event1, delay_seconds=5)
            )
            
            # Oracle: Agent should reply to email
            oracle2 = (
                email_app.reply_to_email(
                    email_id="meeting_proposal",
                    content="Meeting scheduled for Wednesday, January 17th at 10 AM."
                )
                .oracle()
                .depends_on(oracle1, delay_seconds=2)
            )
            
            # Oracle: Agent should notify user
            oracle3 = (
                agui.send_message_to_user(
                    content="I've scheduled the meeting with Alice and confirmed via email."
                )
                .oracle()
                .depends_on(oracle2, delay_seconds=2)
            )
        
        self.events = [event1, oracle1, oracle2, oracle3]
    
    def validate(self, env) -> ScenarioValidationResult:
        try:
            from are.simulation.apps.calendar import CalendarApp
            
            # Check calendar event was created
            calendar_app = env.get_app("CalendarApp")
            meeting_exists = any(
                "Alice" in event.title
                for event in calendar_app.events.values()
            )
            
            # Check email reply was sent
            email_replied = any(
                event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.function_name == "reply_to_email"
                for event in env.event_log.list_view()
            )
            
            # Check user was notified
            user_notified = any(
                event.event_type == EventType.AGENT
                and isinstance(event.action, Action)
                and event.action.function_name == "send_message_to_user"
                for event in env.event_log.list_view()
            )
            
            success = meeting_exists and email_replied and user_notified
            
            rationale = []
            if not meeting_exists:
                rationale.append("Meeting not scheduled")
            if not email_replied:
                rationale.append("Email not replied")
            if not user_notified:
                rationale.append("User not notified")
            
            return ScenarioValidationResult(
                success=success,
                rationale="; ".join(rationale) if rationale else "All tasks completed"
            )
        
        except Exception as e:
            return ScenarioValidationResult(success=False, exception=e)
```

### Example 3: Custom App with Scenario

```python
# First, define the custom app
from dataclasses import dataclass, field
from typing import Any
import uuid
from are.simulation.apps.app import App
from are.simulation.tool_utils import app_tool, data_tool, OperationType
from are.simulation.types import event_registered
from are.simulation.utils import get_state_dict, type_check

@dataclass
class Note:
    """A simple note"""
    title: str
    content: str
    note_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    
    def __post_init__(self):
        if not self.title:
            raise ValueError("Note must have a title")

@dataclass
class NotesApp(App):
    """A simple note-taking app"""
    
    name: str | None = "NotesApp"
    notes: dict[str, Note] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__init__(self.name)
    
    def get_state(self) -> dict[str, Any]:
        return get_state_dict(self, ["notes"])
    
    def load_state(self, state_dict: dict[str, Any]):
        self.notes = {}
        for note_id, note_data in state_dict.get("notes", {}).items():
            self.notes[note_id] = Note(
                title=note_data["title"],
                content=note_data["content"],
                note_id=note_data.get("note_id", note_id)
            )
    
    def reset(self):
        super().reset()
        self.notes = {}
    
    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.WRITE)
    def create_note(self, title: str, content: str) -> str:
        """
        Create a new note.
        
        :param title: The title of the note
        :param content: The content of the note
        :returns: The note_id of the created note
        """
        note = Note(title=title, content=content)
        self.notes[note.note_id] = note
        return note.note_id
    
    @type_check
    @app_tool()
    @data_tool()
    @event_registered(operation_type=OperationType.READ)
    def get_notes(self) -> list[dict[str, Any]]:
        """
        Get all notes.
        
        :returns: List of all notes
        """
        return [
            {
                "note_id": note.note_id,
                "title": note.title,
                "content": note.content
            }
            for note in self.notes.values()
        ]

# Now create a scenario using the app
@register_scenario("notes_scenario")
class NotesScenario(Scenario):
    """Agent must take notes based on information received"""
    
    start_time: float | None = 0
    duration: float | None = 300
    
    def init_and_populate_apps(self, *args, **kwargs) -> None:
        agui = AgentUserInterface()
        notes_app = NotesApp()
        
        self.apps = [agui, notes_app]
    
    def build_events_flow(self) -> None:
        agui = self.get_typed_app(AgentUserInterface)
        notes_app = self.get_typed_app(NotesApp)
        
        with EventRegisterer.capture_mode():
            # User provides information to note
            event1 = agui.send_message_to_agent(
                content="Please create a note titled 'Meeting Agenda' with the content: '1. Budget review, 2. Team updates, 3. Project timeline'"
            ).depends_on(None, delay_seconds=5)
            
            # Oracle: Agent should create the note
            oracle1 = (
                notes_app.create_note(
                    title="Meeting Agenda",
                    content="1. Budget review, 2. Team updates, 3. Project timeline"
                )
                .oracle()
                .depends_on(event1, delay_seconds=5)
            )
        
        self.events = [event1, oracle1]
    
    def validate(self, env) -> ScenarioValidationResult:
        try:
            notes_app = env.get_app("NotesApp")
            
            # Check if note was created with correct title
            note_created = any(
                note.title == "Meeting Agenda"
                and "Budget review" in note.content
                and "Team updates" in note.content
                and "Project timeline" in note.content
                for note in notes_app.notes.values()
            )
            
            return ScenarioValidationResult(
                success=note_created,
                rationale="Note created correctly" if note_created else "Note not created or incorrect"
            )
        
        except Exception as e:
            return ScenarioValidationResult(success=False, exception=e)
```

---

## Best Practices and Common Patterns

### Scenario Design Best Practices

1. **Start Simple**: Begin with basic scenarios before adding complexity
2. **Clear Task Definition**: Make it obvious what the agent should accomplish
3. **Realistic Data**: Use realistic names, emails, dates, and content
4. **Progressive Difficulty**: Build up from simple to complex scenarios
5. **Test in Oracle Mode**: Always test that oracle events execute correctly
6. **Comprehensive Validation**: Check multiple aspects of task completion

### App Design Best Practices

1. **Single Responsibility**: Each app should have a clear, focused purpose
2. **Complete APIs**: Provide all necessary operations for realistic use
3. **State Management**: Always implement get_state/load_state/reset properly
4. **Clear Documentation**: Write excellent docstrings - agents read them
5. **Error Handling**: Handle edge cases and invalid inputs gracefully
6. **Type Safety**: Use type hints and @type_check decorator
7. **Realistic Behavior**: Apps should behave like their real-world counterparts

### Event Design Patterns

**Pattern 1: Simple Chain**
```python
# User asks → Agent acts → Environment responds
event1 = agui.send_message_to_agent("Do task").depends_on(None, delay_seconds=0)
oracle1 = app.do_task().oracle().depends_on(event1, delay_seconds=5)
event2 = agui.send_message_to_user("Done").depends_on(oracle1, delay_seconds=2)
```

**Pattern 2: Parallel Events**
```python
# Multiple things happen at once
event1 = email1.depends_on(None, delay_seconds=5)
event2 = message1.depends_on(None, delay_seconds=5)  # Same time as event1
event3 = converge_event.depends_on([event1, event2], delay_seconds=0)
```

**Pattern 3: Interruption**
```python
# Agent is working when new event interrupts
event1 = agui.send_message_to_agent("Start task").depends_on(None, delay_seconds=5)
event2 = email_arrives.depends_on(event1, delay_seconds=10)  # Interrupt!
oracle1 = handle_email.oracle().depends_on(event2, delay_seconds=5)
```

**Pattern 4: Multi-Turn**
```python
# Multiple back-and-forth interactions
turn1 = agui.send_message_to_agent("Request").depends_on(None, delay_seconds=5)
response1 = agui.send_message_to_user("Info").oracle().depends_on(turn1, delay_seconds=5)
turn2 = agui.send_message_to_agent("Followup").depends_on(response1, delay_seconds=5)
response2 = agui.send_message_to_user("Final").oracle().depends_on(turn2, delay_seconds=5)
```

### Common Validation Patterns

**Pattern 1: Action Verification**
```python
# Verify agent called a specific function with specific args
action_performed = any(
    event.event_type == EventType.AGENT
    and event.action.function_name == "target_function"
    and event.action.args.get("key") == "expected_value"
    for event in env.event_log.list_view()
)
```

**Pattern 2: State Verification**
```python
# Verify final state of an app
app = env.get_app("AppName")
correct_state = (
    len(app.items) > 0
    and app.status == "expected_status"
)
```

**Pattern 3: Sequence Verification**
```python
# Verify actions happened in correct order
agent_events = [
    e for e in env.event_log.list_view()
    if e.event_type == EventType.AGENT
]
correct_sequence = (
    len(agent_events) >= 3
    and agent_events[0].action.function_name == "first_action"
    and agent_events[1].action.function_name == "second_action"
    and agent_events[2].action.function_name == "third_action"
)
```

### Debugging Tips

1. **Test Oracle Mode First**:
   ```python
   if __name__ == "__main__":
       from are.simulation.scenarios.utils.cli_utils import run_and_validate
       run_and_validate(MyScenario())
   ```

2. **Check Event Dependencies**: Use visualization or logging to verify DAG structure

3. **Validate State Management**: Test that apps can be saved/loaded/reset correctly

4. **Use Descriptive Names**: Name events, tasks, and IDs clearly for easier debugging

5. **Add Logging**: Use logging to track what's happening
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.debug(f"Creating event with params: {params}")
   ```

### Common Pitfalls to Avoid

1. **❌ Forgetting `super().__init__()` in app __post_init__**
   ```python
   # BAD
   def __post_init__(self):
       self.data = {}
   
   # GOOD
   def __post_init__(self):
       super().__init__(self.name)
       self.data = {}
   ```

2. **❌ Not handling None in validation**
   ```python
   # BAD
   email_sent = event.action.args["recipients"]  # Can raise KeyError
   
   # GOOD
   email_sent = event.action.args.get("recipients", [])
   ```

3. **❌ Creating circular event dependencies**
   ```python
   # BAD - circular dependency
   event1.depends_on(event2)
   event2.depends_on(event1)  # ERROR!
   ```

4. **❌ Not using capture_mode for events**
   ```python
   # BAD - this actually executes the method
   event = app.some_method()
   
   # GOOD - capture mode returns an Event
   with EventRegisterer.capture_mode():
       event = app.some_method()
   ```

5. **❌ Forgetting to mark oracle events**
   ```python
   # BAD - this is an ENV event, not oracle
   oracle = app.expected_action().depends_on(event1)
   
   # GOOD
   oracle = app.expected_action().oracle().depends_on(event1)
   ```

6. **❌ Not wrapping validation in try-catch**
   ```python
   # BAD
   def validate(self, env):
       app = env.get_app("App")  # Can raise exception
       return ScenarioValidationResult(success=True)
   
   # GOOD
   def validate(self, env):
       try:
           app = env.get_app("App")
           return ScenarioValidationResult(success=True)
       except Exception as e:
           return ScenarioValidationResult(success=False, exception=e)
   ```

---

## Summary Checklist

### Creating a Scenario ✓

- [ ] Import required modules (Scenario, register_scenario, apps, types)
- [ ] Define scenario class with @register_scenario decorator
- [ ] Set start_time and duration
- [ ] Implement init_and_populate_apps:
  - [ ] Create all necessary app instances
  - [ ] Populate apps with initial data
  - [ ] Store apps in self.apps list
- [ ] Implement build_events_flow:
  - [ ] Get typed app references
  - [ ] Use EventRegisterer.capture_mode()
  - [ ] Create event chain with proper dependencies
  - [ ] Add oracle events for expected behavior
  - [ ] Store events in self.events list
- [ ] Implement validate:
  - [ ] Wrap in try-catch
  - [ ] Check event log and/or app state
  - [ ] Return ScenarioValidationResult
- [ ] Test with run_and_validate

### Creating an App ✓

- [ ] Import required modules (App, decorators, type hints)
- [ ] Define data models with dataclasses
- [ ] Create app class inheriting from App
- [ ] Implement __post_init__ with super().__init__()
- [ ] Implement state management:
  - [ ] get_state()
  - [ ] load_state()
  - [ ] reset()
- [ ] Implement tool methods:
  - [ ] Add appropriate decorators (@app_tool, @type_check, etc.)
  - [ ] Write clear, detailed docstrings
  - [ ] Return serializable data
  - [ ] Handle errors gracefully
- [ ] (Optional) Implement protocols
- [ ] Test app in a simple scenario

---

## Running and Testing

### Running a Scenario

```bash
# Run with default agent
uv run are-run -s scenario_id -a default

# Run with specific model and provider (in this case, openai's gpt-5-mini and the responses API agent harness)
uv run are-run -s scenario_id -a responses --model gpt-5-mini --provider openai

# Run in oracle mode (for testing)
uv run are-run -s scenario_id -a default --oracle-mode
```

### Running in Python

```python
from are.simulation.scenarios.utils.cli_utils import run_and_validate
from my_scenario import MyScenario

# Run and validate in oracle mode
result = run_and_validate(MyScenario())
print(f"Success: {result.success}")
```

---

## Additional Resources

### File Locations in Repository

- **Scenarios**: `are/simulation/scenarios/`
- **Apps**: `are/simulation/apps/`
- **Tutorials**: `are/simulation/scenarios/scenario_tutorial/`, `are/simulation/scenarios/scenario_apps_tutorial/`
- **Documentation**: `docs/`

### Key Modules to Import

```python
# Scenario basics
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario

# Apps
from are.simulation.apps.app import App
from are.simulation.apps.agent_user_interface import AgentUserInterface
from are.simulation.apps.email_client import Email, EmailClientApp
from are.simulation.apps.calendar import CalendarApp
from are.simulation.apps.contacts import Contact, ContactsApp
from are.simulation.apps.messaging import MessagingApp

# Event types and utilities
from are.simulation.types import (
    EventRegisterer,
    EventType,
    Action,
    Event,
    ConditionCheckEvent,
)

# Tool decorators
from are.simulation.tool_utils import (
    app_tool,
    user_tool,
    env_tool,
    data_tool,
    OperationType,
)

# Event registration
from are.simulation.types import event_registered

# Utilities
from are.simulation.utils import get_state_dict, type_check
```

---

This primer should provide everything needed to create scenarios and apps in Meta Agents Research Environments without additional context. For more examples, refer to the scenario tutorials in the repository (`scenario_tutorial` and `scenario_apps_tutorial`).

