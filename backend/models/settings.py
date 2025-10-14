# models/settings.py
# Simple SQLModel model for application settings

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Settings(SQLModel, table=True):
    """
    Represents application settings stored in the database.

    Attributes:
        id: Primary key for the settings row. Optional because it is assigned by the DB.
        site_name: Human readable name of the site/application.
        configured_at: UTC timestamp when these settings were configured/created.
                       Defaults to current time using datetime.utcnow.
    """
    # Primary key: auto-assigned integer by the database
    id: Optional[int] = Field(default=None, primary_key=True)

    # Name of the site (required)
    site_name: str

    # Timestamp of when the settings were configured; defaults to current UTC time
    configured_at: datetime = Field(default_factory=datetime.utcnow)
