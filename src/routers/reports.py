import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Engine

from dependencies import get_db_engine, get_s3_client
from reports import generate_invoices_report
from schemas import InvoiceReportRequest, InvoiceReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])
logger = logging.getLogger(__name__)


@router.post("/invoices", response_model=InvoiceReportResponse)
def create_invoices_report(
    filters: InvoiceReportRequest,
    engine: Engine = Depends(get_db_engine),
    s3_client=Depends(get_s3_client),
) -> InvoiceReportResponse:
    try:
        result = generate_invoices_report(
            engine=engine,
            s3_client=s3_client,
            date_from=filters.date_from,
            date_to=filters.date_to,
            date_field=filters.date_field or "issue_date",
            status_id=filters.status_id,
            uploaded_by=filters.uploaded_by,
            supplier_id=filters.supplier_id,
            currency=filters.currency,
            limit=filters.limit or 50000,
        )
        return InvoiceReportResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Reports] Error generating report: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {exc}")


@router.get("/invoices", response_model=InvoiceReportResponse)
def get_invoices_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    date_field: str = Query("issue_date", pattern=r"^(issue_date|created_at)$"),
    status_id: Optional[int] = Query(None),
    uploaded_by: Optional[int] = Query(None),
    supplier_id: Optional[int] = Query(None),
    currency: Optional[str] = Query(None, max_length=3),
    limit: int = Query(50000, ge=1, le=100000),
    engine: Engine = Depends(get_db_engine),
    s3_client=Depends(get_s3_client),
) -> InvoiceReportResponse:
    try:
        result = generate_invoices_report(
            engine=engine,
            s3_client=s3_client,
            date_from=date_from,
            date_to=date_to,
            date_field=date_field,
            status_id=status_id,
            uploaded_by=uploaded_by,
            supplier_id=supplier_id,
            currency=currency,
            limit=limit,
        )
        return InvoiceReportResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Reports] Error generating report: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {exc}")

