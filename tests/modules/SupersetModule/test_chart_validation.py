"""
Tests for chart parameter validation and auto-fixing.
"""
import pytest

from modules.SupersetModule.superset_validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
)


class TestValidateChartParams:
    """Test validation function catches common mistakes."""

    def test_pie_with_metrics_array_is_error(self):
        """Pie chart with 'metrics' (plural) should be flagged as error."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metrics": [
                {
                    "aggregate": "SUM",
                    "column": {"column_name": "sales"},
                    "expressionType": "SIMPLE",
                }
            ],
        }
        errors = validate_chart_params("pie", params)
        assert len(errors) == 1
        assert "metric" in errors[0]

    def test_pie_with_metric_object_is_valid(self):
        """Pie chart with 'metric' (singular) AdHocMetricObject should be valid."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metric": {
                "aggregate": "SUM",
                "column": {"column_name": "sales"},
                "expressionType": "SIMPLE",
                "label": "SUM(sales)",
            },
        }
        errors = validate_chart_params("pie", params)
        assert len(errors) == 0

    def test_pie_with_string_metric_is_accepted(self):
        """Pie chart with string metric is accepted (auto-fix will convert)."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metric": "SUM(sales)",
        }
        errors = validate_chart_params("pie", params)
        assert len(errors) == 0

    def test_big_number_with_string_metric_is_valid(self):
        """Big number with string metric is valid (string metrics expected)."""
        params = {
            "viz_type": "big_number",
            "metric": "count",
        }
        errors = validate_chart_params("big_number", params)
        assert len(errors) == 0

    def test_scatter_with_flat_column_name_is_error(self):
        """Scatter with flat column_name should be flagged."""
        params = {
            "viz_type": "scatter",
            "x": {"column_name": "SP_DYN_CBRT_IN", "expressionType": "DIMENSION"},
            "y": {
                "aggregate": "AVG",
                "column": {"column_name": "SP_DYN_LE00_IN"},
                "expressionType": "SIMPLE",
            },
        }
        errors = validate_chart_params("scatter", params)
        assert len(errors) == 1
        assert "'x'" in errors[0]

    def test_scatter_with_nested_column_is_valid(self):
        """Scatter with nested column should be valid."""
        params = {
            "viz_type": "scatter",
            "x": {"column": {"column_name": "SP_DYN_CBRT_IN"}, "expressionType": "DIMENSION"},
            "y": {
                "aggregate": "AVG",
                "column": {"column_name": "SP_DYN_LE00_IN"},
                "expressionType": "SIMPLE",
            },
        }
        errors = validate_chart_params("scatter", params)
        assert len(errors) == 0

    def test_metric_missing_column_key_is_error(self):
        """Metric without 'column' key should be flagged."""
        params = {
            "viz_type": "pie",
            "metric": {"aggregate": "SUM", "column_name": "sales", "expressionType": "SIMPLE"},
        }
        errors = validate_chart_params("pie", params)
        assert len(errors) >= 1

    def test_metric_missing_aggregate_is_error(self):
        """Metric without 'aggregate' key should be flagged."""
        params = {
            "viz_type": "pie",
            "metric": {
                "column": {"column_name": "sales"},
                "expressionType": "SIMPLE",
            },
        }
        errors = validate_chart_params("pie", params)
        assert any("aggregate" in e for e in errors)

    def test_metric_missing_expression_type_is_error(self):
        """Metric without 'expressionType' key should be flagged."""
        params = {
            "viz_type": "pie",
            "metric": {
                "aggregate": "SUM",
                "column": {"column_name": "sales"},
            },
        }
        errors = validate_chart_params("pie", params)
        assert any("expressionType" in e for e in errors)

    def test_table_with_metric_singular_is_error(self):
        """Table chart with 'metric' (singular) should be flagged."""
        params = {
            "viz_type": "table",
            "metric": {"aggregate": "COUNT", "column": {"column_name": "count"}},
        }
        errors = validate_chart_params("table", params)
        assert any("metrics" in e for e in errors)


class TestAutoFixChartParams:
    """Test auto-fix function corrects common mistakes."""

    def test_fix_pie_metrics_to_metric(self):
        """Auto-fix pie chart metrics array to metric object."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metrics": [
                {
                    "aggregate": "SUM",
                    "column": {"column_name": "sales"},
                    "expressionType": "SIMPLE",
                }
            ],
        }
        fixed = auto_fix_chart_params("pie", params)
        assert "metric" in fixed
        assert "metrics" not in fixed
        assert fixed["metric"]["aggregate"] == "SUM"
        assert fixed["metric"]["column"]["column_name"] == "sales"

    def test_fix_pie_string_metric_to_object(self):
        """Auto-fix pie chart string metric to AdHocMetricObject."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metric": "SUM(sales)",
        }
        fixed = auto_fix_chart_params("pie", params)
        assert isinstance(fixed["metric"], dict)
        assert fixed["metric"]["aggregate"] == "SUM"
        assert fixed["metric"]["column"]["column_name"] == "sales"
        assert fixed["metric"]["expressionType"] == "SIMPLE"

    def test_fix_big_number_string_metric(self):
        """Big number string metric should remain as string (valid format)."""
        params = {
            "viz_type": "big_number",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("big_number", params)
        assert isinstance(fixed["metric"], str)
        assert fixed["metric"] == "count"

    def test_fix_scatter_flat_column_name(self):
        """Auto-fix scatter flat column_name to nested column object."""
        params = {
            "viz_type": "scatter",
            "x": {"column_name": "SP_DYN_CBRT_IN", "expressionType": "DIMENSION"},
            "y": {
                "aggregate": "AVG",
                "column": {"column_name": "SP_DYN_LE00_IN"},
                "expressionType": "SIMPLE",
            },
        }
        fixed = auto_fix_chart_params("scatter", params)
        assert "column_name" not in fixed["x"]
        assert "column" in fixed["x"]
        assert fixed["x"]["column"]["column_name"] == "SP_DYN_CBRT_IN"
        assert fixed["x"]["expressionType"] == "DIMENSION"

    def test_fix_metric_missing_column_wrapper(self):
        """Auto-fix metric with column_name at top level."""
        params = {
            "viz_type": "pie",
            "metric": {"aggregate": "SUM", "column_name": "sales", "expressionType": "SIMPLE"},
        }
        fixed = auto_fix_chart_params("pie", params)
        assert "column_name" not in fixed["metric"]
        assert "column" in fixed["metric"]
        assert fixed["metric"]["column"]["column_name"] == "sales"

    def test_fix_metric_missing_aggregate(self):
        """Auto-fix metric missing aggregate field."""
        params = {
            "viz_type": "pie",
            "metric": {"column": {"column_name": "sales"}, "expressionType": "SIMPLE"},
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["metric"]["aggregate"] == "AVG"

    def test_fix_metric_missing_expression_type(self):
        """Auto-fix metric missing expressionType field."""
        params = {
            "viz_type": "pie",
            "metric": {"aggregate": "SUM", "column": {"column_name": "sales"}},
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["metric"]["expressionType"] == "SIMPLE"

    def test_no_changes_when_already_valid(self):
        """Valid params should not be changed."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metric": {
                "aggregate": "SUM",
                "column": {"column_name": "sales"},
                "expressionType": "SIMPLE",
                "label": "SUM(sales)",
            },
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed == params


