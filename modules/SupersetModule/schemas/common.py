"""
Common Pydantic schemas for shared data structures across Superset API modules.

Provides base response wrappers (list/detail), pagination metadata,
resource identifiers, user info, feature flags, and instance info models
used by all other schema modules.
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class SupersetListResponse(BaseModel, Generic[T]):
    """
    Generic wrapper for paginated list responses from Superset API endpoints.

    Used when fetching collections like charts, dashboards, databases, or datasets.
    Contains the total count, the list of items, optional IDs, and an error message.
    """
    count: int = 0  # Total number of items in the collection
    result: List[T] = Field(default_factory=list)  # List of items of type T
    ids: Optional[List[int]] = None  # IDs of the returned items (optional shortcut)
    error: Optional[str] = None  # Error message if the request failed


class SupersetDetailResponse(BaseModel, Generic[T]):
    """
    Generic wrapper for single resource detail responses from Superset API.

    Used when fetching a specific resource by ID (e.g., a single chart or dashboard).
    Contains the resource data or an error message.
    """
    result: Optional[T] = None  # The resource data of type T, if found
    error: Optional[str] = None  # Error message if the request failed


class PaginationMeta(BaseModel):
    """
    Pagination metadata for paginated API requests and responses.

    Tracks the current page, page size, and total item count for
    implementing pagination in list endpoints.
    """
    page: int = 1  # Current page number (1-indexed)
    page_size: int = 100  # Number of items per page
    total_count: int = 0  # Total number of items across all pages


class ResourceIdentifier(BaseModel):
    """
    Minimal reference to a Superset resource by ID and optional name.

    Used to reference related resources (e.g., charts, dashboards) without
    fetching their full details.
    """
    id: int  # Unique resource identifier
    name: Optional[str] = None  # Human-readable name (optional)


class UserInfo(BaseModel):
    """
    Current Superset user information from the instance info endpoint.

    Describes the authenticated user session, including identity fields,
    active status, and anonymity flag.
    """
    id: int  # User's unique ID in Superset
    username: str  # User's login username
    first_name: str = ""  # User's first name
    last_name: str = ""  # User's last name
    email: str = ""  # User's email address
    is_active: bool = True  # Whether the user account is active
    is_anonymous: bool = False  # Whether the session is anonymous


class FeatureFlags(BaseModel):
    """
    Superset feature flags response model.

    Holds the dictionary of enabled/disabled feature flags from the
    Superset instance, used to conditionally enable functionality.
    """
    result: Dict[str, Any] = Field(default_factory=dict)  # Key-value pairs of feature flag names and their states


class InstanceInfo(BaseModel):
    """
    Full Superset instance information from the /api/v1/superset/info endpoint.

    Aggregates current user info, feature flags, and version string
    for use in feature detection and user context awareness.
    """
    user: Optional[UserInfo] = None  # Authenticated user details, if logged in
    features: Dict[str, Any] = Field(default_factory=dict)  # Feature flag key-value map
    version: Optional[str] = None  # Superset version string (e.g., "4.0.0")
