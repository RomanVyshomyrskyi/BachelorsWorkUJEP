import pytest
from unittest.mock import MagicMock, patch

import sys
import os

from modules.DBAnalysis.tools.analysis import tool_get_rules, tool_analyze_db


class TestToolGetRules:
    def test_get_rules_returns_string(self):
        result = tool_get_rules()
        assert isinstance(result, str)

    def test_get_rules_returns_non_empty(self):
        result = tool_get_rules()
        assert len(result) > 0

    def test_get_rules_contains_normalization_content(self):
        result = tool_get_rules()
        assert "1NF" in result or "First Normal Form" in result

    def test_get_rules_returns_same_as_loader(self):
        from modules.DBAnalysis.utils.rules_loader import get_normalization_rules
        
        tool_result = tool_get_rules()
        loader_result = get_normalization_rules()
        
        assert tool_result == loader_result


class TestToolAnalyzeDb:
    def test_analyze_db_returns_string(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.return_value = "TABLE: users\n  COLUMN: id, TYPE: integer"
                mock_get_strategy.return_value = mock_strategy
                mock_rules.return_value = "1NF: All values atomic"
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert isinstance(result, str)

    def test_analyze_db_includes_schema(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.return_value = "TABLE: users"
                mock_get_strategy.return_value = mock_strategy
                mock_rules.return_value = ""
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert "TABLE: users" in result

    def test_analyze_db_includes_rules(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.return_value = ""
                mock_rules.return_value = "First Normal Form rule"
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert "First Normal Form rule" in result

    def test_analyze_db_includes_schema_header(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.return_value = ""
                mock_rules.return_value = ""
                
                mock_get_strategy.return_value = mock_strategy
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert "DATABASE SCHEMA (postgres)" in result

    def test_analyze_db_includes_instructions(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.return_value = ""
                mock_rules.return_value = ""
                
                mock_get_strategy.return_value = mock_strategy
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert "INSTRUCTIONS FOR AI" in result

    def test_analyze_db_connection_error(self):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            mock_get_strategy.side_effect = ConnectionError("Failed to connect")
            
            result = tool_analyze_db(
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432
            )
            
            assert "Error" in result

    def test_analyze_db_schema_error(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.analysis.get_db_strategy') as mock_get_strategy:
            with patch('modules.DBAnalysis.tools.analysis.get_normalization_rules') as mock_rules:
                mock_strategy = MagicMock()
                mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
                mock_strategy.__exit__ = MagicMock(return_value=False)
                mock_strategy.get_schema_representation.side_effect = Exception("Schema error")
                mock_get_strategy.return_value = mock_strategy
                mock_rules.return_value = ""
                
                result = tool_analyze_db(
                    db_type="postgres",
                    host="localhost",
                    user="admin",
                    password="admin",
                    dbname="test_db",
                    port=5432
                )
                
                assert "Error" in result
