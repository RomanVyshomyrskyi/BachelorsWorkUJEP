import os
import pytest
import dotenv

dotenv.load_dotenv()


@pytest.fixture(scope="session")
def postgres_config():
    return {
        "db_type": "postgres",
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "user": os.getenv("POSTGRES_USER", "admin"),
        "password": os.getenv("POSTGRES_PASSWORD", "admin"),
        "dbname": os.getenv("POSTGRES_DB", "Postgres_Test_DB"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }


@pytest.fixture(scope="session")
def invalid_postgres_config():
    return {
        "db_type": "postgres",
        "host": "nonexistent.host.invalid",
        "user": "invalid_user",
        "password": "invalid_password",
        "dbname": "nonexistent_db",
        "port": 5432,
    }


@pytest.fixture
def valid_connection_details():
    return {
        "host": "localhost",
        "user": "admin",
        "password": "admin",
        "dbname": "Postgres_Test_DB",
        "port": 5432,
    }


@pytest.fixture
def invalid_connection_details():
    return {
        "host": "invalid.host",
        "user": "wrong_user",
        "password": "wrong_password",
        "dbname": "wrong_db",
        "port": 5432,
    }


@pytest.fixture
def sample_table_data():
    return [
        ("users", "id", "integer", "NO"),
        ("users", "name", "character varying", "NO"),
        ("users", "email", "character varying", "YES"),
        ("orders", "id", "integer", "NO"),
        ("orders", "user_id", "integer", "NO"),
        ("orders", "total", "numeric", "YES"),
    ]


@pytest.fixture
def sample_relationships():
    return [
        ("orders", "user_id", "users", "id"),
    ]


@pytest.fixture
def sample_query_results():
    return [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ]
