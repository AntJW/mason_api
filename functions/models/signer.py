from pydantic import BaseModel, EmailStr


class Signer(BaseModel):
    id: str
    name: str
    email: EmailStr
    color: int  # ARGB32 color
    userId: str | None = None  # id of user. null if signer is not a user.
    # id of customer. null if signer is not a customer.
    customerId: str | None = None
    createdAt: str  # isoformat string
    updatedAt: str | None = None  # isoformat string
