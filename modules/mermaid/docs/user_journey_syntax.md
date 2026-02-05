# Mermaid User Journey Syntax

User Journey Maps in Mermaid visualize the user's experience when interacting with a product or service, from their perspective. It outlines their goals, actions, thoughts, and feelings.

## Diagram Declaration

Starts with the `journey` keyword.

```mermaid
journey
    title My working day
```

## Sections (Actors/Personas)

Each section typically represents a different persona or actor in the journey.

```mermaid
journey
    section Customer
    ...
    section Support
    ...
```

## Tasks/Stages

Tasks are the steps or stages within a section of the user journey.

`Task Name: Stage Name: Score`

-   **`Task Name`**: A description of the user's action or step.
-   **`Stage Name`**: The overarching stage of the journey (e.g., "Awareness", "Consideration", "Purchase").
-   **`Score`**: An optional numerical score reflecting the user's emotion/satisfaction at this stage (-5 to 5).

Example:
```mermaid
journey
    section User
        Reads documentation: Learning: 3
        Tries example: Experimenting: 4
        Asks for help: Frustration: -2
```

## Example User Journey Map

```mermaid
journey
    title My shopping experience at an online store

    section User
        Clicks on ad: Discovery: 5
        Browses products: Exploration: 4
        Adds to cart: Selection: 3
        Proceeds to checkout: Payment: 2
        Completes purchase: Satisfaction: 5

    section Support
        Receives order: Fulfillment: 4
        Sends shipping update: Communication: 3
        Handles return request: Resolution: 1
```
