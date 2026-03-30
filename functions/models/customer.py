from pydantic import BaseModel
from enum import Enum
from models.address import Address
from models.document import Document


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
    email: str | None = None
    address: Address | None = None
    userId: str
    status: CustomerStatus
    createdAt: str  # isoformat string