class TestFormatErrorSummary:
    """Test error summary formatting."""

    def test_empty_errors(self):
        """Empty error list returns success message."""
        result = format_error_summary([])
        assert "No errors found" in result

    def test_single_error(self):
        """Single error returns formatted message."""
        errors = ["Something is wrong"]
        result = format_error_summary(errors)
        assert "1 error" in result
        assert "Something is wrong" in result

    def test_multiple_errors(self):
        """Multiple errors return numbered list."""
        errors = ["Error 1", "Error 2", "Error 3"]
        result = format_error_summary(errors)
        assert "3 error" in result
        assert "Error 1" in result
        assert "Error 2" in result
        assert "Error 3" in result


class TestSankeyValidation:
    """Test Sankey chart parameter validation."""

    def test_sankey_missing_source_is_error(self):
        """Sankey without 'source' field should be flagged."""
        params = {
            "viz_type": "sankey_v2",
            "target": "channel_2",
            "metric": "count",
        }
        errors = validate_chart_params("sankey_v2", params)
        assert len(errors) == 1
        assert "source" in errors[0]

    def test_sankey_missing_target_is_error(self):
        """Sankey without 'target' field should be flagged."""
        params = {
            "viz_type": "sankey_v2",
            "source": "channel_1",
            "metric": "count",
        }
        errors = validate_chart_params("sankey_v2", params)
        assert len(errors) == 1
        assert "target" in errors[0]

    def test_sankey_missing_both_source_and_target(self):
        """Sankey without both fields should report both errors."""
        params = {
            "viz_type": "sankey_v2",
            "metric": "count",
        }
        errors = validate_chart_params("sankey_v2", params)
        assert len(errors) == 2
        assert any("source" in e for e in errors)
        assert any("target" in e for e in errors)

    def test_sankey_with_both_fields_is_valid(self):
        """Sankey with source and target should be valid."""
        params = {
            "viz_type": "sankey_v2",
            "source": "channel_1",
            "target": "channel_2",
            "metric": "count",
        }
        errors = validate_chart_params("sankey_v2", params)
        assert len(errors) == 0


