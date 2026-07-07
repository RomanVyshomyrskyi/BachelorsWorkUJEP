import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

from modules.DBAnalysis.utils.formatters import format_schema


class TestFormatSchema:
    def test_format_schema_returns_string(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgres", sample_table_data, sample_relationships)
        assert isinstance(result, str)

    def test_format_schema_includes_database_name(self, sample_table_data, sample_relationships):
        result = format_schema("my_database", "postgres", sample_table_data, sample_relationships)
        assert "my_database" in result

    def test_format_schema_includes_database_type(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgresql", sample_table_data, sample_relationships)
        assert "POSTGRESQL" in result

    def test_format_schema_includes_table_names(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgres", sample_table_data, sample_relationships)
        assert "TABLE: users" in result
        assert "TABLE: orders" in result

    def test_format_schema_includes_column_info(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgres", sample_table_data, sample_relationships)
        assert "COLUMN: id" in result
        assert "COLUMN: name" in result
        assert "TYPE: integer" in result
        assert "TYPE: character varying" in result
        assert "TYPE: numeric" in result

    def test_format_schema_includes_nullable_info(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgres", sample_table_data, sample_relationships)
        assert "NULLABLE: NO" in result
        assert "NULLABLE: YES" in result

    def test_format_schema_includes_relationships(self, sample_table_data, sample_relationships):
        result = format_schema("test_db", "postgres", sample_table_data, sample_relationships)
        assert "RELATIONSHIPS:" in result
        assert "orders.user_id -> users.id" in result

    def test_format_schema_no_relationships(self, sample_table_data):
        result = format_schema("test_db", "postgres", sample_table_data, [])
        assert "No foreign key relationships found." in result

    def test_format_schema_multiple_tables(self):
        tables = [
            ("users", "id", "integer", "NO"),
            ("users", "name", "varchar", "NO"),
            ("posts", "id", "integer", "NO"),
            ("posts", "title", "varchar", "YES"),
            ("comments", "id", "integer", "NO"),
        ]
        result = format_schema("blog_db", "postgres", tables, [])
        
        assert "TABLE: users" in result
        assert "TABLE: posts" in result
        assert "TABLE: comments" in result

    def test_format_schema_table_order_preserved(self):
        tables = [
            ("z_table", "id", "integer", "NO"),
            ("a_table", "id", "integer", "NO"),
            ("m_table", "id", "integer", "NO"),
        ]
        result = format_schema("test_db", "postgres", tables, [])
        
        z_pos = result.find("TABLE: z_table")
        a_pos = result.find("TABLE: a_table")
        m_pos = result.find("TABLE: m_table")
        
        assert z_pos < a_pos < m_pos

    def test_format_schema_relationship_format(self):
        tables = [("users", "id", "integer", "NO")]
        relationships = [
            ("orders", "user_id", "users", "id"),
            ("payments", "order_id", "orders", "id"),
        ]
        result = format_schema("test_db", "postgres", tables, relationships)
        
        assert "orders.user_id -> users.id" in result
        assert "payments.order_id -> orders.id" in result

    def test_format_schema_header_format(self):
        tables = [("users", "id", "integer", "NO")]
        result = format_schema("mydb", "postgresql", tables, [])
        
        assert "SCHEMA FOR POSTGRESQL DATABASE" in result
        assert "'mydb'" in result
