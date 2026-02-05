# Mermaid State Diagram Syntax

State diagrams in Mermaid visualize the different states an object can have and the transitions between those states due to events.

## Diagram Declaration

Starts with the `stateDiagram-v2` keyword (for the newer syntax version).

```mermaid
stateDiagram-v2
    [*] --> StateA
```

## States

### Simple States

A simple state is defined by its name.

```mermaid
stateDiagram-v2
    State1
    State2
```

### Composite States (Nested States)

States can contain other states.

```mermaid
stateDiagram-v2
    state "High-level State" as HighLevelState {
        StateA
        StateB
    }
```

### Start and End States

-   **Start State**: `[*]`
-   **End State**: `[*]` (when it's the target of a transition)

Example:
```mermaid
stateDiagram-v2
    [*] --> InitialState
    FinalState --> [*]
```

## Transitions

Transitions define how the system moves from one state to another.

`SourceState --> TargetState`

You can add a description of the event that triggers the transition, and optionally an action.

`SourceState --> TargetState: EventDescription / Action`

Example:
```mermaid
stateDiagram-v2
    Idle --> Active: turn_on
    Active --> Idle: turn_off / log_duration()
```

## Concurrency (Fork and Join)

Represent parallel activities.

-   **Fork**: `StateA --> fork_state --> StateB` and `fork_state --> StateC`
-   **Join**: `StateB --> join_state --> StateD` and `StateC --> join_state`

Example:
```mermaid
stateDiagram-v2
    [*] --> ForkState

    ForkState --> StateA_parallel
    ForkState --> StateB_parallel

    StateA_parallel --> JoinState
    StateB_parallel --> JoinState

    JoinState --> EndState
```

## Example State Diagram

```mermaid
stateDiagram-v2
    [*] --> Off
    Off --> On: PowerButton
    On --> Off: PowerButton

    state On {
        [*] --> Idle
        Idle --> Playing: PlayButton
        Playing --> Paused: PauseButton
        Paused --> Playing: PlayButton
        Playing --> Idle: StopButton
        Paused --> Idle: StopButton
    }
```
