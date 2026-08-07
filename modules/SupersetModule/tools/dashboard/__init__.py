"""Dashboard module for Apache Superset operations.

Re-exports all public functions from the submodules to maintain
backward compatibility with existing imports.
"""
from modules.SupersetModule.tools.dashboard.layout import (
    generate_simple_dashboard_layout,
    generate_robust_layout,
    _build_simple_layout,
)

from modules.SupersetModule.tools.dashboard.layout_helpers import (
    _add_chart_to_position_json,
    _extract_chart_ids_from_position_json,
    _validate_position_json_structure,
)

from modules.SupersetModule.tools.dashboard.crud import (
    create_dashboard,
    update_dashboard,
    get_dashboard_info,
    get_dashboard_api_info,
    get_dashboard_creation_rules,
)

from modules.SupersetModule.tools.dashboard.linking import (
    bulk_link_charts,
    add_chart_to_existing_dashboard,
)

from modules.SupersetModule.tools.dashboard.generation import (
    generate_dashboard,
)

from modules.SupersetModule.tools.dashboard.chart_validators import (
    _validate_charts_exist,
    _validate_chart_data_endpoint,
    _get_chart_info,
    _pre_validate_chart_data,
)

from modules.SupersetModule.tools.dashboard.helpers import (
    _build_simple_layout_json,
    _build_robust_layout_json,
)

from modules.SupersetModule.tools.dashboard.transfer import (
    transfer_dashboard,
)

__all__ = [
    "generate_simple_dashboard_layout",
    "generate_robust_layout",
    "_build_simple_layout",
    "_add_chart_to_position_json",
    "_extract_chart_ids_from_position_json",
    "_validate_position_json_structure",
    "create_dashboard",
    "update_dashboard",
    "get_dashboard_info",
    "get_dashboard_api_info",
    "get_dashboard_creation_rules",
    "bulk_link_charts",
    "add_chart_to_existing_dashboard",
    "generate_dashboard",
    "_validate_charts_exist",
    "_validate_chart_data_endpoint",
    "_get_chart_info",
    "_pre_validate_chart_data",
    "_build_simple_layout_json",
    "_build_robust_layout_json",
    "transfer_dashboard",
]
