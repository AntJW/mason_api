from pydantic import BaseModel
from enum import Enum


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Company(BaseModel):
    id: str
    name: str
    ownerUserId: str
    status: CompanyStatus
    statusUpdatedAt: str  # isoformat string
    createdAt: str  # isoformat string
