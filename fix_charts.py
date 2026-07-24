"""
Repair script for fixing outdated viz_type across all Superset charts.

This script performs a comprehensive scan of every chart in a Superset
instance and updates any charts that use deprecated viz_type values (e.g.
"bar", "line", "dist_bar") to their modern equivalents (e.g.
"echarts_timeseries_bar", "echarts_timeseries_line").

How it works:
  1. Loads an auth token from a pre-stored file, or falls back to
     programmatic login with hardcoded admin credentials.
  2. Fetches the full list of charts from the Superset REST API.
  3. Filters the list to only those whose viz_type appears in VIZ_TYPE_MAP.
  4. Fixes each chart concurrently via asyncio.gather, updating both the
     top-level viz_type field and the viz_type stored inside the JSON
     params blob.
  5. Prints a summary of how many charts were fixed, already correct,
     or hit errors.

VIZ_TYPE_MAP — deprecated → modern viz_type mapping:
    "bar"       → "echarts_timeseries_bar"
    "dist_bar"  → "echarts_timeseries_bar"
    "line"      → "echarts_timeseries_line"
    "area"      → "echarts_area"
    "scatter"   → "echarts_timeseries_scatter"
    "bubble"    → "bubble_v2"
    "gantt"     → "gantt_chart"
    "map"       → "world_map"
    "gauge"     → "gauge_chart"
    "heatmap"   → "heatmap_v2"
    "histogram" → "histogram_v2"
    "sankey"    → "sankey_v2"
    "sunburst"  → "sunburst_v2"
    "treemap"   → "treemap_v2"
    "tree"      → "tree_chart"
    "pivot_table" → "pivot_table_v2"
    "boxplot"   → "box_plot"
"""

import json
import httpx
import asyncio

# Viz type mapping
VIZ_TYPE_MAP = {
    "bar": "echarts_timeseries_bar",
    "dist_bar": "echarts_timeseries_bar",
    "line": "echarts_timeseries_line",
    "area": "echarts_area",
    "scatter": "echarts_timeseries_scatter",
    "bubble": "bubble_v2",
    "gantt": "gantt_chart",
    "map": "world_map",
    "gauge": "gauge_chart",
    "heatmap": "heatmap_v2",
    "histogram": "histogram_v2",
    "sankey": "sankey_v2",
    "sunburst": "sunburst_v2",
    "treemap": "treemap_v2",
    "tree": "tree_chart",
    "pivot_table": "pivot_table_v2",
    "boxplot": "box_plot",
}


async def fix_chart_viz_type(base_url: str, chart_id: int) -> dict:
    """Fix a single chart's viz_type by updating both the top-level field and the params JSON blob.

    Retrieves the current chart configuration via the Superset REST API, checks
    whether its viz_type (or the viz_type nested inside the params JSON) matches
    a key in VIZ_TYPE_MAP, and if so patches both locations with the modern
    viz_type value.

    Args:
        base_url: The base URL of the Superset instance (e.g. ``http://host:8088``).
        chart_id: The numeric ID of the chart to fix.

    Returns:
        A result dict with at least ``id`` and ``status`` keys. On success
        ``status`` is ``"fixed"`` or ``"ok"``; on failure it is ``"error"``
        with a ``message`` field describing what went wrong.

    Example:
        >>> result = await fix_chart_viz_type("http://host:8088", 160)
        >>> print(result)
        {'id': 160, 'status': 'fixed', 'old_viz': 'bar', 'new_viz': 'echarts_timeseries_bar'}
    """
    # Create an async HTTP client scoped to this single-chart operation
    async with httpx.AsyncClient() as client:
        # --- Step 1: Fetch the current chart configuration from Superset ---
        resp = await client.get(f"{base_url}/api/v1/chart/{chart_id}")
        # If the fetch itself fails (network error, auth issue, etc.), bail out
        if resp.status_code != 200:
            return {"id": chart_id, "status": "error", "message": f"Failed to fetch: {resp.text}"}

        chart = resp.json()["result"]
        # Read the top-level viz_type stored directly on the chart object
        old_viz = chart.get("viz_type", "")

        # --- Step 2: Parse the params JSON blob and read the nested viz_type ---
        params = json.loads(chart.get("params", "{}"))
        old_params_viz = params.get("viz_type", "")

        # --- Step 3: Skip charts that already use a modern viz_type ---
        # Only proceed if at least one location contains a deprecated value
        if old_viz not in VIZ_TYPE_MAP and old_params_viz not in VIZ_TYPE_MAP:
            return {"id": chart_id, "status": "ok", "viz_type": old_viz}

        # --- Step 4: Determine the replacement viz_type ---
        # Prefer matching old_viz; fall back to params viz_type if the top-level
        # was already correct but the params still had the old value
        new_viz = VIZ_TYPE_MAP.get(old_viz, VIZ_TYPE_MAP.get(old_params_viz, old_viz))

        # --- Step 5: Update the viz_type inside the params JSON blob ---
        if "viz_type" in params:
            params["viz_type"] = new_viz

        # --- Step 6: Build the PATCH payload with both fields updated ---
        update_payload = {
            "viz_type": new_viz,
            "params": json.dumps(params),
        }

        # --- Step 7: Send the PUT request to persist the changes ---
        update_resp = await client.put(
            f"{base_url}/api/v1/chart/{chart_id}",
            json=update_payload,
        )

        # --- Step 8: Return a result dict summarising what happened ---
        if update_resp.status_code == 200:
            return {
                "id": chart_id,
                "status": "fixed",
                "old_viz": old_viz,
                "new_viz": new_viz,
                "old_params_viz": old_params_viz,
                "slice_name": chart.get("slice_name"),
            }
        else:
            return {
                "id": chart_id,
                "status": "error",
                "old_viz": old_viz,
                "new_viz": new_viz,
                "message": update_resp.text,
            }


