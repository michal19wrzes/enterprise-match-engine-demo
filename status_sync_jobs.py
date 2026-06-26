"""Focused job module extracted from the original pipeline."""

from jobs_common import (
    hashlib,
    smtplib,
    MIMEMultipart,
    MIMEText,
    fetch_oracle_candidates,
    is_valid_first_supplier_refno,
    SMTP_FROM,
    fetch_oracle_candidate_positions,
    fetch_recent_external_documents,
    parse_external_datetime,
    datetime,
    timedelta,
    json,
    Product,
    fetch_products,
    func,
    ExternalDocumentItem,
    csv,
    Path,
    RegionMapper,
    TransportHeaderMatch,
    TransportPositionMatch,
    extract_delivery_note_refno,
    normalize_supplier_refno,
    registration_match,
    build_external_inspectorate_code,
    supplier_refno_match,
    extract_delivery_note_refno_parts,
    normalize_supplier_refno_parts,
    SessionLocal,
    fetch_partner_unit_mcodes,
    defaultdict,
    ExternalDocument,
    ExternalDocumentItemAggregate,
    ArticleNoMapper,
    ERPWeightTicket,
    ERPWeightTicketPosition,
    ExternalDocumentItemTranslated,
    TransportPositionBestMatch,
    FinalPositionMatch,
    ToManualEntry,
    OUTQueue,
    OUTQueueItem,
    math,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SUBJECT_PREFIX,
    SMTP_TO_ADMIN,
    SMTP_TO_USER,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USERNAME,
    parse_internal_supplier_refno,
    fetch_internal_product_sales_x,
    fetch_internal_product_sales_y,
    InternalProductSalesCache,
    InternalSalesMatch,
    Decimal,
    ROUND_HALF_UP,
    MANUAL_REASONS_ONLY_AFTER_21,
    ADMIN_REASON_FINAL_RETRY_FAILED,
    is_type3_supplier_refno,
    mark_ticket_as_manual_by_id,
    round_2,
    classify_type2_tickets,
    build_manual_entry_fingerprint,
    get_manual_notification_type,
    upsert_manual_entry,
    resolve_missing_manual_entries,
    floor_2,
    classify_tickets_by_supplier_ref,
)

def sync_ticket_status_from_outputs():
    print("START sync_ticket_status_from_outputs")

    with SessionLocal() as session:
        manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.erp_weight_ticket_id.isnot(None),
            )
            .all()
        }

        queue_ticket_ids = {
            row[0]
            for row in session.query(OUTQueue.erp_weight_ticket_id)
            .filter(
                OUTQueue.entry_status == "OPEN",
                OUTQueue.erp_weight_ticket_id.isnot(None),
            )
            .all()
        }

        updated_manual = 0
        updated_active = 0
        updated_no_output = 0

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.status != "REMOVED"
        ).all()

        for ticket in tickets:
            if ticket.id in manual_ticket_ids:
                if ticket.status != "MANUAL":
                    ticket.status = "MANUAL"
                    updated_manual += 1

            elif ticket.id in queue_ticket_ids:
                if ticket.status != "ACTIVE":
                    ticket.status = "ACTIVE"
                    updated_active += 1

            else:
                # techniczny stan przejściowy — po fallbacku nie powinien zostać
                if ticket.status != "NO_OUTPUT":
                    ticket.status = "NO_OUTPUT"
                    updated_no_output += 1

        session.commit()

    print(f"Ustawiono MANUAL: {updated_manual}")
    print(f"Ustawiono ACTIVE: {updated_active}")
    print(f"Ustawiono NO_OUTPUT: {updated_no_output}")
    print("KONIEC sync_ticket_status_from_outputs")

def sync_ticket_status_from_manual_entries():
    print("START sync_ticket_status_from_manual_entries")

    with SessionLocal() as session:
        manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        updated_active = 0
        updated_manual = 0

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.status != "REMOVED"
        ).all()

        for ticket in tickets:
            if ticket.id in manual_ticket_ids:
                if ticket.status != "MANUAL":
                    ticket.status = "MANUAL"
                    updated_manual += 1
            else:
                if ticket.status != "ACTIVE":
                    ticket.status = "ACTIVE"
                    updated_active += 1

        session.commit()

    print(f"Ustawiono ACTIVE: {updated_active}")
    print(f"Ustawiono MANUAL: {updated_manual}")
    print("KONIEC sync_ticket_status_from_manual_entries")
