def format_schema(db_name: str, db_type: str, tables_and_columns: list, relationships: list) -> str:
    """Helper function to format the schema into a readable string."""
    schema_str = f"SCHEMA FOR {db_type.upper()} DATABASE '{db_name}':\n\n"
    
    current_table = None
    for row in tables_and_columns:
        table_name, column_name, data_type, is_nullable = row
        if table_name != current_table:
            schema_str += f"TABLE: {table_name}\n"
            current_table = table_name
        schema_str += f"  COLUMN: {column_name}, TYPE: {data_type}, NULLABLE: {is_nullable}\n"
    
    schema_str += "\nRELATIONSHIPS:\n"
    if relationships:
        for rel in relationships:
            fk_table, fk_column, pk_table, pk_column = rel
            schema_str += f"  {fk_table}.{fk_column} -> {pk_table}.{pk_column}\n"
    else:
        schema_str += "  No foreign key relationships found.\n"
        
    return schema_str