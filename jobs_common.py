import csv
import hashlib
import json
import math
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy import func

from config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SUBJECT_PREFIX,
    SMTP_TO_ADMIN,
    SMTP_TO_USER,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)
from database import SessionLocal
from external_api_client import fetch_recent_external_documents
from models import (
    ArticleNoMapper,
    ERPWeightTicket,
    ERPWeightTicketPosition,
    ExternalDocument,
    ExternalDocumentItem,
    ExternalDocumentItemAggregate,
    ExternalDocumentItemTranslated,
    FinalPositionMatch,
    InternalProductSalesCache,
    InternalSalesMatch,
    OUTQueue,
    OUTQueueItem,
    Product,
    RegionMapper,
    ToManualEntry,
    TransportHeaderMatch,
    TransportPositionBestMatch,
    TransportPositionMatch,
)
from oracle_client import (
    fetch_internal_product_sales_x,
    fetch_internal_product_sales_y,
    fetch_oracle_candidate_positions,
    fetch_oracle_candidates,
    fetch_partner_unit_mcodes,
    fetch_products,
)
from utils import (
    build_external_inspectorate_code,
    extract_delivery_note_refno,
    extract_delivery_note_refno_parts,
    is_valid_first_supplier_refno,
    normalize_supplier_refno,
    normalize_supplier_refno_parts,
    parse_external_datetime,
    parse_internal_supplier_refno,
    registration_match,
    supplier_refno_match,
)

MANUAL_REASONS_ONLY_AFTER_21 = {
    "Nie znaleziono dopasowania Nr. Dok. Dostawy REF do numerów w kwicie zewnętrznym",
    "Nie znaleziono dopasowania pozycji SRC do dokumentu external",
    "Nie znaleziono dopasowania nagłówka SRC do dokumentu external",
    "Nie zbudowano finalnego dopasowania pozycji SRC do dokumentu external",
    
}
ADMIN_REASON_FINAL_RETRY_FAILED = (
    "Admin: final match istnieje, ale nie udało się zbudować OUT"
)

def is_type3_supplier_refno(value: str | None) -> bool:
    if not value:
        return False
    return "SRC_C" in value.upper()

def mark_ticket_as_manual_by_id(session, erp_weight_ticket_id):
    if not erp_weight_ticket_id:
        return False

    ticket = session.query(ERPWeightTicket).filter(
        ERPWeightTicket.id == erp_weight_ticket_id
    ).first()

    if not ticket:
        return False

    if ticket.status != "MANUAL":
        ticket.status = "MANUAL"
        return True

    return False

