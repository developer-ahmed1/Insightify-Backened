"""
Reports API — RFC §8 Scam Reporting.

POST /api/v1/reports — §8.1 Submit Scam Report
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.models.community import Report
from app.schemas.report import ScamReportRequest, ScamReportResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ScamReportResponse, status_code=201)
async def submit_report(
    request: ScamReportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a scam report."""
    report = Report(
        reporter_id=user.id,
        reason=request.reasonId,
        description=request.details,
        status="pending",
    )
    db.add(report)
    await db.flush()

    logger.info(f"Report submitted: {report.id} by user {user.id}")

    return ScamReportResponse(
        reportId=str(report.id),
        status="submitted",
    )