class TestSankeyAutoFix:
    """Test Sankey auto-fix suggests cycle-breaking SQL."""

    def test_sankey_auto_fix_suggests_cycle_sql(self):
        """Auto-fix should suggest cycle-breaking SQL for Sankey."""
        params = {
            "viz_type": "sankey_v2",
            "source": "channel_1",
            "target": "channel_2",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("sankey_v2", params)
        assert fixed.get("_cycle_fix_suggested") is True
        assert "_cycle_fix_sql" in fixed
        assert "channel_1 < channel_2" in fixed["_cycle_fix_sql"]
        assert "channel_1 <> channel_2" in fixed["_cycle_fix_sql"]

    def test_sankey_auto_fix_with_custom_columns(self):
        """Auto-fix should use actual column names in SQL suggestion."""
        params = {
            "viz_type": "sankey_v2",
            "source": "source_node",
            "target": "target_node",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("sankey_v2", params)
        assert "source_node < target_node" in fixed["_cycle_fix_sql"]
        assert "source_node <> target_node" in fixed["_cycle_fix_sql"]


class TestSankeyMetricsValidation:
    """Test _validate_metrics_against_dataset function."""

    def test_metric_exists_in_dataset(self):
        """Valid metric should pass validation."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "count", "viz_type": "sankey_v2"}
        dataset_metrics = [{"metric_name": "count", "expression": "COUNT(*)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "sankey_v2")
        assert missing == []

    def test_metric_not_in_dataset(self):
        """Missing metric should be detected."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "SUM(sales)", "viz_type": "pie"}
        dataset_metrics = [{"metric_name": "count", "expression": "COUNT(*)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "pie")
        assert any("SUM(sales)" in e for e in missing)

    def test_adhoc_metric_with_column_name(self):
        """AdHocMetricObject column should be checked against dataset."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {
            "metric": {
                "aggregate": "SUM",
                "column": {"column_name": "sales"},
                "expressionType": "SIMPLE",
            }
        }
        dataset_metrics = [{"metric_name": "SUM(sales)", "expression": "SUM(sales)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "pie")
        assert missing == []

    def test_multiple_metrics_validation(self):
        """Multiple metrics in array should all be validated."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {
            "metrics": [
                {"aggregate": "SUM", "column": {"column_name": "revenue"}, "expressionType": "SIMPLE"},
                {"aggregate": "SUM", "column": {"column_name": "cost"}, "expressionType": "SIMPLE"},
            ],
            "viz_type": "echarts_timeseries_line",
        }
        dataset_metrics = [
            {"metric_name": "SUM(revenue)", "expression": "SUM(revenue)"},
            {"metric_name": "count", "expression": "COUNT(*)"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line")
        assert any("SUM(cost)" in e for e in missing)
        assert not any("SUM(revenue)" in e for e in missing)


class TestChartIdExtraction:
    """Test _extract_chart_ids_from_position_json function."""

    def test_extract_ids_from_meta_chart_id(self):
        """Chart IDs should be extracted from meta.chartId (our layout format)."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        position_json = {
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW1"]},
            "ROW1": {
                "type": "ROW",
                "id": "ROW1",
                "children": ["CHART-uuid-100"],
            },
            "CHART-uuid-100": {
                "type": "CHART",
                "id": "CHART-uuid-100",
                "meta": {"chartId": 100},
            },
        }
        ids = _extract_chart_ids_from_position_json(position_json)
        assert 100 in ids

    def test_extract_ids_from_slice_id(self):
        """Chart IDs should be extracted from slice_id (legacy format)."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        position_json = {
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW1"]},
            "ROW1": {
                "type": "ROW",
                "id": "ROW1",
                "children": [{"type": "CHART", "slice_id": 1}, {"type": "CHART", "slice_id": 2}],
            },
        }
        ids = _extract_chart_ids_from_position_json(position_json)
        assert 1 in ids
        assert 2 in ids

    def test_extract_ids_from_string(self):
        """Chart IDs should be extracted from position JSON string."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        position_json = '{"ROW1": {"type": "ROW", "children": [{"type": "CHART", "meta": {"chartId": 42}}]}}'
        ids = _extract_chart_ids_from_position_json(position_json)
        assert 42 in ids

    def test_extract_ids_empty(self):
        """Empty position JSON should return empty list."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        ids = _extract_chart_ids_from_position_json({})
        assert ids == []

    def test_extract_ids_nested(self):
        """Chart IDs at any depth should be extracted."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        position_json = {
            "a": {"b": {"c": [{"meta": {"chartId": 10}}, {"meta": {"chartId": 20}}]}}
        }
        ids = _extract_chart_ids_from_position_json(position_json)
        assert 10 in ids
        assert 20 in ids

    def test_extract_ids_deduplicates(self):
        """Duplicate chart IDs should be deduplicated."""
        from modules.SupersetModule.tools.dashboards import _extract_chart_ids_from_position_json
        
        position_json = {
            "ROW1": {"type": "ROW", "children": [
                {"type": "CHART", "meta": {"chartId": 5}},
                {"type": "CHART", "meta": {"chartId": 5}},
            ]},
        }
        ids = _extract_chart_ids_from_position_json(position_json)
        assert ids == [5]


class TestBigNumberAutoFix:
    """Test big_number auto-fix for dashboard rendering."""

    def test_big_number_gets_temporal_field(self):
        """Big number should get granularity_sqla hint."""
        params = {
            "viz_type": "big_number",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("big_number", params)
        assert "_needs_temporal_check" in fixed or "granularity_sqla" in fixed

    def test_big_number_gets_time_range(self):
        """Big number should get time_range."""
        params = {
            "viz_type": "big_number",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("big_number", params)
        assert fixed.get("time_range") == "100 years ago : now"
        assert fixed.get("adhoc_filters") == []


class TestPieChartGroupbyFix:
    """Test pie chart groupby conversion to array."""

    def test_pie_groupby_becomes_array(self):
        """Pie chart groupby string should become array in dashboard context."""
        params = {
            "viz_type": "pie",
            "groupby": "gender",
            "metric": "count",
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["groupby"] == ["gender"]

    def test_pie_groupby_already_array(self):
        """Pie chart groupby already as array should not change."""
        params = {
            "viz_type": "pie",
            "groupby": ["region"],
            "metric": "count",
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["groupby"] == ["region"]


class TestNullColumnFix:
    """Test null column_name fix in AdHocMetricObject."""

    def test_null_column_uses_top_level_groupby(self):
        """Null column_name should be filled from top-level groupby."""
        params = {
            "viz_type": "pie",
            "groupby": "gender",
            "metric": {
                "aggregate": "COUNT",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
            },
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["metric"]["column"]["column_name"] == "gender"

    def test_null_column_with_groupby_in_metric(self):
        """Null column_name should be filled from metric's groupby field."""
        params = {
            "viz_type": "pie",
            "metric": {
                "aggregate": "COUNT",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
                "groupby": "category",
            },
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["metric"]["column"]["column_name"] == "category"

    def test_null_column_falls_back_to_count(self):
        """Null column_name should fall back to 'count' if no groupby."""
        params = {
            "viz_type": "pie",
            "metric": {
                "aggregate": "COUNT",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
            },
        }
        fixed = auto_fix_chart_params("pie", params)
        assert fixed["metric"]["column"]["column_name"] == "count"


class TestDatasourceCompatibilityValidation:
    """Test validate_datasource_compatibility function."""
    
    def test_world_map_requires_entity(self):
        """World map should fail if entity field is missing."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "world_map", "metric": "count"}
        errors = validate_datasource_compatibility("world_map", params)
        
        assert len(errors) > 0
        assert "entity" in errors[0].lower()
    
    def test_world_map_passes_with_entity(self):
        """World map should pass when entity field is provided."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "world_map", "entity": "country_code", "metric": "count"}
        errors = validate_datasource_compatibility("world_map", params)
        
        assert errors == []
    
    def test_heatmap_requires_groupby(self):
        """Heatmap v2 should fail if groupby field is missing."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "heatmap_v2", "x_axis": "date"}
        errors = validate_datasource_compatibility("heatmap_v2", params)
        
        assert len(errors) > 0
        assert "groupby" in errors[0].lower()
    
    def test_heatmap_passes_with_groupby(self):
        """Heatmap v2 should pass when groupby is provided."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "heatmap_v2", "x_axis": "date", "groupby": "category"}
        errors = validate_datasource_compatibility("heatmap_v2", params)
        
        assert errors == []
    
    def test_parallel_requires_dimensions(self):
        """Parallel chart should fail if dimensions field is missing."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "parallel"}
        errors = validate_datasource_compatibility("parallel", params)
        
        assert len(errors) > 0
        assert "dimensions" in errors[0].lower()
    
    def test_parallel_passes_with_dimensions(self):
        """Parallel chart should pass when dimensions are provided."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "parallel", "dimensions": ["col1", "col2"]}
        errors = validate_datasource_compatibility("parallel", params)
        
        assert errors == []
    
    def test_big_number_trendline_requires_temporal_x_axis(self):
        """Big number with trendline should fail if x_axis is not temporal."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "big_number", "show_trend_line": True, "x_axis": "status"}
        
        dataset_columns = [
            {"column_name": "status", "type": "VARCHAR"},
        ]
        
        errors = validate_datasource_compatibility("big_number", params, dataset_columns)
        
        assert len(errors) > 0
        assert "not a date/time" in errors[0].lower() or "trendline" in errors[0].lower()
    
    def test_big_number_trendline_passes_with_temporal_x_axis(self):
        """Big number with trendline should pass with temporal x_axis."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "big_number", "show_trend_line": True, "x_axis": "created_at"}
        
        dataset_columns = [
            {"column_name": "created_at", "type": "DATETIME"},
        ]
        
        errors = validate_datasource_compatibility("big_number", params, dataset_columns)
        
        assert errors == []
    
    def test_unrecognized_viz_type_has_no_requirements(self):
        """Unknown viz types should return no errors."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "fake_chart"}
        errors = validate_datasource_compatibility("fake_chart", params)
        
        assert errors == []
    
    def test_timeseries_prefers_temporal_x_axis(self):
        """Time series charts warn if x_axis is not temporal."""
        from modules.SupersetModule.superset_validation import validate_datasource_compatibility
        
        params = {"viz_type": "echarts_timeseries_line", "x_axis": "order_id"}
        
        dataset_columns = [
            {"column_name": "order_id", "type": "INTEGER"},
        ]
        
        errors = validate_datasource_compatibility("echarts_timeseries_line", params, dataset_columns)
        
        assert len(errors) > 0
        assert "not a date/time" in errors[0].lower()


class TestNullColumnNameChecks:
    """Tests for null column_name detection and auto-fix."""

    def test_adhoc_metric_null_column_name_returns_false(self):
        """_is_adhoc_metric_object should reject null column_name."""
        from modules.SupersetModule.superset_validation import _is_adhoc_metric_object

        val = {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"}
        assert not _is_adhoc_metric_object(val)

    def test_adhoc_metric_empty_column_name_returns_false(self):
        """_is_adhoc_metric_object should reject empty column_name string."""
        from modules.SupersetModule.superset_validation import _is_adhoc_metric_object

        val = {"aggregate": "SUM", "column": {"column_name": ""}, "expressionType": "SIMPLE"}
        assert not _is_adhoc_metric_object(val)

    def test_adhoc_metric_missing_column_key_returns_false(self):
        """_is_adhoc_metric_object should reject missing column key."""
        from modules.SupersetModule.superset_validation import _is_adhoc_metric_object

        val = {"aggregate": "SUM", "column_name": "sales", "expressionType": "SIMPLE"}
        assert not _is_adhoc_metric_object(val)

    def test_adhoc_metric_valid_column_name_returns_true(self):
        """_is_adhoc_metric_object should accept valid column_name."""
        from modules.SupersetModule.superset_validation import _is_adhoc_metric_object

        val = {"aggregate": "SUM", "column": {"column_name": "sales"}, "expressionType": "SIMPLE"}
        assert _is_adhoc_metric_object(val)

    def test_big_number_total_null_metric_errors(self):
        """Single string metric type with null column in dict metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
        }
        errors = validate_chart_params("big_number_total", params)
        assert len(errors) >= 1

    def test_big_number_total_undefined_string_errors(self):
        """Single string metric type with 'undefined' as metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": "undefined",
        }
        errors = validate_chart_params("big_number_total", params)
        assert len(errors) >= 1

    def test_big_number_total_null_string_errors(self):
        """Single string metric type with 'null' as metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": "null",
        }
        errors = validate_chart_params("big_number_total", params)
        assert len(errors) >= 1

    def test_big_number_total_none_string_errors(self):
        """Single string metric type with 'none' as metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": "none",
        }
        errors = validate_chart_params("big_number_total", params)
        assert len(errors) >= 1

    def test_big_number_total_count_string_passes(self):
        """Single string metric type with 'count' as metric should pass."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": "count",
        }
        errors = validate_chart_params("big_number_total", params)
        assert errors == []

    def test_timeseries_null_metric_errors(self):
        """Array metric type with null column in dict metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": [
                {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
            ],
        }
        errors = validate_chart_params("echarts_timeseries_line", params)
        assert len(errors) >= 1

    def test_timeseries_undefined_string_errors(self):
        """Array metric type with 'undefined' as metric string should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["undefined"],
        }
        errors = validate_chart_params("echarts_timeseries_line", params)
        assert len(errors) >= 1

    def test_timeseries_valid_metric_passes(self):
        """Array metric type with valid metric should pass."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["SUM(sales)"],
        }
        errors = validate_chart_params("echarts_timeseries_line", params)
        assert errors == []

    def test_auto_fix_null_column_name_uses_groupby_fallback(self):
        """Auto-fix should replace null column_name with groupby first entry."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "big_number_total",
            "groupby": "region",
            "metric": {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
        }
        fixed = auto_fix_chart_params("big_number_total", params)
        assert fixed["metric"]["column"]["column_name"] == "region"

    def test_auto_fix_null_column_name_falls_back_to_count(self):
        """Auto-fix should replace null column_name with 'count' if no groupby."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "big_number_total",
            "metric": {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
        }
        fixed = auto_fix_chart_params("big_number_total", params)
        assert fixed["metric"]["column"]["column_name"] == "count"

    def test_auto_fix_null_column_name_array_metric(self):
        """Auto-fix should replace null column_name in array metrics."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "groupby": "category",
            "metrics": [
                {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
            ],
        }
        fixed = auto_fix_chart_params("echarts_timeseries_line", params)
        assert fixed["metrics"][0]["column"]["column_name"] == "category"


class TestPositionJsonStructure:
    """Test _validate_position_json_structure function."""

    def test_valid_structure_returns_no_errors(self):
        """Valid position JSON with chartId should return no errors."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW1"]},
            "ROW1": {"type": "ROW", "id": "ROW1", "children": ["CHART-uuid-100"], "parents": ["GRID_ID"]},
            "CHART-uuid-100": {
                "type": "CHART",
                "id": "CHART-uuid-100",
                "children": [],
                "parents": ["ROW1"],
                "meta": {"chartId": 100, "width": 6, "height": 50},
            },
        }
        errors = _validate_position_json_structure(pos)
        assert errors == []

    def test_missing_dashboard_version_key(self):
        """Missing DASHBOARD_VERSION_KEY should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {
            "ROOT_ID": {"type": "ROOT", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "children": []},
        }
        errors = _validate_position_json_structure(pos)
        assert any("DASHBOARD_VERSION_KEY" in e for e in errors)

    def test_missing_root_id(self):
        """Missing ROOT_ID should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {"DASHBOARD_VERSION_KEY": "v2"}
        errors = _validate_position_json_structure(pos)
        assert any("ROOT_ID" in e for e in errors)

    def test_chart_without_chart_id_errors(self):
        """CHART component without meta.chartId should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "children": ["ROW1"]},
            "ROW1": {"type": "ROW", "id": "ROW1", "children": ["CHART-1"]},
            "CHART-1": {
                "type": "CHART",
                "id": "CHART-1",
                "children": [],
                "parents": ["ROW1"],
                "meta": {},
            },
        }
        errors = _validate_position_json_structure(pos)
        assert any("chartId" in e for e in errors)

    def test_chart_under_grid_id_errors(self):
        """CHART placed directly under GRID_ID should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "children": ["CHART-1"]},
            "CHART-1": {
                "type": "CHART",
                "id": "CHART-1",
                "children": [],
                "parents": ["GRID_ID"],
                "meta": {"chartId": 1},
            },
        }
        errors = _validate_position_json_structure(pos)
        assert any("GRID_ID" in e for e in errors)

    def test_component_missing_children(self):
        """Component without children field should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "children": ["ROW1"]},
            "ROW1": {"type": "ROW", "id": "ROW1"},
        }
        errors = _validate_position_json_structure(pos)
        assert any("children" in e for e in errors)

    def test_invalid_json_string_errors(self):
        """Non-JSON string should error."""
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        errors = _validate_position_json_structure("not valid json{{{")
        assert len(errors) >= 1

    def test_valid_json_string_passes(self):
        """Valid JSON string should parse and validate."""
        import json
        from modules.SupersetModule.tools.dashboards import _validate_position_json_structure
        
        pos_json = json.dumps({
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "children": ["ROW1"]},
            "ROW1": {"type": "ROW", "id": "ROW1", "children": ["CHART-1"], "parents": ["GRID_ID"]},
            "CHART-1": {
                "type": "CHART",
                "id": "CHART-1",
                "children": [],
                "parents": ["ROW1"],
                "meta": {"chartId": 42},
            },
        })
        errors = _validate_position_json_structure(pos_json)
        assert errors == []


