"""
Backward compatibility wrapper for dashboard package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.dashboard import (
    generate_dashboard,
    create_dashboard,
    update_dashboard,
    get_dashboard_info,
    get_dashboard_api_info,
    get_dashboard_creation_rules,
    bulk_link_charts,
    add_chart_to_existing_dashboard,
    transfer_dashboard,
    generate_simple_dashboard_layout,
    generate_robust_layout,
)
from modules.SupersetModule.tools.dashboard.layout import (
    _build_simple_layout,
)
from modules.SupersetModule.tools.dashboard.layout_helpers import (
    _add_chart_to_position_json,
    _extract_chart_ids_from_position_json,
    _validate_position_json_structure,
)
from modules.SupersetModule.tools.dashboard.chart_validators import (
    _validate_charts_exist,
    _validate_chart_data_endpoint,
    _get_chart_info,
    _pre_validate_chart_data,
)

__all__ = [
    'generate_dashboard', 'create_dashboard', 'update_dashboard',
    'get_dashboard_info', 'get_dashboard_api_info',
    'get_dashboard_creation_rules', 'bulk_link_charts',
    'add_chart_to_existing_dashboard', 'transfer_dashboard',
    'generate_simple_dashboard_layout', 'generate_robust_layout',
    '_build_simple_layout', '_add_chart_to_position_json',
    '_extract_chart_ids_from_position_json',
    '_validate_position_json_structure',
    '_validate_charts_exist', '_validate_chart_data_endpoint',
    '_get_chart_info', '_pre_validate_chart_data',
]
