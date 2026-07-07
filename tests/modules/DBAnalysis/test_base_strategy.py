import pytest
from abc import ABC
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.strategies.base import DatabaseStrategy


class TestDatabaseStrategy:
    def test_base_class_is_abstract(self):
        assert issubclass(DatabaseStrategy, ABC)

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            DatabaseStrategy({})

    def test_init_stores_connection_details(self, valid_connection_details):
        strategy = MagicMock(spec=DatabaseStrategy)
        strategy.connection_details = valid_connection_details
        strategy.connection = None
        
        assert strategy.connection_details == valid_connection_details
        assert strategy.connection is None

    def test_init_sets_connection_to_none(self, valid_connection_details):
        strategy = MagicMock(spec=DatabaseStrategy)
        strategy.connection = None
        
        assert strategy.connection is None


class TestDatabaseStrategyContextManager:
    def test_context_manager_connects_on_enter(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as MockStrategy:
            mock_instance = MockStrategy.return_value
            mock_instance.connection = MagicMock()
            
            with DatabaseStrategy.__new__(MockStrategy) as strategy:
                pass
            
            MockStrategy.assert_called_once()
            MockStrategy.return_value.connect.assert_called_once()
            MockStrategy.return_value.disconnect.assert_called_once()

    def test_context_manager_disconnects_on_exit(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as MockStrategy:
            mock_instance = MockStrategy.return_value
            mock_instance.connection = MagicMock()
            
            try:
                with MockStrategy(valid_connection_details) as strategy:
                    pass
            except Exception:
                pass
            
            MockStrategy.return_value.disconnect.assert_called_once()

    def test_context_manager_returns_strategy_instance(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as MockStrategy:
            mock_instance = MockStrategy.return_value
            
            result = MockStrategy(valid_connection_details).__enter__()
            
            assert result is mock_instance


class TestDatabaseStrategyAbstractMethods:
    def test_connect_is_abstract(self):
        with pytest.raises(TypeError):
            class TestStrategy(DatabaseStrategy):
                pass
            TestStrategy({})

    def test_disconnect_is_abstract(self):
        with pytest.raises(TypeError):
            class TestStrategy(DatabaseStrategy):
                def connect(self):
                    pass
            TestStrategy({})

    def test_get_schema_representation_is_abstract(self):
        with pytest.raises(TypeError):
            class TestStrategy(DatabaseStrategy):
                def connect(self):
                    pass
                def disconnect(self):
                    pass
            TestStrategy({})

    def test_execute_query_is_abstract(self):
        with pytest.raises(TypeError):
            class TestStrategy(DatabaseStrategy):
                def connect(self):
                    pass
                def disconnect(self):
                    pass
                def get_schema_representation(self):
                    return ""
            TestStrategy({})

    def test_concrete_implementation_with_all_methods_works(self):
        class TestStrategy(DatabaseStrategy):
            def connect(self):
                pass
            def disconnect(self):
                pass
            def get_schema_representation(self) -> str:
                return "test"
            def execute_query(self, query: str) -> list:
                return []
        
        strategy = TestStrategy({})
        assert isinstance(strategy, DatabaseStrategy)
        assert strategy.get_schema_representation() == "test"