class TestMetricsColumnFallback:
    """Tests for _validate_metrics_against_dataset column fallback logic."""

    def test_empty_metrics_with_valid_column_passes(self):
        """When dataset_metrics is empty, valid column from string metric should pass."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "SUM(sales)"}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "sales", "type": "DOUBLE PRECISION"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert missing == []

    def test_empty_metrics_with_missing_column_errors(self):
        """When dataset_metrics is empty, missing column from string metric should error."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "SUM(num)"}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "sales", "type": "DOUBLE PRECISION"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert any("num" in e for e in missing)

    def test_varchar_column_with_sum_errors(self):
        """SUM on a VARCHAR column should be flagged as type error."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "SUM(category)"}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "category", "type": "VARCHAR"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert any("sum()" in e.lower() and "varchar" in e.lower() for e in missing)

    def test_string_column_with_avg_errors(self):
        """AVG on a TEXT column should be flagged as type error."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "AVG(description)"}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "description", "type": "TEXT"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert any("avg()" in e.lower() and "text" in e.lower() for e in missing)

    def test_count_on_numeric_column_passes(self):
        """COUNT on any column type should pass (no type restriction)."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "COUNT(category)"}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "category", "type": "VARCHAR"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert missing == []

    def test_count_count_rejected(self):
        """COUNT(count) should be rejected with suggestion."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "COUNT(count)"}
        dataset_metrics = [{"metric_name": "count", "expression": "COUNT(*)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line")
        assert any("COUNT" in e for e in missing)

    def test_bare_count_passes(self):
        """Bare 'count' (no parens) should pass as valid built-in."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "count"}
        dataset_metrics = [{"metric_name": "count", "expression": "COUNT(*)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line")
        assert missing == []

    def test_count_distinct_count_rejected(self):
        """COUNT_DISTINCT(count) should be rejected with suggestion."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "COUNT_DISTINCT(count)"}
        dataset_metrics = [{"metric_name": "count", "expression": "COUNT(*)"}]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line")
        assert any("COUNT" in e for e in missing)

    def test_no_columns_no_metrics_errors(self):
        """When neither dataset_metrics nor dataset_columns exist, validation blocks."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "SUM(something)"}
        missing = _validate_metrics_against_dataset(params, [], "echarts_timeseries_line")
        assert len(missing) >= 1
        assert any("schema" in e.lower() or "columns" in e.lower() for e in missing)

    def test_bare_count_without_dataset_metrics_passes(self):
        """Bare 'count' should pass even without dataset metrics."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metric": "count"}
        missing = _validate_metrics_against_dataset(params, [], "echarts_timeseries_line")
        assert missing == []

    def test_metrics_array_with_column_fallback(self):
        """Array metrics should use column fallback when no predefined metrics."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metrics": ["SUM(sales)", "count"]}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "sales", "type": "DOUBLE PRECISION"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert missing == []

    def test_type_mismatch_in_array_metrics(self):
        """Array metrics with type mismatch should error."""
        from modules.SupersetModule.tools.charts import _validate_metrics_against_dataset
        
        params = {"metrics": ["SUM(name)", "COUNT(id)"]}
        dataset_metrics = []
        dataset_columns = [
            {"column_name": "name", "type": "VARCHAR"},
            {"column_name": "id", "type": "INTEGER"},
        ]
        missing = _validate_metrics_against_dataset(params, dataset_metrics, "echarts_timeseries_line", dataset_columns)
        assert any("sum()" in e.lower() and "name" in e.lower() for e in missing)
        assert not any("COUNT(id)" in e for e in missing)  # COUNT on int is fine


class TestMetricStringFormatValidation:
    """Test _validate_metric_string_format function."""

    def test_valid_count_passes(self):
        """Bare 'count' should pass syntax check."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        errors = _validate_metric_string_format({"metric": "count"})
        assert errors == []

    def test_valid_sum_passes(self):
        """Valid SUM(sales) should pass syntax check."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        errors = _validate_metric_string_format({"metric": "SUM(sales)"})
        assert errors == []

    def test_invalid_format_errors(self):
        """Malformed metric string should error."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        errors = _validate_metric_string_format({"metric": "blah blah"})
        assert len(errors) >= 1
        assert any("invalid format" in e.lower() for e in errors)

    def test_missing_column_name_in_dict_errors(self):
        """Dict metric with null column_name should error."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        params = {
            "metric": {
                "aggregate": "SUM",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
            }
        }
        errors = _validate_metric_string_format(params)
        assert len(errors) >= 1
        assert any("null" in e.lower() for e in errors)

    def test_metrics_array_with_invalid_format(self):
        """Array metrics with invalid format should error."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        params = {"metrics": ["SUM(sales)", "INVALID(col)"]}
        errors = _validate_metric_string_format(params)
        assert len(errors) == 1  # only INVALID(col) should error
        assert any("INVALID" in e for e in errors)

    def test_empty_params_passes(self):
        """No metric fields should pass."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        errors = _validate_metric_string_format({})
        assert errors == []

    def test_metrics_array_null_column_name_errors(self):
        """Array dict metric with null column_name should error."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format
        
        params = {
            "metrics": [
                {"aggregate": "SUM", "column": {"column_name": None}, "expressionType": "SIMPLE"},
            ]
        }
        errors = _validate_metric_string_format(params)
        assert len(errors) >= 1
        assert any("null" in e.lower() for e in errors)

    def test_orderby_null_entry_errors(self):
        """Null entry in orderby should be caught."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "orderby": [["count", False], [None, False]],
        }
        errors = _validate_metric_string_format(params)
        assert any("null" in e.lower() for e in errors)

    def test_orderby_dict_null_column_errors(self):
        """Dict entry in orderby with null column should be caught."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "orderby": [{"column": {"column_name": None}, "asc": True}],
        }
        errors = _validate_metric_string_format(params)
        assert any("null" in e.lower() for e in errors)

    def test_orderby_valid_entries_passes(self):
        """Valid orderby entries should pass format check."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "orderby": [["sales", False], ["revenue", True]],
        }
        errors = _validate_metric_string_format(params)
        assert not any("orderby" in e for e in errors)

    def test_timeseries_limit_metric_null_errors(self):
        """Null timeseries_limit_metric should be caught."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "timeseries_limit_metric": None,
        }
        errors = _validate_metric_string_format(params)
        assert any("null" in e.lower() for e in errors)

    def test_timeseries_limit_metric_dict_null_column_errors(self):
        """Dict timeseries_limit_metric with null column_name should be caught."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "timeseries_limit_metric": {
                "aggregate": "SUM",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
            },
        }
        errors = _validate_metric_string_format(params)
        assert any("null" in e.lower() for e in errors)

    def test_timeseries_limit_metric_valid_passes(self):
        """Valid timeseries_limit_metric should pass."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        params = {
            "metrics": ["count"],
            "timeseries_limit_metric": {"aggregate": "SUM", "column": {"column_name": "sales"}, "expressionType": "SIMPLE"},
        }
        errors = _validate_metric_string_format(params)
        assert not any("timeseries_limit_metric" in e for e in errors)


