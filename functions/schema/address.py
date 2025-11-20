from pydantic import BaseModel

# TODO: Update and incorporate this schema into firebase functions, especially for validation.
# Using pydantic - https://docs.pydantic.dev/latest/


class Address(BaseModel):
    street: str
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None