async def main():
    """Scan all charts in a Superset instance and fix outdated viz_type values.

    Orchestrates the full repair workflow:

    1. Loads the Superset base URL and an auth token (from file or login).
    2. Fetches the complete chart list from ``GET /api/v1/chart/``.
    3. Filters to only those charts whose ``viz_type`` appears in
       ``VIZ_TYPE_MAP``.
    4. Fixes every flagged chart concurrently via ``asyncio.gather``.
    5. Prints a summary (fixed / ok / errors) and details on any failures.

    Returns:
        None

    Example:
        >>> asyncio.run(main())
        Loaded token from modules/SupersetModule/.tokens/.superset_token_superset_main
        Found 42 charts
        Charts needing viz_type fix: 5
        Summary:
          Fixed: 5
          Errors: 0
          Already OK: 37
    """
    import os
    # Get Superset credentials from environment or use defaults
    superset_url = "http://192.168.37.73:8088"

    # --- Step 1: Try to load a pre-stored auth token from the project tree ---
    token_file = os.path.join(os.path.dirname(__file__), "modules", "SupersetModule", ".tokens", ".superset_token_superset_main")
    token = None
    if os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()
            print(f"Loaded token from {token_file}")

    # --- Step 2: Create the HTTP client and attach the auth token ---
    async with httpx.AsyncClient() as client:
        if token:
            client.headers.update({"Authorization": f"Bearer {token}"})

        # --- Step 3: If no token was found, attempt programmatic login ---
        if not token:
            # Fallback: try login
            login_resp = await client.post(
                f"{superset_url}/api/v1/security/login",
                json={"username": "admin", "password": "admin"},
            )
            if login_resp.status_code != 200:
                print(f"Login failed: {login_resp.text[:200]}")
                return
            token = login_resp.json().get("access_token")
            if not token:
                print("No access token in response")
                return

        # --- Step 4: Fetch the complete list of charts from Superset ---
        resp = await client.get(f"{superset_url}/api/v1/chart/")
        if resp.status_code != 200:
            print(f"Failed to fetch charts: {resp.text}")
            return

        charts = resp.json()["result"]["charts"]
        print(f"Found {len(charts)} charts")

        # --- Step 5: Filter to only charts with deprecated viz_type values ---
        needs_fix = []
        for chart in charts:
            viz = chart.get("viz_type", "")
            if viz in VIZ_TYPE_MAP:
                needs_fix.append(chart["id"])

        print(f"Charts needing viz_type fix: {len(needs_fix)}")
        for cid in needs_fix:
            print(f"  Chart {cid}")

        if not needs_fix:
            print("No charts need fixing!")
            return

        # --- Step 6: Fix every flagged chart concurrently ---
        print("\nFixing charts...")
        results = await asyncio.gather(*[fix_chart_viz_type(superset_url, cid) for cid in needs_fix])

        # --- Step 7: Print a summary of the repair operation ---
        fixed = sum(1 for r in results if r.get("status") == "fixed")
        errors = sum(1 for r in results if r.get("status") == "error")
        ok = sum(1 for r in results if r.get("status") == "ok")

        print(f"\nSummary:")
        print(f"  Fixed: {fixed}")
        print(f"  Errors: {errors}")
        print(f"  Already OK: {ok}")

        if errors:
            print("\nErrors:")
            for r in results:
                if r.get("status") == "error":
                    print(f"  Chart {r['id']}: {r.get('message', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