class TestOrderbyColumnExtraction:
    """Test _extract_columns_from_params handles orderby."""

    def test_orderby_array_format_extracts_columns(self):
        """Array format orderby columns should be extracted."""
        from modules.SupersetModule.tools.chart_validation import _extract_columns_from_params

        params = {
            "orderby": [["sales", False], ["revenue", True]],
            "viz_type": "echarts_timeseries_line",
        }
        refs = _extract_columns_from_params(params, "echarts_timeseries_line")
        assert any("sales" in r for r in refs)
        assert any("revenue" in r for r in refs)

    def test_orderby_dict_format_extracts_columns(self):
        """Dict format orderby columns should be extracted."""
        from modules.SupersetModule.tools.chart_validation import _extract_columns_from_params

        params = {
            "orderby": [{"column": {"column_name": "sales"}, "asc": True}],
            "viz_type": "echarts_timeseries_line",
        }
        refs = _extract_columns_from_params(params, "echarts_timeseries_line")
        assert any("sales" in r for r in refs)

    def test_orderby_null_entry_skipped(self):
        """Null entry in orderby should not crash extraction."""
        from modules.SupersetModule.tools.chart_validation import _extract_columns_from_params

        params = {
            "orderby": [["sales", False], [None, False]],
            "viz_type": "echarts_timeseries_line",
        }
        refs = _extract_columns_from_params(params, "echarts_timeseries_line")
        assert any("sales" in r for r in refs)

    def test_timeseries_limit_metric_string_extracts(self):
        """String timeseries_limit_metric should extract column."""
        from modules.SupersetModule.tools.chart_validation import _extract_columns_from_params

        params = {
            "timeseries_limit_metric": "SUM(sales)",
            "viz_type": "echarts_timeseries_line",
        }
        refs = _extract_columns_from_params(params, "echarts_timeseries_line")
        assert any("sales" in r for r in refs)

    def test_timeseries_limit_metric_dict_extracts(self):
        """Dict timeseries_limit_metric should extract column."""
        from modules.SupersetModule.tools.chart_validation import _extract_columns_from_params

        params = {
            "timeseries_limit_metric": {
                "aggregate": "SUM",
                "column": {"column_name": "sales"},
                "expressionType": "SIMPLE",
            },
            "viz_type": "echarts_timeseries_line",
        }
        refs = _extract_columns_from_params(params, "echarts_timeseries_line")
        assert any("sales" in r for r in refs)


