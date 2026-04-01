from pydantic import BaseModel


class Company(BaseModel):
    id: str
    name: str
    ownerUserId: str
    createdAt: str  # isoformat string
