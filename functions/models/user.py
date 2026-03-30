from pydantic import BaseModel


class User(BaseModel):
    id: str
    displayName: str
    firstName: str
    lastName: str
    email: str
    createdAt: str  # isoformat string
