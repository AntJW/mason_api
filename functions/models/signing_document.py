from typing import Any

from pydantic import BaseModel, EmailStr

from models.signer import Signer
from models.signature_box import SignatureBox
from models.audit_log import AuditLog
from models.custom_data_types.quill_delta import QuillDelta


class SigningDocument(BaseModel):
    id: str
    name: str
    text: QuillDelta
    signer: Signer
    signatureBoxes: list[SignatureBox]
    adminName: str
    adminEmail: EmailStr
    adminMessage: str | None = None
    companyName: str | None = None
    auditLogs: list[AuditLog] | None = None
