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
        assert "SUM(sales)" in missing

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
        assert "SUM(cost)" in missing
        assert "SUM(revenue)" not in missing


class TestChartIdExtraction:
    """Test _extract_chart_ids_from_position_json function."""

    def test_extract_ids_from_dict(self):
        """Chart IDs should be extracted from position dict."""
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
        
        position_json = '{"ROW1": {"type": "ROW", "children": [{"type": "CHART", "slice_id": 42}]}}'
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
            "a": {"b": {"c": [{"slice_id": 10}, {"slice_id": 20}]}}
        }
        ids = _extract_chart_ids_from_position_json(position_json)
        assert 10 in ids
        assert 20 in ids


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
