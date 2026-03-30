from typing import Any

from pydantic import BaseModel, EmailStr

from models.signer import Signer
from models.signature_box import SignatureBox
from models.signature import Signature
from models.audit_log import AuditLog
from models.custom_data_types.quill_delta import QuillDelta


class SigningDocument(BaseModel):
    id: str
    name: str
    text: QuillDelta
    signer: Signer
    # Signature boxes associated with signer.
    signatureBoxes: list[SignatureBox]
    # Signatures associated with signer.
    signatures: list[Signature]
    adminName: str
    adminEmail: EmailStr
    adminMessage: str | None = None
    companyName: str | None = None
    auditLogs: list[AuditLog] | None = None
