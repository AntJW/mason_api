from pydantic import BaseModel


class Address(BaseModel):
    street: str | None = None
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None
