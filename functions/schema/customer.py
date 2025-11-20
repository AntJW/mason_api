from pydantic import BaseModel

# TODO: Update and incorporate this schema into firebase functions, especially for validation.
# Using pydantic - https://docs.pydantic.dev/latest/


class Customer(BaseModel):
    id: int
    displayName: str
    firstName: str
    lastName: str
    email: str
    phone: str
    address: Address
    status: CustomerStatus
    userId: str
    createdAt: datetime
