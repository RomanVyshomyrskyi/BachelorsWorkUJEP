"""
Pydantic schemas for setup-related API requests.

These models validate input for:
- testing a database connection (TestDBRequest)
- performing initial application setup, including creating an admin user (InitRequest)
"""
from pydantic import BaseModel, EmailStr

class TestDBRequest(BaseModel):
    """Model for testing a database connection.

    Attributes:
        dsn: Database connection string (Data Source Name) used to attempt a connection.
    """
    dsn: str  # Database connection string (DSN)

class InitRequest(BaseModel):
    """Model for initial application setup.

    Attributes:
        dsn: Database connection string to initialize or connect the application's DB.
        site_name: Human-readable name/title of the site/application.
        admin_email: Email address for the initial admin user (validated as an email).
        admin_password: Plaintext password for the initial admin user. Handle securely:
                        do not log it and store only a hashed version.
    """
    dsn: str  # Database connection string (DSN) for initialization
    site_name: str  # Display name for the site/application
    admin_email: EmailStr  # Admin user's email (validated)
    admin_password: str  # Admin user's password (ensure hashing before storing)
