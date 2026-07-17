import re
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class DatabaseStrategy(ABC):
    """
    Abstract base class for a database analysis strategy.
    This defines the common interface for all database-specific implementations.
    """
    def __init__(self, connection_details: dict):
        """
        Initializes the strategy with the necessary connection details.
        
        :param connection_details: A dictionary containing user, password, host, port, and dbname.
        """
        self.connection_details = connection_details
        self.connection = None

    @abstractmethod
    def connect(self):
        """
        Establishes a connection to the database.
        Should raise an exception if the connection fails.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Closes the database connection.
        """
        pass

    @abstractmethod
    def get_schema_representation(self) -> str:
        """
        Retrieves the database schema and returns it as a single,
        descriptive string. This string will be used as context for the LLM.
        
        The representation should include:
        - Table names
        - Column names, data types, and nullability for each table
        - Primary key constraints
        - Foreign key relationships
        
        :return: A string detailing the database schema.
        """
        pass

    @staticmethod
    def _validate_read_only_query(query: str) -> str:
        cleaned = re.sub(r'(?m)^\s*(--|#).*$', '', query.strip())
        cleaned = re.sub(r'(?m)^\s*/\*.*?\*/', '', cleaned).strip()
        if not re.match(r'(SELECT|WITH)\s', cleaned, re.IGNORECASE):
            raise ValueError("Security violation: Only SELECT/WITH queries are allowed.")
        return cleaned

    @abstractmethod
    def execute_query(self, query: str) -> list[dict]:
        """
        Executes a raw SQL query (expected to be read-only) and returns results.
        
        :param query: The SQL SELECT query to execute.
        :return: A list of dictionaries, where each dictionary represents a row.
        """
        pass

    def __enter__(self):
        """Allows the strategy to be used as a context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures disconnection when the context is exited."""
        self.disconnect()
