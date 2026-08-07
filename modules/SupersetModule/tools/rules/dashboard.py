"""Dashboard creation rules for Superset MCP integration.

Provides the get_dashboard_creation_rules() function that returns
a Markdown guide covering dashboard hierarchy rules, required
properties, and grid sizing.
"""


def get_dashboard_creation_rules() -> str:
    """Return Markdown guide for creating Superset dashboards.

    Description:
        Produces a structured reference covering the mandatory dashboard layout
        hierarchy (ROOT→GRID→ROW→CHART), required component properties,
        metadata requirements, and common pitfalls.

        Used as LLM context and developer documentation for the Superset
        dashboard automation tools.

    Returns:
        A Markdown string with sections: Strict Hierarchy, Required Properties,
        Meta Data, and Avoid Top-Level Charts.
    """
    return """
# Superset Dashboard Creation Rules

1. **Strict Hierarchy**: Every `position_json` must follow: `ROOT` -> `GRID` -> `ROW` -> `CHART`.
   - Charts MUST be children of a `ROW`.
   - Rows MUST be children of the `GRID_ID`.

2. **Required Properties**:
   - Every component must have a `children` array (even if empty `[]`).
   - Every component must have a `parents` array.
   - Components should use standardized string IDs: `ROW-xxxx`, `CHART-xxxx`.

3. **Meta Data**:
   - `CHART` meta must include `chartId` (integer) and `sliceName` (string).
   - `width` should be between 1 and 12 (Superset uses a 12-column grid).

4. **Avoid Top-Level Charts**: Never place a `CHART` directly under `GRID_ID`. This causes 'length of undefined' errors in the Superset frontend.
"""
