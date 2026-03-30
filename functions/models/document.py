from enum import Enum
from pydantic import BaseModel

from models.signer import Signer
from models.signature_box import SignatureBox
from models.signature import Signature
from models.audit_log import AuditLog
from models.invitation import Invitation
from models.custom_data_types.quill_delta import QuillDelta


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PREPARED = "prepared"
    SENT = "sent"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Document(BaseModel):
    id: str
    name: str
    text: QuillDelta
    plainText: str
    createdAt: str  # isoformat string
    customerId: str
    signers: list[Signer] | None = None
    signatureBoxes: list[SignatureBox] | None = None
    signatures: list[Signature] | None = None
    storagePath: str | None = None
    sourceTemplateId: str | None = None  # required if created from a template
    status: DocumentStatus
    invitations: list[Invitation] | None = None
    auditLogs: list[AuditLog] | None = None
