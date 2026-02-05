# Mermaid Pie Chart Syntax

Pie Charts in Mermaid visualize the proportional distribution of a whole into different categories.

## Diagram Declaration

Starts with the `pie` keyword.

```mermaid
pie
    title What I eat for breakfast
```

## Sections and Values

Each section represents a category, followed by its numerical value.

`"Section Name" : Value`

-   **`Section Name`**: The label for the slice of the pie.
-   **`Value`**: A numerical value representing the size of the slice. Mermaid automatically calculates percentages.

Example:
```mermaid
pie
    "Apples" : 42
    "Berries" : 20
    "Oranges" : 10
```

## Options

-   `showData`: Setting this to `true` will display the actual data values on the pie chart, in addition to percentages. (This is a global config option, not part of the pie chart syntax itself)

## Example Pie Chart

```mermaid
pie
    title Expenses by Category
    "Housing" : 40
    "Food" : 25
    "Transportation" : 15
    "Entertainment" : 10
    "Savings" : 10
```
