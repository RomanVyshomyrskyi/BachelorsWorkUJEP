import pytest
from unittest.mock import MagicMock, patch
import json

from modules.SupersetModule.tools.dashboards import _build_simple_layout


class TestBuildSimpleLayout:
    def test_single_chart_in_row(self):
        chart_info = [{"id": 1, "name": "Chart 1"}]
        layout = _build_simple_layout(chart_info)
        
        assert "ROOT_ID" in layout
        assert "GRID_ID" in layout
        assert "ROW-R0" in layout
        assert "CHART_1" in layout
        
        assert layout["ROOT_ID"]["children"] == ["GRID_ID"]
        assert layout["GRID_ID"]["children"] == ["ROW-R0"]
        assert layout["ROW-R0"]["children"] == ["CHART_1"]
        assert layout["CHART_1"]["parents"] == ["ROW-R0"]

    def test_two_charts_in_row(self):
        chart_info = [{"id": 1, "name": "Chart 1"}, {"id": 2, "name": "Chart 2"}]
        layout = _build_simple_layout(chart_info)
        
        assert "ROW-R0" in layout
        assert "CHART_1" in layout
        assert "CHART_2" in layout
        
        assert set(layout["ROW-R0"]["children"]) == {"CHART_1", "CHART_2"}
        assert layout["CHART_1"]["parents"] == ["ROW-R0"]
        assert layout["CHART_2"]["parents"] == ["ROW-R0"]

    def test_charts_split_into_multiple_rows(self):
        chart_info = [
            {"id": 1, "name": "Chart 1"},
            {"id": 2, "name": "Chart 2"},
            {"id": 3, "name": "Chart 3"},
            {"id": 4, "name": "Chart 4"},
        ]
        layout = _build_simple_layout(chart_info)
        
        assert "ROW-R0" in layout
        assert "ROW-R1" in layout
        
        row0_children = layout["ROW-R0"]["children"]
        row1_children = layout["ROW-R1"]["children"]
        
        assert set(row0_children) == {"CHART_1", "CHART_2"}
        assert set(row1_children) == {"CHART_3", "CHART_4"}
        
        assert layout["GRID_ID"]["children"] == ["ROW-R0", "ROW-R1"]

    def test_row_of_charts_layout(self):
        chart_info = [
            {"id": 1, "name": "Chart 1"},
            {"id": 2, "name": "Chart 2"},
        ]
        layout = _build_simple_layout(chart_info, layout_type="row_of_charts", chart_width=6)
        
        assert layout["CHART_1"]["meta"]["startX"] == 0
        assert layout["CHART_2"]["meta"]["startX"] == 6
        assert layout["CHART_1"]["meta"]["startY"] == 0
        assert layout["CHART_2"]["meta"]["startY"] == 0

    def test_column_of_charts_layout(self):
        chart_info = [
            {"id": 1, "name": "Chart 1"},
            {"id": 2, "name": "Chart 2"},
        ]
        layout = _build_simple_layout(chart_info, layout_type="column_of_charts", chart_height=50)
        
        assert layout["CHART_1"]["meta"]["startX"] == 0
        assert layout["CHART_2"]["meta"]["startX"] == 0
        assert layout["CHART_1"]["meta"]["startY"] == 0
        assert layout["CHART_2"]["meta"]["startY"] == 50

    def test_custom_chart_dimensions(self):
        chart_info = [{"id": 1, "name": "Chart 1"}]
        layout = _build_simple_layout(chart_info, chart_width=4, chart_height=30)
        
        assert layout["CHART_1"]["meta"]["width"] == 4
        assert layout["CHART_1"]["meta"]["height"] == 30

    def test_hierarchical_structure(self):
        chart_info = [
            {"id": 1, "name": "Chart 1"},
            {"id": 2, "name": "Chart 2"},
            {"id": 3, "name": "Chart 3"},
        ]
        layout = _build_simple_layout(chart_info)
        
        # ROOT -> GRID
        assert "GRID_ID" in layout["ROOT_ID"]["children"]
        
        # GRID -> ROWs
        assert layout["GRID_ID"]["parents"] == ["ROOT_ID"]
        
        # ROW -> CHARTs
        for row_id in ["ROW-R0", "ROW-R1"]:
            assert layout[row_id]["parents"] == ["GRID_ID"]
        
        # CHART -> ROW
        for chart_id in [1, 2, 3]:
            chart_id_str = f"CHART_{chart_id}"
            assert layout[chart_id_str]["parents"] == [f"ROW-R{0 if chart_id <= 2 else 1}"]

    def test_chart_meta_has_required_fields(self):
        chart_info = [{"id": 42, "name": "Test Chart"}]
        layout = _build_simple_layout(chart_info)
        
        meta = layout["CHART_42"]["meta"]
        
        assert meta["chartId"] == 42
        assert meta["sliceName"] == "Test Chart"
        assert "width" in meta
        assert "height" in meta
        assert "startX" in meta
        assert "startY" in meta

    def test_three_charts_layout(self):
        chart_info = [
            {"id": 1, "name": "Chart 1"},
            {"id": 2, "name": "Chart 2"},
            {"id": 3, "name": "Chart 3"},
        ]
        layout = _build_simple_layout(chart_info, layout_type="row_of_charts", chart_width=6)
        
        # First two charts in ROW-R0
        assert layout["ROW-R0"]["children"] == ["CHART_1", "CHART_2"]
        assert layout["CHART_1"]["meta"]["startX"] == 0
        assert layout["CHART_2"]["meta"]["startX"] == 6
        
        # Third chart in ROW-R1
        assert layout["ROW-R1"]["children"] == ["CHART_3"]
        assert layout["CHART_3"]["meta"]["startX"] == 0
        assert layout["CHART_3"]["meta"]["startY"] == 0
