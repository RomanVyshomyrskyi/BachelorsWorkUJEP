import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from modules.DBAnalysis.tools.visualization import tool_generate_chart


class MockSeries:
    """Mock pandas Series that behaves like a list for iteration."""
    def __init__(self, data):
        self._data = list(data)
    
    def astype(self, dtype):
        return self._data
    
    def __iter__(self):
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def tolist(self):
        return self._data


class TestToolGenerateChart:
    def test_generate_chart_success(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [
                    {"category": "A", "value": 10},
                    {"category": "B", "value": 20},
                ]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries(['A', 'B'])
                y_series = MockSeries([10, 20])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['category', 'value']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'category' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT category, value FROM data",
                    chart_type="bar",
                    x_column="category",
                    y_column="value",
                    title="Test Chart",
                    port=5432
                )
                
                assert isinstance(result, list)
                assert len(result) == 2
                assert result[0]["type"] == "text"
                assert result[1]["type"] == "image"

    def test_generate_chart_bar_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": "A", "y": 10}]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries(["A"])
                y_series = MockSeries([10])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x', 'y']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'x' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x, y FROM data",
                    chart_type="bar",
                    x_column="x",
                    y_column="y",
                    port=5432
                )
                
                assert isinstance(result, list)

    def test_generate_chart_line_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": "A", "y": 10}]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries(["A"])
                y_series = MockSeries([10])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x', 'y']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'x' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x, y FROM data",
                    chart_type="line",
                    x_column="x",
                    y_column="y",
                    port=5432
                )
                
                assert isinstance(result, list)

    def test_generate_chart_pie_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": "A", "y": 10}]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries(["A"])
                y_series = MockSeries([10])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x', 'y']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'x' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x, y FROM data",
                    chart_type="pie",
                    x_column="x",
                    y_column="y",
                    port=5432
                )
                
                assert isinstance(result, list)

    def test_generate_chart_scatter_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": 1, "y": 2}]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries([1])
                y_series = MockSeries([2])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x', 'y']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'x' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x, y FROM data",
                    chart_type="scatter",
                    x_column="x",
                    y_column="y",
                    port=5432
                )
                
                assert isinstance(result, list)

    def test_generate_chart_unsupported_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": "A", "y": 10}]
                mock_get_strategy.return_value = mock_strategy
                
                x_series = MockSeries(["A"])
                y_series = MockSeries([10])
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x', 'y']
                mock_df_instance.__getitem__ = MagicMock(side_effect=lambda k: x_series if k == 'x' else y_series)
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x, y FROM data",
                    chart_type="invalid_type",
                    x_column="x",
                    y_column="y",
                    port=5432
                )
                
                assert "Unsupported chart type" in result

    def test_generate_chart_no_data(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = []
            mock_get_strategy.return_value = mock_strategy
            
            result = tool_generate_chart(
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                query="SELECT * FROM empty",
                chart_type="bar",
                x_column="x",
                y_column="y",
                port=5432
            )
            
            assert "No data returned" in result

    def test_generate_chart_column_not_found(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.visualization.pd.DataFrame') as mock_df_class:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.execute_query.return_value = [{"x": 1}]
                mock_get_strategy.return_value = mock_strategy
                
                mock_df_instance = MagicMock()
                mock_df_instance.columns = ['x']
                mock_df_class.return_value = mock_df_instance
                
                result = tool_generate_chart(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    query="SELECT x FROM data",
                    chart_type="bar",
                    x_column="x",
                    y_column="missing_column",
                    port=5432
                )
                
                assert "not found" in result.lower()

    def test_generate_chart_connection_error(self):
        with patch('modules.DBAnalysis.tools.visualization.get_db_strategy') as mock_get_strategy:
            mock_get_strategy.side_effect = ConnectionError("Failed to connect")
            
            result = tool_generate_chart(
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                query="SELECT * FROM data",
                chart_type="bar",
                x_column="x",
                y_column="y",
                port=5432
            )
            
            assert "error" in result.lower()
