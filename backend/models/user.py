from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    """User model representing an account in the system.

    This SQLModel-backed class maps to the users table and stores essential
    authentication and authorization data.

    Attributes:
        id: Auto-incrementing primary key.
        email: Unique, indexed email address used for login/identification.
        password_hash: Secure hash of the user's password (never store plaintext).
        is_admin: Flag indicating administrative privileges.
        created_at: UTC timestamp when the account was created.
        api_keys: List of API keys issued to the user (store hashed/rotated if needed).

    Notes:
        - Keep password handling and API key storage secure (hashing, limited exposure).
        - Avoid exposing sensitive fields in logs or API responses.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
