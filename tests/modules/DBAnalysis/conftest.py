import pytest


from modules.DBAnalysis.models.connection import ConnectionDetails


@pytest.fixture
def connection_details_model():
    return ConnectionDetails(
        host="localhost",
        user="test_user",
        password="test_password",
        dbname="test_db",
        port=5432,
    )


@pytest.fixture
def connection_details_model_no_port():
    return ConnectionDetails(
        host="localhost",
        user="test_user",
        password="test_password",
        dbname="test_db",
    )
