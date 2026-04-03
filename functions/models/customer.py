from pydantic import BaseModel, EmailStr
from enum import Enum
from models.address import Address


class CustomerStatus(str, Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDEFINED = "undefined"


class Customer(BaseModel):
    id: str
    displayName: str
    firstName: str | None = None
    lastName: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: Address | None = None
    createdByUserId: str
    companyId: str
    status: CustomerStatus
    statusUpdatedAt: str  # isoformat string
    createdAt: str  # isoformat string