def round_2(value: float | None) -> float | None:
    if value is None:
        return None
    return float(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

def classify_type2_tickets(rows_pos):
    allowed_supplier_codes = {"HKBS01", "HMIE22", "HMIE70"}

    positions_by_ticket = defaultdict(list)
    for row in rows_pos:
        ticket_number = str(row[0])
        positions_by_ticket[ticket_number].append(row)

    valid_ticket_numbers = set()
    manual_ticket_numbers = set()
    manual_details = {}

    for ticket_number, pos_rows in positions_by_ticket.items():
        pos_rows = sorted(pos_rows, key=lambda r: (r[1] is None, r[1]))

        if not pos_rows:
            continue

        first_row = pos_rows[0]
        first_supplier_code = str(first_row[12]).strip() if first_row[12] is not None else None

        if first_supplier_code not in allowed_supplier_codes:
            continue

        invalid_positions = []

        for row in pos_rows:
            pos_number = row[1]
            supplier_refno = row[6]

            cdu_id, external_ticket_number = parse_internal_supplier_refno(supplier_refno)

            if not cdu_id or not external_ticket_number:
                invalid_positions.append(
                    f"pos={pos_number}, supplier_refno={supplier_refno}, error=Nie rozpoznano numeru REF na spółce źródłowej"
                )

        if invalid_positions:
            manual_ticket_numbers.add(ticket_number)
            manual_details[ticket_number] = " | ".join(invalid_positions)
        else:
            valid_ticket_numbers.add(ticket_number)

    return valid_ticket_numbers, manual_ticket_numbers, manual_details

def build_manual_entry_fingerprint(ticket_number, reason, details):
    payload = "|".join([
        str(ticket_number or "").strip(),
        str(reason or "").strip(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def get_manual_notification_type(ticket_number):
    return "USER" if ticket_number else "ADMIN"

def upsert_manual_entry(
    session,
    *,
    erp_weight_ticket_id=None,
    ticket_number=None,
    timestamp_in=None,
    truck_regnumber=None,
    first_pos_supplier_refno=None,
    position_count=None,
    reason=None,
    details=None,
    now=None,
):
    now = now or datetime.utcnow()
    fingerprint = build_manual_entry_fingerprint(ticket_number, reason, details)
    notification_type = get_manual_notification_type(ticket_number)

    row = session.query(ToManualEntry).filter(ToManualEntry.fingerprint == fingerprint).first()

    if row is None:
        row = ToManualEntry(
            erp_weight_ticket_id=erp_weight_ticket_id,
            ticket_number=ticket_number,
            timestamp_in=timestamp_in,
            truck_regnumber=truck_regnumber,
            first_pos_supplier_refno=first_pos_supplier_refno,
            position_count=position_count,
            reason=reason,
            details=details,
            notification_type=notification_type,
            notification_status="NEW",
            entry_status="OPEN",
            fingerprint=fingerprint,
            first_detected_at=now,
            last_seen_at=now,
            resolved_at=None,
        )
        session.add(row)
        return row, True, False

    was_closed = row.entry_status != "OPEN"

    row.erp_weight_ticket_id = erp_weight_ticket_id
    row.ticket_number = ticket_number
    row.timestamp_in = timestamp_in
    row.truck_regnumber = truck_regnumber
    row.first_pos_supplier_refno = first_pos_supplier_refno
    row.position_count = position_count
    row.reason = reason
    row.details = details
    row.notification_type = notification_type
    row.entry_status = "OPEN"
    row.last_seen_at = now
    row.resolved_at = None

    if row.notification_status not in ("SENT", "FAILED"):
        row.notification_status = "NEW"
        
    if erp_weight_ticket_id:
        ticket = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.id == erp_weight_ticket_id
        ).first()
        if ticket and ticket.status != "MANUAL":
            ticket.status = "MANUAL"

    return row, False, was_closed

def resolve_missing_manual_entries(session, active_fingerprints, reasons, now=None):
    q = session.query(ToManualEntry).filter(
        ToManualEntry.reason.in_(list(reasons)),
    )
    for row in q.all():
        if row.fingerprint not in active_fingerprints:
            session.delete(row)

def floor_2(value: float | None) -> float | None:
    if value is None:
        return None
    return math.floor(float(value) * 100) / 100

def classify_tickets_by_supplier_ref(rows_pos, allowed_mcodes=None):
    positions_by_ticket = defaultdict(list)

    for row in rows_pos:
        ticket_number = str(row[0])
        positions_by_ticket[ticket_number].append(row)

    valid_ticket_numbers = set()
    manual_ticket_numbers = set()
    manual_details = {}
    type3_ticket_numbers = set()

    for ticket_number, pos_rows in positions_by_ticket.items():
        # sort po POSNUMBER rosnąco
        pos_rows = sorted(pos_rows, key=lambda r: (r[1] is None, r[1]))

        if not pos_rows:
            continue

        first_row = pos_rows[0]
        first_supplier_refno = first_row[6]
        first_supplier_code = first_row[12]

        # warunek 1:
        # pierwsza pozycja musi mieć supplier_refno z dokładnie jednym "/"
        # i minimum 6 znaków
        if first_supplier_refno is None:
            continue

        first_supplier_refno = str(first_supplier_refno).strip()
        
        if is_type3_supplier_refno(first_supplier_refno):
            type3_ticket_numbers.add(ticket_number)
            continue
            
        if first_supplier_refno.count("/") != 1:
            continue

        if len(first_supplier_refno) < 6:
            continue

        # warunek 2:
        # first_pos_mcode musi być w allowed_mcodes
        if allowed_mcodes is not None:
            if first_supplier_code is None:
                continue

            first_supplier_code = str(first_supplier_code).strip()
            if first_supplier_code not in allowed_mcodes:
                continue

        # warunek 3:
        # jeśli jakakolwiek inna pozycja nie ma "/" -> manual
        invalid_other_positions = []

        for row in pos_rows[1:]:
            other_supplier_refno = row[6]

            if other_supplier_refno is None:
                invalid_other_positions.append(
                    f"pos={row[1]}, supplier_refno=None"
                )
                continue

            other_supplier_refno = str(other_supplier_refno).strip()

            if "/" not in other_supplier_refno:
                invalid_other_positions.append(
                    f"pos={row[1]}, supplier_refno={other_supplier_refno}"
                )

        if invalid_other_positions:
            manual_ticket_numbers.add(ticket_number)
            manual_details[ticket_number] = " | ".join(invalid_other_positions)
        else:
            valid_ticket_numbers.add(ticket_number)

    return valid_ticket_numbers, manual_ticket_numbers, manual_details, type3_ticket_numbers

