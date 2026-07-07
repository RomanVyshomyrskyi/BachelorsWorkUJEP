import pytest
import json
import psycopg2

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.strategies.postgres import PostgresStrategy


@pytest.mark.integration
class TestPostgresStrategyIntegration:
    """Integration tests that require a running PostgreSQL container."""

    @pytest.fixture(scope="class")
    def connected_strategy(self, postgres_config):
        strategy = PostgresStrategy({
            "host": postgres_config["host"],
            "user": postgres_config["user"],
            "password": postgres_config["password"],
            "dbname": postgres_config["dbname"],
            "port": postgres_config["port"],
        })
        strategy.connect()
        yield strategy
        strategy.disconnect()

    @pytest.fixture(scope="class")
    def setup_test_tables(self, connected_strategy):
        cursor = connected_strategy.connection.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS test_int_data CASCADE")
        cursor.execute("DROP TABLE IF EXISTS test_int_users CASCADE")
        
        cursor.execute("""
            CREATE TABLE test_int_users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE test_int_data (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                value INTEGER
            )
        """)
        
        cursor.execute("INSERT INTO test_int_users (name, email) VALUES ('Alice', 'alice@test.com')")
        cursor.execute("INSERT INTO test_int_users (name, email) VALUES ('Bob', 'bob@test.com')")
        cursor.execute("INSERT INTO test_int_data (user_id, value) VALUES (1, 100)")
        cursor.execute("INSERT INTO test_int_data (user_id, value) VALUES (2, 200)")
        
        connected_strategy.connection.commit()
        
        yield connected_strategy
        
        cursor.execute("DROP TABLE IF EXISTS test_int_data CASCADE")
        cursor.execute("DROP TABLE IF EXISTS test_int_users CASCADE")
        connected_strategy.connection.commit()
        cursor.close()

    def test_connect_and_disconnect(self, postgres_config):
        strategy = PostgresStrategy({
            "host": postgres_config["host"],
            "user": postgres_config["user"],
            "password": postgres_config["password"],
            "dbname": postgres_config["dbname"],
            "port": postgres_config["port"],
        })
        
        strategy.connect()
        assert strategy.connection is not None
        
        strategy.disconnect()
        assert strategy.connection is None

    def test_execute_query_returns_results(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query(
            "SELECT id, name, email FROM test_int_users"
        )
        
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["name"] == "Alice"
        assert results[1]["name"] == "Bob"

    def test_execute_query_with_where_clause(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query(
            "SELECT name FROM test_int_users WHERE id = 1"
        )
        
        assert len(results) == 1
        assert results[0]["name"] == "Alice"

    def test_execute_query_returns_empty_for_no_matches(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query(
            "SELECT * FROM test_int_users WHERE id = 9999"
        )
        
        assert results == []

    def test_get_schema_representation_contains_tables(self, connected_strategy, setup_test_tables):
        schema = connected_strategy.get_schema_representation()
        
        assert isinstance(schema, str)
        assert "test_int_users" in schema
        assert "test_int_data" in schema
        assert "id" in schema
        assert "name" in schema

    def test_get_schema_representation_includes_column_types(self, connected_strategy, setup_test_tables):
        schema = connected_strategy.get_schema_representation()
        
        assert "VARCHAR" in schema or "character varying" in schema.lower()
        assert "integer" in schema.lower() or "serial" in schema.lower()

    def test_security_rejects_insert(self, connected_strategy, setup_test_tables):
        with pytest.raises(ValueError, match="Security violation"):
            connected_strategy.execute_query(
                "INSERT INTO test_int_users (name) VALUES ('test')"
            )

    def test_security_rejects_update(self, connected_strategy, setup_test_tables):
        with pytest.raises(ValueError, match="Security violation"):
            connected_strategy.execute_query(
                "UPDATE test_int_users SET name = 'test' WHERE id = 1"
            )

    def test_security_rejects_delete(self, connected_strategy, setup_test_tables):
        with pytest.raises(ValueError, match="Security violation"):
            connected_strategy.execute_query(
                "DELETE FROM test_int_users WHERE id = 1"
            )

    def test_security_rejects_drop(self, connected_strategy, setup_test_tables):
        with pytest.raises(ValueError, match="Security violation"):
            connected_strategy.execute_query(
                "DROP TABLE test_int_users"
            )

    def test_count_query(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query(
            "SELECT COUNT(*) FROM test_int_users"
        )
        
        assert len(results) == 1
        assert results[0]["count"] == 2

    def test_sum_query(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query(
            "SELECT SUM(value) FROM test_int_data"
        )
        
        assert len(results) == 1
        assert results[0]["sum"] == 300

    def test_join_query(self, connected_strategy, setup_test_tables):
        results = connected_strategy.execute_query("""
            SELECT u.name, d.value 
            FROM test_int_users u 
            JOIN test_int_data d ON u.id = d.user_id
        """)
        
        assert isinstance(results, list)
        assert results[0]["name"] == "Alice"
        assert results[0]["value"] == 100


@pytest.mark.integration
class TestPostgresInvalidConnectionIntegration:
    """Test handling of invalid database connections."""

    def test_invalid_connection_raises_error(self, invalid_postgres_config):
        strategy = PostgresStrategy({
            "host": invalid_postgres_config["host"],
            "user": invalid_postgres_config["user"],
            "password": invalid_postgres_config["password"],
            "dbname": invalid_postgres_config["dbname"],
            "port": invalid_postgres_config["port"],
        })
        
        with pytest.raises(ConnectionError):
            strategy.connect()