class TestAutoFixOrderby:
    """Test auto_fix handles null column_name in orderby/timeseries_limit_metric."""

    def test_auto_fix_null_orderby_array(self):
        """Null entry in orderby array should be fixed."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["SUM(sales)"],
            "orderby": [["count", False], [None, False]],
        }
        fixed = auto_fix_chart_params("echarts_timeseries_line", params)
        assert fixed["orderby"][1][0] == "count"

    def test_auto_fix_null_orderby_dict(self):
        """Dict entry in orderby with null column_name should be fixed."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["SUM(sales)"],
            "groupby": "category",
            "orderby": [{"column": {"column_name": None}, "asc": True}],
        }
        fixed = auto_fix_chart_params("echarts_timeseries_line", params)
        assert fixed["orderby"][0]["column"]["column_name"] == "category"

    def test_auto_fix_null_timeseries_limit_metric(self):
        """Null timeseries_limit_metric should be replaced."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["SUM(sales)"],
            "timeseries_limit_metric": None,
        }
        fixed = auto_fix_chart_params("echarts_timeseries_line", params)
        assert fixed["timeseries_limit_metric"] == "count"

    def test_auto_fix_null_timeseries_limit_metric_dict(self):
        """Dict timeseries_limit_metric with null column_name should be fixed."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        params = {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["SUM(sales)"],
            "timeseries_limit_metric": {
                "aggregate": "SUM",
                "column": {"column_name": None},
                "expressionType": "SIMPLE",
            },
        }
        fixed = auto_fix_chart_params("echarts_timeseries_line", params)
        assert fixed["timeseries_limit_metric"]["column"]["column_name"] == "count"


