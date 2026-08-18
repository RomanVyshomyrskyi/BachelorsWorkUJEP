"""
Formatters - Schema representation formatting utilities.

Provides functions to convert database schema metadata (tables, columns,
relationships) into human-readable string representations for use in
LLM context and analysis reports.
"""


def format_schema(db_name: str, db_type: str, tables_and_columns: list, relationships: list) -> str:
    """
    Format database schema metadata into a human-readable string representation.

    This function takes raw schema data (tables with columns and their metadata,
    plus foreign key relationships) and produces a structured text output that
    clearly shows the database structure for LLM consumption and analysis.
        1. Creates a header line with the database name and type.
        2. Iterates through the tables_and_columns list, creating a TABLE section
           for each unique table and listing its columns with details.
        3. Appends a RELATIONSHIPS section listing all foreign key relationships
           or a message if no relationships exist.

    Args:
        db_name: The name of the database being described.
        db_type: The type of database (e.g., "PostgreSQL", "MariaDB", "MSSQL").
        tables_and_columns: A list of tuples, each containing:
            (table_name, column_name, data_type, is_nullable).
        relationships: A list of tuples, each containing:
            (foreign_table, foreign_column, primary_table, primary_column).

    Returns:
        A formatted string with the database schema structure, including
        table listings, column details, and foreign key relationships.
    """
    # Create a header identifying the database name and type
    schema_str = f"SCHEMA FOR {db_type.upper()} DATABASE '{db_name}':\n\n"

    # Track the last table name to avoid repeating it for each column
    current_table = None

    # Iterate through all table/column rows from the schema query
    for row in tables_and_columns:
        table_name, column_name, data_type, is_nullable = row

        # When encountering a new table, add a TABLE header line
        if table_name != current_table:
            schema_str += f"TABLE: {table_name}\n"
            current_table = table_name

        # Append the column details indented under its table
        schema_str += f"  COLUMN: {column_name}, TYPE: {data_type}, NULLABLE: {is_nullable}\n"

    # Append the relationships section header
    schema_str += "\nRELATIONSHIPS:\n"

    # If foreign key relationships exist, list each one with its source and target
    if relationships:
        for rel in relationships:
            fk_table, fk_column, pk_table, pk_column = rel
            schema_str += f"  {fk_table}.{fk_column} -> {pk_table}.{pk_column}\n"
    else:
        # Indicate that no foreign key relationships were found
        schema_str += "  No foreign key relationships found.\n"

    return schema_str
