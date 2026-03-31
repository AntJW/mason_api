from pydantic import BaseModel
from enum import Enum


class AuditLogAction(str, Enum):
    DOCUMENT_CREATED = "documentCreated"
    DOCUMENT_UPDATED = "documentUpdated"
    DOCUMENT_DELETED = "documentDeleted"
    DOCUMENT_COMPLETED = "documentCompleted"
    INVITATION_SENT = "invitationSent"
    INVITATION_RESENT = "invitationResent"
    INVITATION_OPENED = "invitationOpened"
    INVITATION_EXPIRED = "invitationExpired"
    INVITATION_CANCELED = "invitationCanceled"
    INVITATION_DECLINED = "invitationDeclined"
    SIGNATURE_COMPLETED = "signatureCompleted"


class AuditLogActorRole(str, Enum):
    USER = "user"
    SIGNER = "signer"
    SYSTEM = "system"


class AuditLogTargetType(str, Enum):
    DOCUMENT = "document"
    INVITATION = "invitation"
    SIGNATURE = "signature"


class AuditLogTarget(BaseModel):
    id: str
    type: AuditLogTargetType


class AuditLogMetadata(BaseModel):
    reason: str | None = None
    method: str | None = None


class AuditLogActor(BaseModel):
    id: str | None = None
    role: AuditLogActorRole
    name: str | None = None
    email: str | None = None
    ipAddress: str | None = None
    userAgent: str | None = None


class AuditLog(BaseModel):
    id: str
    documentId: str
    timestamp: str  # isoformat string
    action: AuditLogAction
    actor: AuditLogActor
    target: AuditLogTarget
    metadata: AuditLogMetadata | None = None
    signerId: str | None = None
