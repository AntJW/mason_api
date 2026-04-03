from enum import Enum
from pydantic import BaseModel, EmailStr


# sent - Invitation sent to signer
# opened - Signer opened the invitation
# completed - Signer completed the signature
# canceled - Invitation canceled by user who sent the invitation
# declined - Signer declined the invitation
class InvitationStatus(str, Enum):
    SENT = "sent"
    OPENED = "opened"
    COMPLETED = "completed"
    CANCELED = "canceled"
    DECLINED = "declined"
    EXPIRED = "expired"


class Invitation(BaseModel):
    id: str
    signerId: str
    name: str
    email: EmailStr
    documentId: str
    companyId: str
    token: str
    status: InvitationStatus
    sentAt: str  # isoformat string
    expiresAt: str  # isoformat string
    openedAt: str | None = None  # isoformat string
    completedAt: str | None = None  # isoformat string
    canceledAt: str | None = None  # isoformat string
    canceledReason: str | None = None
    canceledBy: str | None = None
    declinedAt: str | None = None  # isoformat string
    declinedReason: str | None = None
    lastReminderAt: str | None = None  # isoformat string
    reminderCount: int
    lastViewedAt: str | None = None  # isoformat string
