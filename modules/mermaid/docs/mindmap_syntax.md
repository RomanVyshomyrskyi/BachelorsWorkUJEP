# Mermaid Mindmap Syntax

Mindmaps in Mermaid visualize hierarchical information in a branching structure, useful for brainstorming and organizing ideas.

## Diagram Declaration

Starts with the `mindmap` keyword.

```mermaid
mindmap
    root((Mindmap Root))
```

## Nodes

Nodes are defined by indentation. The top-most node is the root.

-   **Root Node**: Must be the first line, often with `((text))` for a rounded shape.
-   **Child Nodes**: Indent to create child nodes. Each level of indentation represents a new level in the hierarchy.

Example:
```mermaid
mindmap
    root((Main Idea))
        Branch 1
            Sub-Branch A
            Sub-Branch B
        Branch 2
            Sub-Branch C
```

### Node Shapes

Mermaid mindmaps support various node shapes:

-   **Rounded rectangle (default for children)**: `Node text`
-   **Rounded rectangle**: `(Node text)`
-   **Circle**: `((Node text))`
-   **Bang (Hexagon)**: `))Node text((`
-   **Cloud**: `)Node text(`
-   **Square**: `[Node text]`

Example:
```mermaid
mindmap
    root((Root Concept))
        (Idea 1)
        Idea 2
        ))Important Point((
        )Ephemeral Thought(
        [Key Decision]
```

## Example Mindmap

```mermaid
mindmap
    root((Project Planning))
        Introduction
            Goal
            Scope
        Phases
            Analysis
                Requirements
                Feasibility
            Design
                Architecture
                Database
                UI/UX
            Implementation
                Backend
                Frontend
                Integrations
            Testing
                Unit Tests
                Integration Tests
                UAT
            Deployment
                Staging
                Production
        Team
            Roles
            Responsibilities
        Timeline
            Milestones
            Deadlines
        Risks
            Technical
            Resource
            Market
```
