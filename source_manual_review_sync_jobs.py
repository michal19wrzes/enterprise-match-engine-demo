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

def sync_type2_invalid_supplier_refno_manual_entries():
    print("START sync_type2_invalid_supplier_refno_manual_entries")

    rows_pos = fetch_oracle_candidate_positions()
    _, manual_ticket_numbers, manual_details = classify_type2_tickets(rows_pos)

    rows = fetch_oracle_candidates()
    deduped = {}
    for row in rows:
        ticket_number = str(row[0])
        if ticket_number in manual_ticket_numbers:
            deduped[ticket_number] = row

    rows = list(deduped.values())
    now = datetime.utcnow()
    active_fingerprints = set()
    inserted = 0
    updated = 0

    with SessionLocal() as session:
        ticket_map = {
            row.ticket_number: row
            for row in session.query(ERPWeightTicket).all()
        }
        for row in rows:
            (
                ticket_number,
                timestamp_in,
                processing_status,
                truck_regnumber,
                vehicletype,
                length1,
                width1,
                height1,
                gap1,
                quantity_rm1,
                length2,
                width2,
                height2,
                gap2,
                quantity_rm2,
            ) = row

            ticket_number = str(ticket_number)
            details = manual_details.get(ticket_number)

            fingerprint = build_manual_entry_fingerprint(
                ticket_number,
                "Nie rozpoznano numeru REF na spółce źródłowej",
                details,
            )
            active_fingerprints.add(fingerprint)

            ticket = ticket_map.get(ticket_number)

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id if ticket else None,
                ticket_number=ticket_number,
                timestamp_in=timestamp_in,
                truck_regnumber=truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno if ticket else None,
                position_count=ticket.position_count if ticket else None,
                reason="Nie rozpoznano numeru REF na spółce źródłowej",
                details=details,
                now=now,
            )

            if created:
                inserted += 1
            else:
                updated += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {"Nie rozpoznano numeru REF na spółce źródłowej"},
            now=now,
        )
        session.commit()

    print(f"Dodano do manual entry: {inserted}")
    print(f"Zaktualizowano manual entry: {updated}")
    print("KONIEC sync_type2_invalid_supplier_refno_manual_entries")


def sync_to_manual_entry():
    print("START sync_to_manual_entry")

    rows_pos = fetch_oracle_candidate_positions()
    valid_ticket_numbers, manual_ticket_numbers, manual_details, type3_ticket_numbers = classify_tickets_by_supplier_ref(rows_pos)

    rows = fetch_oracle_candidates()
    deduped = {}
    for row in rows:
        ticket_number = str(row[0])
        if ticket_number in manual_ticket_numbers:
            deduped[ticket_number] = row

    rows = list(deduped.values())
    now = datetime.utcnow()
    active_fingerprints = set()
    inserted = 0
    updated = 0

    with SessionLocal() as session:
        for row in rows:
            ticket_map = {
                row.ticket_number: row
                for row in session.query(ERPWeightTicket).all()
            }
            (
                ticket_number,
                timestamp_in,
                processing_status,
                truck_regnumber,
                vehicletype,
                length1,
                width1,
                height1,
                gap1,
                quantity_rm1,
                length2,
                width2,
                height2,
                gap2,
                quantity_rm2,
            ) = row

            ticket_number = str(ticket_number)
            details = manual_details.get(ticket_number)
            fingerprint = build_manual_entry_fingerprint(ticket_number, "Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02", details)
            active_fingerprints.add(fingerprint)
            ticket = ticket_map.get(ticket_number)

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id if ticket else None,
                ticket_number=ticket_number,
                timestamp_in=timestamp_in,
                truck_regnumber=truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno if ticket else None,
                position_count=ticket.position_count if ticket else None,
                reason="Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02",
                details=details,
                now=now,
            )
            if created:
                inserted += 1
            else:
                updated += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {"Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02"},
            now=now,
        )
        session.commit()

    print(f"Dodano do manual entry: {inserted}")
    print(f"Zaktualizowano manual entry: {updated}")
    print("KONIEC sync_to_manual_entry")


def build_to_manual_entry():
    print("START build_to_manual_entry")

    with SessionLocal() as session:

        tickets = session.query(ERPWeightTicket).all()
        positions = session.query(ERPWeightTicketPosition).all()

        positions_by_ticket_id = defaultdict(list)
        for pos in positions:
            positions_by_ticket_id[pos.erp_weight_ticket_id].append(pos)

        inserted = 0

        for ticket in tickets:
            ticket_positions = positions_by_ticket_id.get(ticket.id, [])
            if not ticket_positions:
                continue

            ticket_positions = sorted(
                ticket_positions,
                key=lambda p: (p.pos_number is None, p.pos_number)
            )

            first_pos = ticket_positions[0]
            first_ref = first_pos.supplier_refno

            # warunek 1: pierwsza pozycja ma "/"
            if not first_ref or "/" not in str(first_ref):
                continue

            # warunek 2: jakakolwiek kolejna pozycja nie ma "/"
            invalid_other_positions = []
            for pos in ticket_positions[1:]:
                ref = pos.supplier_refno
                if ref is None or "/" not in str(ref):
                    invalid_other_positions.append(pos)

            if not invalid_other_positions:
                continue

            details = ", ".join(
                f"pos={p.pos_number}, supplier_refno={p.supplier_refno}"
                for p in invalid_other_positions
            )

            session.add(
                ToManualEntry(
                    erp_weight_ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    timestamp_in=ticket.timestamp_in,
                    truck_regnumber=ticket.truck_regnumber,
                    first_pos_supplier_refno=first_ref,
                    position_count=ticket.position_count,
                    reason="MISSING_SUPPLIER_REFNO_IN_OTHER_POSITION",
                    details=details,
                )
            )
            inserted += 1

        session.commit()

    print(f"Zapisano do manual entry: {inserted}")
    print("KONIEC build_to_manual_entry")

