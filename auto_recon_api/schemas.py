from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class Message(BaseModel):
    message: str


class DomainPublic(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_atributes=True)


class EnterDomainSchema(BaseModel):
    domains: List[str]


class DomainSchema(BaseModel):
    domains: List[DomainPublic]


class DomainListItem(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    job_id: Optional[str] = None


class DomainListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[DomainListItem] = Field(default_factory=list)


class DomainResponseCreated(BaseModel):
    job_id: Optional[str] = None
    added: List[DomainListItem]
    already_exists: List[str]


class DeleteDomain(BaseModel):
    domain: str


class SubdomainSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain_id: int
    host: str
    ip: str
    created_at: datetime
    updated_at: datetime


class SubdomainResponse(BaseModel):
    total: int
    offset: int
    limit: int
    subdomains: List[SubdomainSchema] = Field(default_factory=list)


class FilterPage(BaseModel):
    offset: int = Field(ge=0, default=0)
    limit: int = Field(default=10, ge=1, le=200)


class FilterDomain(FilterPage):
    status: Optional[Literal['running', 'done', 'failed', 'queued']] = None
    q: Optional[str] = None

    @field_validator('q')
    @classmethod
    def _strip_q(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class JobDomainItem(BaseModel):
    id: int
    name: str
    status: str
    updated_at: Optional[str] = None
    error: Optional[str] = None


class UrlJobMeta(BaseModel):
    phase: Optional[str] = None
    seen: int = 0
    inserted: int = 0
    errors: int = 0
    last_error: Optional[str] = None


class JobMeta(BaseModel):
    domain_ids: List[int] = Field(default_factory=list)
    total: int = 0
    done: int = 0
    failed: int = 0

    done_domain_ids: List[int] = Field(default_factory=list)
    failed_domain_ids: List[int] = Field(default_factory=list)

    current_domain_id: Optional[int] = None
    current_domain: Optional[str] = None

    last_error: Optional[str] = None
    errors_by_domain: Dict[str, str] = Field(default_factory=dict)

    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None

    seen: int = 0
    inserted: int = 0
    phase: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    type: Literal['subdomains', 'urls']
    queue: str
    status: str
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    progress: Optional[float] = None
    meta: Union[JobMeta, UrlJobMeta]
    domains: List[JobDomainItem] = Field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class DiscoveredURLItem(BaseModel):
    id: int
    host: Optional[str] = None
    url: str
    hostname: Optional[str] = None
    port: Optional[int] = None
    status_code: Optional[int] = None
    title: Optional[str] = None
    tech: Optional[list] = None
    created_at: str


class PaginatedDiscoveredURLs(BaseModel):
    items: List[DiscoveredURLItem]
    next_cursor: Optional[int] = None


class UrlItem(BaseModel):
    id: int
    url: str
    host: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    status_code: Optional[int] = None
    title: Optional[str] = None
    tech: Optional[list] = None
    created_at: datetime


class UrlListResponse(BaseModel):
    next_cursor: Optional[str] = None
    items: List[UrlItem]


class UrlListFilters(BaseModel):
    cursor: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)

    q: Optional[str] = None
    host: Optional[str] = None
    status_code: Optional[int] = None
    ext: Optional[str] = None

    @field_validator('q')
    @classmethod
    def _strip_q(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator('ext')
    @classmethod
    def _norm_ext(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        v = v.lstrip('.')
        return v or None

    @field_validator('host')
    @classmethod
    def _strip_host(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        return v or None
