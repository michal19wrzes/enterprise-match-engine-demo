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

def validate_header_without_position_match():
    print("START validate_header_without_position_match")

    reason_text = "Nie znaleziono dopasowania pozycji SRC do dokumentu external"

    with SessionLocal() as session:
        now = datetime.utcnow()

        header_ticket_ids = {
            row[0]
            for row in session.query(TransportHeaderMatch.erp_weight_ticket_id)
            .filter(
                TransportHeaderMatch.entry_status == "OPEN",
                TransportHeaderMatch.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        position_match_ticket_ids = {
            row[0]
            for row in session.query(ERPWeightTicketPosition.erp_weight_ticket_id)
            .join(
                TransportPositionMatch,
                TransportPositionMatch.erp_weight_ticket_position_id == ERPWeightTicketPosition.id,
            )
            .filter(
                ERPWeightTicketPosition.entry_status == "OPEN",
                ERPWeightTicketPosition.type == 1,
                TransportPositionMatch.entry_status == "OPEN",
            )
            .distinct()
            .all()
        }

        open_output_ticket_ids = {
            row[0]
            for row in session.query(OUTQueue.erp_weight_ticket_id)
            .filter(
                OUTQueue.entry_status == "OPEN",
                OUTQueue.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
            ERPWeightTicket.id.in_(header_ticket_ids),
            ~ERPWeightTicket.id.in_(position_match_ticket_ids),
            ~ERPWeightTicket.id.in_(open_output_ticket_ids),
        ).all()

        inserted = 0
        updated = 0
        marked_manual = 0
        active_fingerprints = set()

        for ticket in tickets:
            details_text = (
                f"ticket_number={ticket.ticket_number}, "
                f"truck_regnumber={ticket.truck_regnumber}, "
                f"first_pos_mcode={ticket.first_pos_mcode}, "
                f"first_pos_supplier_refno={ticket.first_pos_supplier_refno}, "
                f"position_count={ticket.position_count}, "
                f"reason_source=HEADER_EXISTS_BUT_NO_POSITION_MATCH"
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    ticket.ticket_number,
                    reason_text,
                    details_text,
                )
            )

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id,
                ticket_number=ticket.ticket_number,
                timestamp_in=ticket.timestamp_in,
                truck_regnumber=ticket.truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                position_count=ticket.position_count,
                reason=reason_text,
                details=details_text,
                now=now,
            )

            session.flush()

            if created:
                inserted += 1
            else:
                updated += 1

            if ticket.status != "MANUAL":
                ticket.status = "MANUAL"
                ticket.updated_at = now
                marked_manual += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {reason_text},
            now=now,
        )

        session.commit()

    print(f"Dodano manual: {inserted}")
    print(f"Zaktualizowano manual: {updated}")
    print(f"Oznaczono MANUAL: {marked_manual}")
    print("KONIEC validate_header_without_position_match")


