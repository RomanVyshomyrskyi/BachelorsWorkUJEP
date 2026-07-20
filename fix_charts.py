"""
Fix broken charts by updating viz_type and metric names.

This script fixes charts that were created with the old code that didn't
resolve viz_type mappings (e.g., "bar" instead of "echarts_timeseries_bar").
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
    """Fix a single chart's viz_type."""
    # Get chart
    async with httpx.AsyncClient() as client:
        # Fetch chart
        resp = await client.get(f"{base_url}/api/v1/chart/{chart_id}")
        if resp.status_code != 200:
            return {"id": chart_id, "status": "error", "message": f"Failed to fetch: {resp.text}"}
        
        chart = resp.json()["result"]
        old_viz = chart.get("viz_type", "")
        
        # Parse params
        params = json.loads(chart.get("params", "{}"))
        old_params_viz = params.get("viz_type", "")
        
        # Check if fix needed
        if old_viz not in VIZ_TYPE_MAP and old_params_viz not in VIZ_TYPE_MAP:
            return {"id": chart_id, "status": "ok", "viz_type": old_viz}
        
        # Determine the correct viz_type
        new_viz = VIZ_TYPE_MAP.get(old_viz, VIZ_TYPE_MAP.get(old_params_viz, old_viz))
        
        # Update params
        if "viz_type" in params:
            params["viz_type"] = new_viz
        
        # Update chart
        update_payload = {
            "viz_type": new_viz,
            "params": json.dumps(params),
        }
        
        update_resp = await client.put(
            f"{base_url}/api/v1/chart/{chart_id}",
            json=update_payload,
        )
        
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
    import os
    # Get Superset credentials from environment or use defaults
    superset_url = "http://192.168.37.73:8088"
    
    # Try to load token from file
    token_file = os.path.join(os.path.dirname(__file__), "modules", "SupersetModule", ".tokens", ".superset_token_superset_main")
    token = None
    if os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()
            print(f"Loaded token from {token_file}")
    
    async with httpx.AsyncClient() as client:
        if token:
            client.headers.update({"Authorization": f"Bearer {token}"})
        
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
        
        # Fetch all charts
        resp = await client.get(f"{superset_url}/api/v1/chart/")
        if resp.status_code != 200:
            print(f"Failed to fetch charts: {resp.text}")
            return
        
        charts = resp.json()["result"]["charts"]
        print(f"Found {len(charts)} charts")
        
        # Find charts that need fixing
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
        
        # Fix charts
        print("\nFixing charts...")
        results = await asyncio.gather(*[fix_chart_viz_type(superset_url, cid) for cid in needs_fix])
        
        # Print summary
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
