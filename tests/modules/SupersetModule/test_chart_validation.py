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
