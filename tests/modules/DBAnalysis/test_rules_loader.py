import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.utils.rules_loader import get_normalization_rules


class TestGetNormalizationRules:
    def test_returns_string(self):
        result = get_normalization_rules()
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        result = get_normalization_rules()
        assert len(result) > 0

    def test_contains_normalization_rules(self):
        result = get_normalization_rules()
        assert "1NF" in result or "First Normal Form" in result
        assert "2NF" in result or "Second Normal Form" in result
        assert "3NF" in result or "Third Normal Form" in result

    def test_contains_rules_section(self):
        result = get_normalization_rules()
        assert "Rule" in result or "rule" in result.lower()

    def test_returns_error_message_when_file_missing(self, monkeypatch):
        import modules.DBAnalysis.utils.rules_loader as rules_module
        
        original_path = os.path.join(
            os.path.dirname(os.path.dirname(rules_module.__file__)),
            "normalization_rules.md"
        )
        
        def mock_join(*args):
            return "/nonexistent/path/normalization_rules.md"
        
        monkeypatch.setattr('os.path.join', mock_join)
        
        result = get_normalization_rules()
        assert "Error: Normalization rules file not found" in result
