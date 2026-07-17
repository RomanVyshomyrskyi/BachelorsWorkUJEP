from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class SupersetListResponse(BaseModel, Generic[T]):
    count: int = 0
    result: List[T] = Field(default_factory=list)
    ids: Optional[List[int]] = None
    error: Optional[str] = None


class SupersetDetailResponse(BaseModel, Generic[T]):
    result: Optional[T] = None
    error: Optional[str] = None


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = 100
    total_count: int = 0


class ResourceIdentifier(BaseModel):
    id: int
    name: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    username: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    is_active: bool = True
    is_anonymous: bool = False


class FeatureFlags(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict)


class InstanceInfo(BaseModel):
    user: Optional[UserInfo] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[str] = None