def validate_missing_header_match():
    print("START validate_missing_header_match")

    reason_text = "Nie znaleziono dopasowania nagłówka SRC do dokumentu external"

    with SessionLocal() as session:
        now = datetime.utcnow()

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
        ).all()

        header_ticket_ids = {
            row[0]
            for row in session.query(TransportHeaderMatch.erp_weight_ticket_id)
            .filter(
                TransportHeaderMatch.entry_status == "OPEN",
                TransportHeaderMatch.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        open_output_ticket_ids = {
            row[0]
            for row in session.query(OUTQueue.erp_weight_ticket_id)
            .filter(
                OUTQueue.entry_status == "OPEN",
                OUTQueue.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        inserted = 0
        updated = 0
        marked_manual = 0
        skipped_pz = 0
        active_fingerprints = set()

        for ticket in tickets:
            if ticket.id in open_output_ticket_ids:
                skipped_pz += 1
                continue

            if ticket.id in header_ticket_ids:
                continue

            details_text = (
                f"ticket_number={ticket.ticket_number}, "
                f"truck_regnumber={ticket.truck_regnumber}, "
                f"first_pos_mcode={ticket.first_pos_mcode}, "
                f"first_pos_supplier_refno={ticket.first_pos_supplier_refno}, "
                f"position_count={ticket.position_count}"
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    ticket.ticket_number,
                    reason_text,
                    details_text,
                )
            )

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id,
                ticket_number=ticket.ticket_number,
                timestamp_in=ticket.timestamp_in,
                truck_regnumber=ticket.truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                position_count=ticket.position_count,
                reason=reason_text,
                details=details_text,
                now=now,
            )

            if created:
                inserted += 1
            else:
                updated += 1

            if ticket.status != "MANUAL":
                ticket.status = "MANUAL"
                ticket.updated_at = now
                marked_manual += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {reason_text},
            now=now,
        )

        session.commit()

    print(f"Dodano manual: {inserted}")
    print(f"Zaktualizowano manual: {updated}")
    print(f"Oznaczono MANUAL: {marked_manual}")
    print(f"Pominięto - ma OUT: {skipped_pz}")
    print("KONIEC validate_missing_header_match")


def validate_missing_supplier_refno_position_matches():
    print("START validate_missing_supplier_refno_position_matches")

    reason_text = "Nie znaleziono dopasowania Nr. Dok. Dostawy REF do numerów w kwicie zewnętrznym"

    BLOCKING_REASONS = {
        "Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02",
        "Nie znaleziono dopasowania nagłówka SRC do dokumentu external",
        "Nie znaleziono dopasowania pozycji SRC do dokumentu external",
    }

    with SessionLocal() as session:
        now = datetime.utcnow()

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
        ).all()

        positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.type == 1,
            ERPWeightTicketPosition.entry_status == "OPEN",
        ).all()

        position_matches = session.query(TransportPositionMatch).filter(
            TransportPositionMatch.entry_status == "OPEN"
        ).all()

        queue_ticket_ids = {
            row[0]
            for row in session.query(OUTQueue.erp_weight_ticket_id)
            .filter(
                OUTQueue.entry_status == "OPEN",
                OUTQueue.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        blocked_manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.erp_weight_ticket_id.isnot(None),
                ToManualEntry.reason.in_(BLOCKING_REASONS),
            )
            .distinct()
            .all()
        }

        positions_by_ticket = defaultdict(list)
        position_ticket_by_position_id = {}

        for pos in positions:
            positions_by_ticket[pos.erp_weight_ticket_id].append(pos)
            position_ticket_by_position_id[pos.id] = pos.erp_weight_ticket_id

        matched_position_ids = {
            pm.erp_weight_ticket_position_id
            for pm in position_matches
            if pm.erp_weight_ticket_position_id is not None
        }

        position_match_ticket_ids = {
            position_ticket_by_position_id.get(pm.erp_weight_ticket_position_id)
            for pm in position_matches
            if pm.erp_weight_ticket_position_id is not None
        }
        position_match_ticket_ids.discard(None)

        inserted = 0
        updated = 0
        marked_manual = 0
        skipped_queue = 0
        skipped_blocked_manual = 0
        skipped_no_position_match = 0
        active_fingerprints = set()

        for ticket in tickets:
            if ticket.id in queue_ticket_ids:
                skipped_queue += 1
                continue

            if ticket.id in blocked_manual_ticket_ids:
                skipped_blocked_manual += 1
                continue

            ticket_positions = positions_by_ticket.get(ticket.id, [])
            if not ticket_positions:
                continue

            # Jeśli ticket nie ma żadnego position match,
            # to obsługuje go validate_header_without_position_match().
            # Tutaj tylko częściowy problem: coś się dopasowało, ale nie wszystkie pozycje.
            if ticket.id not in position_match_ticket_ids:
                skipped_no_position_match += 1
                continue

            unmatched_positions = [
                pos for pos in ticket_positions
                if pos.id not in matched_position_ids
            ]

            if not unmatched_positions:
                continue

            details_text = " | ".join(
                f"erp_pos_number={pos.pos_number}, "
                f"supplier_refno={pos.supplier_refno}, "
                f"product_code={pos.product_code}"
                for pos in unmatched_positions
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    ticket.ticket_number,
                    reason_text,
                    details_text,
                )
            )

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id,
                ticket_number=ticket.ticket_number,
                timestamp_in=ticket.timestamp_in,
                truck_regnumber=ticket.truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                position_count=ticket.position_count,
                reason=reason_text,
                details=details_text,
                now=now,
            )

            session.flush()

            if created:
                inserted += 1
            else:
                updated += 1

            if ticket.status != "MANUAL":
                ticket.status = "MANUAL"
                ticket.updated_at = now
                marked_manual += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {reason_text},
            now=now,
        )

        session.commit()

    print(f"Dodano do manual entry: {inserted}")
    print(f"Zaktualizowano manual entry: {updated}")
    print(f"Oznaczono ticket jako MANUAL: {marked_manual}")
    print(f"Pominięto - istnieje OUT queue: {skipped_queue}")
    print(f"Pominięto - istnieje ważniejszy manual: {skipped_blocked_manual}")
    print(f"Pominięto - brak jakiegokolwiek position match: {skipped_no_position_match}")
    print("KONIEC validate_missing_supplier_refno_position_matches")

