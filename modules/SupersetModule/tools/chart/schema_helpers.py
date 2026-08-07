"""
Schema parsing and markdown generation helpers.

Contains helper functions for _parse_schema and _build_markdown used by get_all_chart_schemas.
"""

import json
import time
from typing import Dict, Any, List


def parse_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a raw chart schema into categorized field lists."""
    properties = schema.get("properties", {})
    parsed_required = []

    if "required" in schema and isinstance(schema["required"], list):
        parsed_required = list(schema["required"])

    metric_fields = []
    groupby_fields = []
    other_fields = []

    for field_name, field_info in properties.items():
        if not isinstance(field_info, dict):
            other_fields.append(f"**{field_name}** (unknown)")
            continue
        field_type = str(field_info.get("type", "unknown"))
        description = field_info.get("description", "") or field_info.get("title", "")
        name_lower = field_name.lower()

        if any(kw in name_lower for kw in ["metric", "aggregate"]):
            metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
        elif any(kw in name_lower for kw in ["group", "series", "dimension", "category", "x_axis", "y_", "slice"]):
            groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
        elif name_lower not in ("datasource", "viz_type", "slice_name", "description", "id"):
            other_fields.append(f"**{field_name}** ({field_type}) - {description}")

    form_data = schema.get("form_data", {})
    if isinstance(form_data, dict):
        fd_props = form_data.get("properties", {})
        fd_required = form_data.get("required", [])
        if isinstance(fd_required, list):
            parsed_required.extend(fd_required)
        for field_name, field_info in fd_props.items():
            if not isinstance(field_info, dict):
                continue
            field_type = str(field_info.get("type", "unknown"))
            description = field_info.get("description", "") or field_info.get("title", "")
            name_lower = field_name.lower()
            if any(kw in name_lower for kw in ["metric", "aggregate"]):
                metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif any(kw in name_lower for kw in ["group", "series", "dimension", "x_", "y_"]):
                groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif name_lower not in ("datasource", "viz_type", "slice_name", "description"):
                other_fields.append(f"**{field_name}** ({field_type}) - {description}")

    return {
        "required": list(set(parsed_required)),
        "metric_fields": metric_fields,
        "groupby_fields": groupby_fields,
        "other_fields": other_fields,
    }


def build_markdown(all_schemas: List[Dict[str, Any]], cache_key: str) -> str:
    """Build a consolidated Markdown reference from parsed chart schemas."""
    lines = [
        "# Superset Chart Types - Complete Reference",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Source: Superset API ({cache_key})",
        "",
        "---",
        "",
        f"**Total chart types available: {len(all_schemas)}**",
        "",
        "## Quick Reference",
        "",
        "| # | Chart Type | Required Fields | Metric Fields | GroupBy Fields |",
        "|---|-----------|----------------|---------------|----------------|",
    ]

    for idx, item in enumerate(all_schemas, 1):
        chart_type = item["type"]
        parsed = item["parsed"]
        required_str = ", ".join(parsed["required"][:5]) if parsed["required"] else "See details"
        metric_count = len(parsed["metric_fields"])
        groupby_count = len(parsed["groupby_fields"])
        lines.append(f"| {idx} | `{chart_type}` | {required_str} | {metric_count} | {groupby_count} |")

    lines.extend(["", "---", "", "## Detailed Schemas", "", ""])

    for item in all_schemas:
        chart_type = item["type"]
        parsed = item["parsed"]
        raw = item.get("raw_schema", {})

        lines.append(f"### `{chart_type}`")
        lines.append("")

        if parsed["required"]:
            lines.append("**Required fields:**")
            for field in parsed["required"]:
                lines.append(f"- `{field}`")
            lines.append("")

        if parsed["metric_fields"]:
            lines.append("**Metric fields:**")
            for f in parsed["metric_fields"][:10]:
                lines.append(f"- {f}")
            if len(parsed["metric_fields"]) > 10:
                lines.append(f"- ... and {len(parsed['metric_fields']) - 10} more")
            lines.append("")

        if parsed["groupby_fields"]:
            lines.append("**GroupBy/Dimension fields:**")
            for f in parsed["groupby_fields"][:10]:
                lines.append(f"- {f}")
            if len(parsed["groupby_fields"]) > 10:
                lines.append(f"- ... and {len(parsed['groupby_fields']) - 10} more")
            lines.append("")

        if parsed["other_fields"]:
            lines.append("**Other fields:**")
            for f in parsed["other_fields"][:10]:
                lines.append(f"- {f}")
            if len(parsed["other_fields"]) > 10:
                lines.append(f"- ... and {len(parsed['other_fields']) - 10} more")
            lines.append("")

        form_data = raw.get("form_data", {})
        if isinstance(form_data, dict) and form_data:
            lines.append("**Form data properties (top 15):**")
            fd_props = form_data.get("properties", {})
            for field_name, field_info in list(fd_props.items())[:15]:
                if isinstance(field_info, dict):
                    field_type = str(field_info.get("type", "unknown"))
                    desc = field_info.get("description", "") or field_info.get("title", "")
                    lines.append(f"- `{field_name}`: {field_type} - {desc}")
            if len(fd_props) > 15:
                lines.append(f"- ... and {len(fd_props) - 15} more")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
