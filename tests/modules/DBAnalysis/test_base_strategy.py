import pytest
from abc import ABC
from unittest.mock import MagicMock, patch

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


# Note: Context manager tests are in test_postgres_strategy.py since they
# require a concrete implementation with mocked psycopg2.connect


class TestDatabaseStrategyAbstractMethods:
    def test_connect_is_abstract(self):
        class TestStrategy(DatabaseStrategy):
            pass
        
        with pytest.raises(TypeError):
            TestStrategy({})

    def test_disconnect_is_abstract(self):
        class TestStrategy(DatabaseStrategy):
            def connect(self):
                pass
        
        with pytest.raises(TypeError):
            TestStrategy({})

    def test_get_schema_representation_is_abstract(self):
        class TestStrategy(DatabaseStrategy):
            def connect(self):
                pass
            def disconnect(self):
                pass
        
        with pytest.raises(TypeError):
            TestStrategy({})

    def test_execute_query_is_abstract(self):
        class TestStrategy(DatabaseStrategy):
            def connect(self):
                pass
            def disconnect(self):
                pass
            def get_schema_representation(self):
                return ""
        
        with pytest.raises(TypeError):
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
