import pytest
from unittest.mock import MagicMock, patch, mock_open
import psycopg2

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.strategies.postgres import PostgresStrategy
from modules.DBAnalysis.strategies.base import DatabaseStrategy


class TestPostgresStrategyConnect:
    def test_connect_success(self, valid_connection_details):
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            strategy = PostgresStrategy(valid_connection_details)
            strategy.connect()
            
            mock_connect.assert_called_once_with(
                dbname=valid_connection_details['dbname'],
                user=valid_connection_details['user'],
                password=valid_connection_details['password'],
                host=valid_connection_details['host'],
                port=valid_connection_details.get('port', 5432)
            )
            assert strategy.connection is not None

    def test_connect_with_custom_port(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
            'port': 5433,
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            strategy = PostgresStrategy(details)
            strategy.connect()
            
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs['port'] == 5433

    def test_connect_without_port_defaults_to_5432(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            strategy = PostgresStrategy(details)
            strategy.connect()
            
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs['port'] == 5432

    def test_connect_failure_raises_connection_error(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("Connection failed")
            
            strategy = PostgresStrategy(details)
            
            with pytest.raises(ConnectionError, match="Failed to connect to PostgreSQL"):
                strategy.connect()

    def test_connect_attribute_error(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            mock_connect.side_effect = Exception("Some other error")
            
            strategy = PostgresStrategy(details)
            
            with pytest.raises(ConnectionError, match="Failed to connect to PostgreSQL"):
                strategy.connect()


class TestPostgresStrategyDisconnect:
    def test_disconnect_closes_connection(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        strategy.connection = MagicMock()
        
        strategy.disconnect()
        
        strategy.connection.close.assert_called_once()
        assert strategy.connection is None

    def test_disconnect_with_no_connection(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        strategy.connection = None
        
        strategy.disconnect()
        
        assert strategy.connection is None


class TestPostgresStrategyGetSchema:
    def test_get_schema_raises_error_when_not_connected(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ConnectionError, match="Not connected to the database"):
            strategy.get_schema_representation()

    def test_get_schema_returns_formatted_string(self, sample_table_data, sample_relationships):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [sample_table_data, sample_relationships]
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        strategy.connection = mock_connection
        
        result = strategy.get_schema_representation()
        
        assert isinstance(result, str)
        assert 'SCHEMA FOR POSTGRESQL DATABASE' in result
        assert 'test_db' in result
        assert 'TABLE: users' in result
        assert 'TABLE: orders' in result
        assert 'COLUMN: id' in result
        assert 'RELATIONSHIPS:' in result
        assert 'orders.user_id -> users.id' in result

    def test_get_schema_with_no_relationships(self, sample_table_data):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [sample_table_data, []]
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        strategy.connection = mock_connection
        
        result = strategy.get_schema_representation()
        
        assert 'No foreign key relationships found.' in result


class TestPostgresStrategyExecuteQuery:
    def test_execute_query_raises_error_when_not_connected(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ConnectionError, match="Not connected to the database"):
            strategy.execute_query("SELECT * FROM users")

    def test_execute_query_rejects_non_select(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ValueError, match="Security violation"):
            strategy.execute_query("INSERT INTO users VALUES (1, 'test')")

    def test_execute_query_rejects_update(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ValueError, match="Security violation"):
            strategy.execute_query("UPDATE users SET name = 'test'")

    def test_execute_query_rejects_delete(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ValueError, match="Security violation"):
            strategy.execute_query("DELETE FROM users WHERE id = 1")

    def test_execute_query_rejects_drop(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        with pytest.raises(ValueError, match="Security violation"):
            strategy.execute_query("DROP TABLE users")

    def test_execute_query_returns_results_as_dicts(self, sample_query_results):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, 'Alice', 'alice@example.com'), (2, 'Bob', 'bob@example.com')]
        mock_cursor.description = [('id',), ('name',), ('email',)]
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        strategy.connection = mock_connection
        
        result = strategy.execute_query("SELECT * FROM users")
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}
        assert result[1] == {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'}

    def test_execute_query_returns_empty_list_on_no_description(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = None
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        strategy.connection = mock_connection
        
        result = strategy.execute_query("SELECT 1")
        
        assert result == []

    def test_execute_query_with_case_insensitive_select(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, 'test')]
        mock_cursor.description = [('id',), ('value',)]
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        strategy.connection = mock_connection
        
        result = strategy.execute_query("select * from users")
        
        assert isinstance(result, list)
        assert len(result) == 1


class TestPostgresStrategyInheritance:
    def test_postgres_strategy_inherits_from_database_strategy(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        assert isinstance(strategy, DatabaseStrategy)

    def test_postgres_strategy_has_all_abstract_methods(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        strategy = PostgresStrategy(details)
        
        assert hasattr(strategy, 'connect')
        assert hasattr(strategy, 'disconnect')
        assert hasattr(strategy, 'get_schema_representation')
        assert hasattr(strategy, 'execute_query')


class TestPostgresStrategyContextManager:
    def test_context_manager_connects_on_enter(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect'):
            with PostgresStrategy(details) as strategy:
                assert strategy.connection is not None

    def test_context_manager_disconnects_on_exit(self):
        details = {
            'host': 'localhost',
            'user': 'admin',
            'password': 'admin',
            'dbname': 'test_db',
        }
        with patch('modules.DBAnalysis.strategies.postgres.psycopg2.connect') as mock_connect:
            mock_connect.return_value = MagicMock()
            with PostgresStrategy(details) as strategy:
                pass
            
            strategy.connection.close.assert_called_once()
