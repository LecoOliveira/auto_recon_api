from typing import List

from pydantic import BaseModel


class SubdomainSchema(BaseModel):
    host: str
    ip: str


class SubdomainResponse(BaseModel):
    subdomains: List[SubdomainSchema]