class TestEntityValidation:
    """Test entity field validation catches null/empty values."""

    def test_validate_chart_params_null_entity_errors(self):
        """world_map with null entity should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        errors = validate_chart_params("world_map", {"viz_type": "world_map", "entity": None, "metric": "count"})
        assert any("entity" in e.lower() for e in errors)

    def test_validate_chart_params_empty_entity_errors(self):
        """world_map with empty string entity should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        errors = validate_chart_params("world_map", {"viz_type": "world_map", "entity": "", "metric": "count"})
        assert any("entity" in e.lower() for e in errors)

    def test_validate_chart_params_valid_entity_passes(self):
        """world_map with valid entity should pass."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        errors = validate_chart_params("world_map", {"viz_type": "world_map", "entity": "country_code", "metric": "count"})
        assert not any("entity" in e.lower() for e in errors) or errors == []

    def test_auto_fix_null_entity(self):
        """world_map with null entity should be fixed to 'country_code'."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        fixed = auto_fix_chart_params("world_map", {"viz_type": "world_map", "entity": None, "metric": "count"})
        assert fixed["entity"] == "country_code"

    def test_auto_fix_empty_entity(self):
        """world_map with empty entity should be fixed to 'country_code'."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        fixed = auto_fix_chart_params("world_map", {"viz_type": "world_map", "entity": "", "metric": "count"})
        assert fixed["entity"] == "country_code"

    def test_auto_fix_missing_entity(self):
        """world_map without entity should be fixed to 'country_code'."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        fixed = auto_fix_chart_params("world_map", {"viz_type": "world_map", "metric": "count"})
        assert fixed["entity"] == "country_code"

    def test_format_check_null_entity_errors(self):
        """Null entity should be caught by format validator."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        errors = _validate_metric_string_format({"metric": "count", "entity": None})
        assert any("entity" in e.lower() and "null" in e.lower() for e in errors)

    def test_format_check_empty_entity_errors(self):
        """Empty entity should be caught by format validator."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        errors = _validate_metric_string_format({"metric": "count", "entity": ""})
        assert any("entity" in e.lower() for e in errors)

    def test_format_check_valid_entity_passes(self):
        """Valid entity should pass format check."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        errors = _validate_metric_string_format({"metric": "count", "entity": "country_code"})
        assert not any("entity" in e for e in errors)


class TestNullMetricValue:
    """Test metric: None is caught at all levels."""

    def test_validate_chart_params_null_metric_string_type(self):
        """SINGULAR_STRING_METRIC_TYPES with null metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        errors = validate_chart_params("big_number_total", {"metric": None})
        assert any("null" in e.lower() for e in errors)

    def test_validate_chart_params_null_metric_adhoc_type(self):
        """SINGULAR_ADHOC_METRIC_TYPES with null metric should error."""
        from modules.SupersetModule.superset_validation import validate_chart_params

        errors = validate_chart_params("pie", {"metric": None})
        assert any("null" in e.lower() for e in errors)

    def test_format_check_null_metric(self):
        """Format check should catch null metric."""
        from modules.SupersetModule.tools.charts import _validate_metric_string_format

        errors = _validate_metric_string_format({"metric": None})
        assert any("null" in e.lower() for e in errors)

    def test_auto_fix_null_metric_replaces_with_count(self):
        """Auto-fix should replace null metric with 'count'."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        fixed = auto_fix_chart_params("big_number_total", {"metric": None})
        assert fixed["metric"] == "count"

    def test_auto_fix_null_metric_uses_groupby(self):
        """Auto-fix should use groupby when available."""
        from modules.SupersetModule.superset_validation import auto_fix_chart_params

        fixed = auto_fix_chart_params("big_number_total", {"metric": None, "groupby": "region"})
        assert fixed["metric"] == "region"
