import pytest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.strategies.factory import get_db_strategy
from modules.DBAnalysis.strategies.base import DatabaseStrategy


class TestGetDbStrategy:
    def test_get_db_strategy_returns_postgres_for_postgres_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as mock_strategy:
            strategy = get_db_strategy("postgres", valid_connection_details)
            
            mock_strategy.assert_called_once_with(valid_connection_details)
            assert strategy is mock_strategy.return_value

    def test_get_db_strategy_returns_mariadb_for_mariadb_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.mariadb.MariaDBStrategy') as mock_strategy:
            strategy = get_db_strategy("mariadb", valid_connection_details)
            
            mock_strategy.assert_called_once_with(valid_connection_details)
            assert strategy is mock_strategy.return_value

    def test_get_db_strategy_returns_mssql_for_mssql_type(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.mssql.MSSQLStrategy') as mock_strategy:
            strategy = get_db_strategy("mssql", valid_connection_details)
            
            mock_strategy.assert_called_once_with(valid_connection_details)
            assert strategy is mock_strategy.return_value

    def test_get_db_strategy_returns_database_strategy_instance(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as mock_strategy:
            mock_instance = MagicMock(spec=DatabaseStrategy)
            mock_strategy.return_value = mock_instance
            
            strategy = get_db_strategy("postgres", valid_connection_details)
            
            assert isinstance(strategy, DatabaseStrategy)

    def test_get_db_strategy_passes_connection_details(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.PostgresStrategy') as mock_strategy:
            get_db_strategy("postgres", valid_connection_details)
            
            mock_strategy.assert_called_once_with(valid_connection_details)


class TestGetDbStrategyErrors:
    def test_get_db_strategy_raises_value_error_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_db_strategy("oracle", {})

    def test_get_db_strategy_raises_value_error_for_empty_type(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_db_strategy("", {})

    def test_get_db_strategy_raises_value_error_for_mysql_type(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_db_strategy("mysql", {})

    def test_get_db_strategy_raises_value_error_for_sqlite_type(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_db_strategy("sqlite", {})


class TestGetDbStrategyImports:
    def test_get_db_strategy_handles_mssql_import_error(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.factory') as mock_factory:
            import modules.DBAnalysis.strategies.mssql
            
            original_mssql = sys.modules.get('modules.DBAnalysis.strategies.mssql')
            
            try:
                if 'modules.DBAnalysis.strategies.mssql' in sys.modules:
                    del sys.modules['modules.DBAnalysis.strategies.mssql']
                
                with patch.dict('sys.modules', {'modules.DBAnalysis.strategies.mssql': None}):
                    with patch('builtins.__import__', side_effect=ImportError("No module named 'pyodbc'")):
                        with pytest.raises(ImportError, match="MSSQL support requires pyodbc"):
                            get_db_strategy("mssql", valid_connection_details)
            finally:
                if original_mssql is not None:
                    sys.modules['modules.DBAnalysis.strategies.mssql'] = original_mssql
