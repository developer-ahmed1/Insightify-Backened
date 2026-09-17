"""
Report schemas — RFC §8 Scam Reporting.
"""
from typing import List, Optional
from pydantic import Field
from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# §8.1 Submit Scam Report
# ---------------------------------------------------------------------------
class ScamReportRequest(BaseSchema):
    """
    POST /api/v1/reports — RFC §8.1

    User submits a scam report with a reason, details, and optional evidence.
    """
    reasonId: str  # phishing | scam | malware | spam | other
    details: Optional[str] = Field(None, max_length=2000)
    evidence: List[str] = []  # List of evidence URLs
    threatContext: Optional[dict] = None
    # e.g. {"scanId": "scan_001"} or {"threatId": "threat_001"}


class ScamReportResponse(BaseSchema):
    """Report submission confirmation."""
    reportId: str
    status: str = "submitted"
    message: str = "Report submitted successfully. Thank you for keeping the community safe."


# ---------------------------------------------------------------------------
# Admin: Report Management
# ---------------------------------------------------------------------------
class AdminReportListItem(BaseSchema):
    """Admin view of a report."""
    id: str
    reporterId: Optional[str] = None
    reporterName: Optional[str] = None
    reasonId: str
    details: Optional[str] = None
    status: str  # pending | reviewed | dismissed | action_taken
    createdAt: str
    resolvedAt: Optional[str] = None


class AdminReportActionRequest(BaseSchema):
    """Admin action on a report."""
    action: str  # approve | dismiss | action_taken
    resolutionNotes: Optional[str] = None
