from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, EmailStr


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    model_config = ConfigDict(from_atributes=True)


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


class DomainResponseCreated(BaseModel):
    added: List[DomainPublic]
    already_exists: List[str]


class DeleteDomain(BaseModel):
    domain: str
