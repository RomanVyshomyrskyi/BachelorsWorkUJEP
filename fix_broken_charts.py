#!/usr/bin/env python3
"""
Fix 5 broken charts by updating their params.

This script applies targeted parameter patches to five known-broken charts
(CIDs 160–164) whose ``params`` JSON blobs had incorrect or incomplete
configuration (e.g. wrong datasource, missing fields, stale viz_type).

How it works:
  1. Reads a pre-stored Superset auth token from disk.
  2. Fetches a CSRF token from ``/api/v1/security/csrf_token/`` and attaches
     it to every request.
  3. Iterates over the ``CHART_FIXES`` dictionary (chart_id → params dict),
     sends a ``PUT /api/v1/chart/<id>`` with the corrected ``params`` JSON.
  4. Prints a per-chart status line and a final summary.

CHART_FIXES mapping:
    160  –  table chart  (datasource 2)
    161  –  pie chart    (datasource 2, grouped by "name")
    162  –  line chart   (datasource 6, echarts_timeseries_line)
    163  –  pie chart    (datasource 20, grouped by "phase")
    164  –  bar chart    (datasource 20, echarts_timeseries_bar)
"""
import httpx
import json
import asyncio

BASE_URL = "http://192.168.37.73:8088"
TOKEN_FILE = "modules/SupersetModule/.tokens/.superset_token_superset_main"

CHART_FIXES = {
    160: {
        "params": json.dumps({
            "datasource": "2__table",
            "datasource_type": "table",
            "viz_type": "table",
            "metrics": ["count"],
            "groupby": [],
            "all_columns": ["ds", "gender", "name", "num", "state"],
            "query_mode": "raw",
            "row_limit": 1000,
            "adhoc_filters": [],
            "order_desc": True,
            "table_timestamp_format": "smart_date",
            "show_cell_bars": True,
            "color_pn": True,
            "allow_render_html": True,
        }),
    },
    161: {
        "params": json.dumps({
            "datasource": "2__table",
            "datasource_type": "table",
            "viz_type": "pie",
            "groupby": ["name"],
            "metric": {
                "label": "Count",
                "expressionType": "SIMPLE",
                "column": None,
                "aggregate": "COUNT",
                "configType": "label"
            },
            "sort_by_metric": True,
            "show_labels_threshold": 5,
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "label_type": "key",
            "number_format": "SMART_NUMBER",
            "date_format": "smart_date",
            "show_labels": True,
            "labels_outside": True,
            "outerRadius": 70,
            "innerRadius": 30,
            "color_scheme": "supersetColors",
            "adhoc_filters": [],
        }),
    },
    162: {
        "params": json.dumps({
            "datasource": "6__table",
            "datasource_type": "table",
            "viz_type": "echarts_timeseries_line",
            "x_axis": "ds",
            "time_grain_sqla": "P1M",
            "metrics": ["count"],
            "groupby": [],
            "order_desc": True,
            "truncate_metric": True,
            "show_empty_columns": True,
            "comparison_type": "values",
            "annotation_layers": [],
            "forecastPeriods": 10,
            "forecastInterval": 0.8,
            "seriesType": "echarts_timeseries_line",
            "opacity": 0.2,
            "markerSize": 6,
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "x_axis_time_format": "smart_date",
            "rich_tooltip": True,
            "tooltipTimeFormat": "smart_date",
            "y_axis_format": "SMART_NUMBER",
            "truncateXAxis": True,
            "y_axis_bounds": [None, None],
            "color_scheme": "supersetColors",
            "adhoc_filters": [],
        }),
    },
    163: {
        "params": json.dumps({
            "datasource": "20__table",
            "datasource_type": "table",
            "viz_type": "pie",
            "groupby": ["phase"],
            "metric": {
                "label": "Count",
                "expressionType": "SIMPLE",
                "column": None,
                "aggregate": "COUNT",
                "configType": "label"
            },
            "sort_by_metric": True,
            "show_labels_threshold": 5,
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "label_type": "key",
            "number_format": "SMART_NUMBER",
            "date_format": "smart_date",
            "show_labels": True,
            "labels_outside": True,
            "outerRadius": 70,
            "innerRadius": 30,
            "color_scheme": "supersetColors",
            "adhoc_filters": [],
        }),
    },
    164: {
        "params": json.dumps({
            "datasource": "20__table",
            "datasource_type": "table",
            "viz_type": "echarts_timeseries_bar",
            "x_axis": "phase",
            "time_grain_sqla": "P1D",
            "metrics": ["count"],
            "groupby": [],
            "order_desc": True,
            "truncate_metric": True,
            "show_empty_columns": True,
            "comparison_type": "values",
            "annotation_layers": [],
            "forecastPeriods": 10,
            "forecastInterval": 0.8,
            "orientation": "vertical",
            "only_total": True,
            "x_axis_title_margin": 15,
            "y_axis_title_margin": 15,
            "y_axis_title_position": "middle",
            "sort_series_type": "alphabetical",
            "color_scheme": "supersetColors",
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
            "truncateXAxis": True,
            "y_axis_bounds": [None, None],
            "rich_tooltip": True,
            "tooltipTimeFormat": "smart_date",
            "adhoc_filters": [],
        }),
    },
}


