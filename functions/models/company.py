from pydantic import BaseModel


class Company(BaseModel):
    id: str
    name: str
    adminUserId: str
    createdAt: str  # isoformat string
