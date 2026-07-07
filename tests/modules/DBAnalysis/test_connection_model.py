import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.models.connection import ConnectionDetails


class TestConnectionDetails:
    def test_create_valid_connection_details(self, connection_details_model):
        assert connection_details_model.host == "localhost"
        assert connection_details_model.user == "test_user"
        assert connection_details_model.password == "test_password"
        assert connection_details_model.dbname == "test_db"
        assert connection_details_model.port == 5432

    def test_create_without_port(self, connection_details_model_no_port):
        assert connection_details_model_no_port.host == "localhost"
        assert connection_details_model_no_port.port is None

    def test_create_with_all_required_fields(self):
        details = ConnectionDetails(
            host="db.example.com",
            user="admin",
            password="secret",
            dbname="production",
        )
        
        assert details.host == "db.example.com"
        assert details.user == "admin"
        assert details.password == "secret"
        assert details.dbname == "production"
        assert details.port is None

    def test_create_with_all_fields(self):
        details = ConnectionDetails(
            host="db.example.com",
            user="admin",
            password="secret",
            dbname="production",
            port=5432,
        )
        
        assert details.port == 5432

    def test_missing_host_raises_error(self):
        with pytest.raises(ValidationError):
            ConnectionDetails(
                host="",
                user="admin",
                password="secret",
                dbname="production",
            )

    def test_missing_user_raises_error(self):
        with pytest.raises(ValidationError):
            ConnectionDetails(
                host="localhost",
                user="",
                password="secret",
                dbname="production",
            )

    def test_missing_password_raises_error(self):
        with pytest.raises(ValidationError):
            ConnectionDetails(
                host="localhost",
                user="admin",
                password="",
                dbname="production",
            )

    def test_missing_dbname_raises_error(self):
        with pytest.raises(ValidationError):
            ConnectionDetails(
                host="localhost",
                user="admin",
                password="secret",
                dbname="",
            )

    def test_invalid_port_type(self):
        with pytest.raises(ValidationError):
            ConnectionDetails(
                host="localhost",
                user="admin",
                password="secret",
                dbname="production",
                port="not_a_number",
            )

    def test_port_zero_is_valid(self):
        details = ConnectionDetails(
            host="localhost",
            user="admin",
            password="secret",
            dbname="production",
            port=0,
        )
        assert details.port == 0

    def test_to_dict_conversion(self, connection_details_model):
        result = connection_details_model.model_dump()
        
        assert isinstance(result, dict)
        assert result["host"] == "localhost"
        assert result["user"] == "test_user"
        assert result["password"] == "test_password"
        assert result["dbname"] == "test_db"
        assert result["port"] == 5432

    def test_model_has_description_fields(self):
        details = ConnectionDetails(
            host="localhost",
            user="admin",
            password="secret",
            dbname="production",
        )
        
        schema = ConnectionDetails.model_json_schema()
        assert "host" in schema["properties"]
        assert "user" in schema["properties"]
        assert "password" in schema["properties"]
        assert "dbname" in schema["properties"]
        assert "port" in schema["properties"]