async def fix_chart(client: httpx.AsyncClient, chart_id: int, new_params: str) -> dict:
    """Update a single chart with new params.

    Sends a ``PUT`` request to ``/api/v1/chart/<id>`` with the corrected
    ``params`` JSON blob. Returns a status dict indicating whether the
    patch succeeded.

    Args:
        client: An authenticated async HTTP client already configured with the
            Superset base URL, auth header, and CSRF header.
        chart_id: The numeric ID of the chart to patch.
        new_params: The JSON-serialized params dict that should replace the
            chart's current ``params`` value.

    Returns:
        A result dict with ``id`` and ``status`` keys. ``status`` is
        ``"ok"`` on success, ``"error"`` on failure (with a ``message``
        field containing the server's error response).

    Example:
        >>> result = await fix_chart(client, 160, '{"viz_type": "table"}')
        >>> print(result)
        {'id': 160, 'status': 'ok'}
    """
    # Send the PUT request to update only the params field of the chart
    resp = await client.put(
        f"{BASE_URL}/api/v1/chart/{chart_id}",
        json={"params": new_params},
    )
    # Check if the update succeeded (HTTP 200)
    if resp.status_code != 200:
        return {"id": chart_id, "status": "error", "message": resp.text}
    return {"id": chart_id, "status": "ok"}


async def main():
    """Apply targeted param fixes to the five broken charts (160–164).

    Orchestrates the repair flow:

    1. Loads the Superset auth token from disk.
    2. Fetches a CSRF token and attaches it to the client headers.
    3. Iterates over ``CHART_FIXES``, calling ``fix_chart`` for each
       chart ID.
    4. Prints per-chart status and a final summary.

    Returns:
        None

    Example:
        >>> asyncio.run(main())
        Fixing chart 160...
          ok
        Fixing chart 161...
          ok
        Done! OK: 5, Errors: 0
    """
    # --- Step 1: Load the auth token from the pre-stored file ---
    with open(TOKEN_FILE) as f:
        token = f.read().strip()

    # --- Step 2: Create the HTTP client and attach the auth token ---
    async with httpx.AsyncClient() as client:
        client.headers.update({"Authorization": f"Bearer {token}"})

        # --- Step 3: Fetch a CSRF token and attach it to every request ---
        csrf_resp = await client.get(f"{BASE_URL}/api/v1/security/csrf_token/")
        csrf_token = csrf_resp.json().get("result")
        client.headers.update({"X-CSRFToken": csrf_token})

        # --- Step 4: Fix each chart sequentially using CHART_FIXES mapping ---
        results = []
        for chart_id, fix in CHART_FIXES.items():
            print(f"Fixing chart {chart_id}...")
            result = await fix_chart(client, chart_id, fix["params"])
            results.append(result)
            print(f"  {result['status']}")

        # --- Step 5: Print a summary of the repair operation ---
        ok = sum(1 for r in results if r["status"] == "ok")
        err = sum(1 for r in results if r["status"] == "error")
        print(f"\nDone! OK: {ok}, Errors: {err}")

        if err:
            print("\nErrors:")
            for r in results:
                if r["status"] == "error":
                    print(f"  Chart {r['id']}: {r['message'][:200]}")


if __name__ == "__main__":
    asyncio.run(main())
