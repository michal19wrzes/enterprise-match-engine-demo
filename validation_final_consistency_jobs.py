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

def validate_position_count_erp_vs_external_translated():
    print("START validate_position_count_erp_vs_external_translated")

    reason_text = "ERP_EXT_POSITION_COUNT_MISMATCH"

    BLOCKING_REASONS = {
        "Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02",
        "Nie znaleziono dopasowania nagłówka SRC do dokumentu external",
        "Nie znaleziono dopasowania pozycji SRC do dokumentu external",
        "Nie znaleziono dopasowania Nr. Dok. Dostawy REF do numerów w kwicie zewnętrznym",
    }

    with SessionLocal() as session:
        now = datetime.utcnow()

        best_matches = session.query(TransportPositionBestMatch).filter(
            TransportPositionBestMatch.entry_status == "OPEN"
        ).all()

        erp_positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.entry_status == "OPEN",
            ERPWeightTicketPosition.type == 1,
        ).all()

        external_translated = session.query(ExternalDocumentItemTranslated).filter(
            ExternalDocumentItemTranslated.entry_status == "OPEN"
        ).all()

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
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

        ticket_by_number = {t.ticket_number: t for t in tickets}

        positions_by_ticket = defaultdict(list)
        for pos in erp_positions:
            positions_by_ticket[pos.erp_weight_ticket_id].append(pos)

        external_translated_by_doc = defaultdict(list)
        for row in external_translated:
            external_translated_by_doc[row.external_document_id].append(row)

        best_by_ticket_doc = defaultdict(list)
        for bm in best_matches:
            best_by_ticket_doc[(bm.erp_ticket_number, bm.external_document_id)].append(bm)

        inserted = 0
        updated = 0
        marked_manual = 0
        skipped_queue = 0
        skipped_blocked_manual = 0
        active_fingerprints = set()

        for (ticket_number, external_document_id), bm_rows in best_by_ticket_doc.items():
            if not bm_rows:
                continue

            ticket = ticket_by_number.get(ticket_number)
            if not ticket:
                continue

            if ticket.id in queue_ticket_ids:
                skipped_queue += 1
                continue

            if ticket.id in blocked_manual_ticket_ids:
                skipped_blocked_manual += 1
                continue

            matched_position_ids = {
                bm.erp_weight_ticket_position_id
                for bm in bm_rows
                if bm.erp_weight_ticket_position_id is not None
            }

            matched_positions = [
                p for p in positions_by_ticket.get(ticket.id, [])
                if p.id in matched_position_ids
            ]

            by_supplier_ref = defaultdict(list)
            for pos in matched_positions:
                if pos.supplier_refno:
                    by_supplier_ref[pos.supplier_refno].append(pos)

            external_count = len(external_translated_by_doc.get(external_document_id, []))
            mismatch_reasons = []

            for supplier_refno, pos_list in by_supplier_ref.items():
                erp_count = len(pos_list)

                if erp_count != external_count:
                    mismatch_reasons.append(
                        f"supplier_refno={supplier_refno}, "
                        f"erp_count={erp_count}, "
                        f"external_translated_count={external_count}"
                    )

            if not mismatch_reasons:
                continue

            details_text = " | ".join(mismatch_reasons)

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
    print("KONIEC validate_position_count_erp_vs_external_translated")


def validate_erp_duplicate_product_per_supplier_ref():
    print("START validate_erp_duplicate_product_per_supplier_ref")

    with SessionLocal() as session:
        tickets = session.query(ERPWeightTicket).all()
        positions = session.query(ERPWeightTicketPosition).all()

        positions_by_ticket = defaultdict(list)
        for pos in positions:
            positions_by_ticket[pos.erp_weight_ticket_id].append(pos)

        inserted = 0
        updated = 0
        removed_from_auto = 0
        active_fingerprints = set()
        now = datetime.utcnow()

        for ticket in tickets:
            ticket_positions = positions_by_ticket.get(ticket.id, [])
            if not ticket_positions:
                continue

            by_supplier_ref = defaultdict(list)
            for pos in ticket_positions:
                if not pos.supplier_refno:
                    continue
                by_supplier_ref[pos.supplier_refno].append(pos)

            reasons = []

            for supplier_refno, pos_list in by_supplier_ref.items():
                position_count = len(pos_list)
                distinct_codes = {
                    str(p.product_code).strip()
                    for p in pos_list
                    if p.product_code
                }
                distinct_code_count = len(distinct_codes)

                if position_count != distinct_code_count:
                    details = (
                        f"supplier_refno={supplier_refno}, "
                        f"position_count={position_count}, "
                        f"distinct_product_code_count={distinct_code_count}, "
                        f"codes={sorted(distinct_codes)}"
                    )
                    reasons.append(details)

            if not reasons:
                continue

            details_text = " | ".join(reasons)
            active_fingerprints.add(build_manual_entry_fingerprint(ticket.ticket_number, "AMBIGUOUS_ERP_POSITIONS_SAME_SUPPLIER_REFNO", details_text))
            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=ticket.id,
                ticket_number=ticket.ticket_number,
                timestamp_in=ticket.timestamp_in,
                truck_regnumber=ticket.truck_regnumber,
                first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                position_count=ticket.position_count,
                reason="AMBIGUOUS_ERP_POSITIONS_SAME_SUPPLIER_REFNO",
                details=details_text,
                now=now,
            )
            if created:
                inserted += 1
            else:
                updated += 1

            if ticket.status != "MANUAL":
                ticket.status = "MANUAL"
                removed_from_auto += 1

        resolve_missing_manual_entries(session, active_fingerprints, {"AMBIGUOUS_ERP_POSITIONS_SAME_SUPPLIER_REFNO"}, now=now)
        session.commit()

    print(f"Dodano do manual entry: {inserted}")
    print(f"Zaktualizowano manual entry: {updated}")
    print(f"Usunięto z automatu: {removed_from_auto}")
    print("KONIEC validate_erp_duplicate_product_per_supplier_ref")

