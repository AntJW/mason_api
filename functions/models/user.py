from pydantic import BaseModel, EmailStr
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"


class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class User(BaseModel):
    id: str
    displayName: str
    firstName: str
    lastName: str
    email: EmailStr
    companyId: str
    role: UserRole
    status: UserStatus
    statusUpdatedAt: str  # isoformat string
    createdAt: str  # isoformat string
