# Mermaid Requirement Diagram Syntax

Requirement Diagrams in Mermaid are used to visualize and manage requirements, their relationships, and their connections to other artifacts.

## Diagram Declaration

Starts with the `requirementDiagram` keyword.

```mermaid
requirementDiagram
    requirement test_req {
        id: "1"
        text: "The test requirement."
        risk: high
        verify: "test_case_1"
    }
```

## Requirements

You can define different types of requirements: `requirement`, `functionalRequirement`, `interfaceRequirement`, `physicalRequirement`, `designRequirement`.

Each requirement has properties:

-   **`id`**: Unique identifier for the requirement.
-   **`text`**: Description of the requirement.
-   **`risk`**: (Optional) e.g., `high`, `medium`, `low`.
-   **`verify`**: (Optional) How the requirement is verified.

Example:
```mermaid
requirementDiagram
    requirement R1 {
        id: "FR1"
        text: "The system shall allow users to log in."
        risk: medium
        verify: "Login Test Plan"
    }

    functionalRequirement FR2 {
        id: "FR2"
        text: "The system shall display a list of available products."
        risk: low
        verify: "Product Listing Test"
    }
```

## Elements

You can define other elements to link requirements to:

-   **`element`**: A generic system element.
-   **`artifact`**: A document or file.
-   **`testCase`**: A test case.

Example:
```mermaid
requirementDiagram
    element Backend {
        type: "Software"
    }
    artifact FrontendSpec {
        version: "1.0"
    }
    testCase TC1 {
        id: "TC_LOGIN_001"
        text: "Verify user can login with valid credentials."
    }
```

## Relationships

Relationships link requirements to other requirements or elements.

-   **`contains`**: `ReqA contains ReqB`
-   **`satisfies`**: `ReqA satisfies ElemB`
-   **`verifies`**: `ReqA verifies TestC`
-   **`derives`**: `ReqA derives ReqB`
-   **`refines`**: `ReqA refines ReqB`
-   **`traceto`**: `ReqA traceto ElemB`

Example:
```mermaid
requirementDiagram
    requirement R1 { id: "UserAuth" text: "User authentication" }
    functionalRequirement FR1 { id: "Login" text: "User login" }
    element BackendAPI { type: "Software" }
    testCase TC_Login { id: "TC_Login" }

    R1 contains FR1
    FR1 satisfies BackendAPI
    FR1 verifies TC_Login
```

## Example Requirement Diagram

```mermaid
requirementDiagram
    requirement SystemReq {
        id: "SYS-001"
        text: "The system shall manage customer orders."
        risk: high
    }

    functionalRequirement UserAuth {
        id: "FR-001"
        text: "Users must be able to securely log in."
        risk: medium
        verify: "Test Cases for Login"
    }

    functionalRequirement ProductListing {
        id: "FR-002"
        text: "The system shall display available products."
        risk: low
        verify: "Test Cases for Product List"
    }

    interfaceRequirement API_Auth {
        id: "IR-001"
        text: "Authentication API must be secured."
    }

    element Frontend {
        type: "Web Application"
    }

    element Backend {
        type: "Microservice"
    }

    testCase TC_Login {
        id: "TC-LOGIN-001"
        text: "Verify successful login."
    }

    SystemReq contains UserAuth
    SystemReq contains ProductListing

    UserAuth derives API_Auth
    UserAuth verifies TC_Login
    UserAuth satisfies Frontend
    UserAuth satisfies Backend

    ProductListing satisfies Frontend
    ProductListing satisfies Backend
```
