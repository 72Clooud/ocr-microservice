import io
import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy import Engine, text

from config import settings

logger = logging.getLogger(__name__)

RENAME_COLUMNS = {
    "invoice_id": "ID Faktury",
    "invoice_number": "Numer Faktury",
    "issue_date": "Data Wystawienia",
    "created_at": "Data Utworzenia",
    "currency": "Waluta",
    "net_amount": "Kwota Netto",
    "gross_amount": "Kwota Brutto",
    "status_id": "Status ID",
    "supplier_id": "ID Dostawcy",
    "uploaded_by": "ID Użytkownika",
    "rejection_reason": "Powód Odrzucenia",
    "file_path": "Ścieżka Pliku",
}


def generate_invoices_report(
    engine: Engine,
    s3_client: Any,
    bucket: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    date_field: str = "issue_date",
    status_id: Optional[int] = None,
    uploaded_by: Optional[int] = None,
    supplier_id: Optional[int] = None,
    currency: Optional[str] = None,
    limit: int = 50000,
) -> dict:
    bucket_name = bucket or settings.REPORTS_BUCKET_NAME
    if not bucket_name:
        raise ValueError("MinIO reports bucket name is not configured.")

    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from nie może być późniejsza niż date_to.")

    target_date_col = "created_at" if date_field == "created_at" else "issue_date"

    clauses = []
    params = {}

    if uploaded_by is not None:
        clauses.append("uploaded_by = :uploaded_by")
        params["uploaded_by"] = uploaded_by

    if status_id is not None:
        clauses.append("status_id = :status_id")
        params["status_id"] = status_id

    if supplier_id is not None:
        clauses.append("supplier_id = :supplier_id")
        params["supplier_id"] = supplier_id

    if currency is not None:
        clauses.append("currency = :currency")
        params["currency"] = currency

    if date_from is not None:
        clauses.append(f"{target_date_col} >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        clauses.append(f"{target_date_col} <= :date_to")
        params["date_to"] = date_to

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    params["limit"] = max(1, min(limit, 100000))

    query_str = f"""
        SELECT 
            invoice_id,
            invoice_number,
            issue_date,
            created_at,
            currency,
            net_amount,
            gross_amount,
            status_id,
            supplier_id,
            uploaded_by,
            rejection_reason,
            file_path
        FROM invoices
        {where_sql}
        ORDER BY {target_date_col} DESC, invoice_id DESC
        LIMIT :limit
    """

    with engine.connect() as conn:
        df = pd.read_sql(text(query_str), conn, params=params)

    export_df = df.rename(columns=RENAME_COLUMNS)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Faktury")
    buffer.seek(0)

    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    filename = f"raport_faktury_{timestamp_str}_{rand_suffix}.xlsx"
    file_path = f"invoices/{filename}"

    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except Exception:
        try:
            s3_client.create_bucket(Bucket=bucket_name)
        except Exception as e:
            logger.warning(f"[Reports] Could not ensure bucket '{bucket_name}': {e}")

    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_path,
        Body=buffer.getvalue(),
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    logger.info(f"[Reports] Report '{filename}' ({len(df)} rows) uploaded to MinIO at '{bucket_name}/{file_path}'")

    download_url = None
    if settings.MINIO_EXTERNAL_URL:
        download_url = f"{settings.MINIO_EXTERNAL_URL.rstrip('/')}/{bucket_name}/{file_path}"

    return {
        "file_path": file_path,
        "bucket": bucket_name,
        "filename": filename,
        "download_url": download_url,
        "rows_count": len(df),
        "generated_at": now.isoformat(),
    }
