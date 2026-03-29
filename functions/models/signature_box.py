from pydantic import BaseModel, ConfigDict

defaultWidthFrac = 0.40
defaultHeightFrac = 0.08


class SignatureBox(BaseModel):
    pageNumber: int
    fracX: float
    fracY: float
    widthFrac: float = defaultWidthFrac
    heightFrac: float = defaultHeightFrac
    id: str
    signerId: str
    signatureId: str | None = None
