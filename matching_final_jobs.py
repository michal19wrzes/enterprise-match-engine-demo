"""Job functions split from the original monolithic jobs.py.

This module is intentionally domain-neutral for the portfolio demo.
"""

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

def build_final_position_matches():
    print("START build_final_position_matches")

    now = datetime.utcnow()

    with SessionLocal() as session:
        best_matches = session.query(TransportPositionBestMatch).filter(
            TransportPositionBestMatch.entry_status == "OPEN"
        ).all()

        erp_positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.entry_status == "OPEN",
            ERPWeightTicketPosition.type == 1,
        ).all()

        external_translated = session.query(ExternalDocumentItemTranslated).all()
        tickets = session.query(ERPWeightTicket).all()

        existing_rows = session.query(FinalPositionMatch).all()
        manual_rows = session.query(ToManualEntry).all()

        erp_pos_by_id = {p.id: p for p in erp_positions}
        ticket_by_id = {t.id: t for t in tickets}

        external_translated_by_doc_and_code = {}
        for row in external_translated:
            key = (
                row.external_document_id,
                str(row.product_code).strip() if row.product_code else None,
            )
            if key[1]:
                external_translated_by_doc_and_code[key] = row

        existing_by_key = {
            (row.erp_weight_ticket_position_id, row.external_document_id): row
            for row in existing_rows
        }

        manual_by_ticket_reason = {
            (row.ticket_number, row.reason): row
            for row in manual_rows
            if row.ticket_number and row.reason
        }

        seen_keys = set()

        inserted = 0
        updated = 0
        resolved = 0

        manual_added = 0
        manual_updated = 0
        marked_manual = 0

        for bm in best_matches:
            erp_pos = erp_pos_by_id.get(bm.erp_weight_ticket_position_id)
            if not erp_pos:
                continue

            erp_code = str(erp_pos.product_code).strip() if erp_pos.product_code else None
            if not erp_code:
                continue

            key_lp = (bm.external_document_id, erp_code)
            external_row = external_translated_by_doc_and_code.get(key_lp)

            if not external_row:
                ticket = ticket_by_id.get(erp_pos.erp_weight_ticket_id)

                if ticket:
                    reason = "MISSING_FINAL_PRODUCT_MATCH"
                    details_text = (
                        f"ticket_number={ticket.ticket_number}, "
                        f"erp_pos_number={erp_pos.pos_number}, "
                        f"supplier_refno={erp_pos.supplier_refno}, "
                        f"erp_product_code={erp_code}, "
                        f"external_document_id={bm.external_document_id}"
                    )

                    existing_manual = manual_by_ticket_reason.get((ticket.ticket_number, reason))
                    if existing_manual:
                        existing_manual.timestamp_in = ticket.timestamp_in
                        existing_manual.truck_regnumber = ticket.truck_regnumber
                        existing_manual.first_pos_supplier_refno = ticket.first_pos_supplier_refno
                        existing_manual.position_count = ticket.position_count
                        existing_manual.details = details_text
                        manual_updated += 1
                    else:
                        session.add(
                            ToManualEntry(
                                erp_weight_ticket_id=ticket.id,
                                ticket_number=ticket.ticket_number,
                                timestamp_in=ticket.timestamp_in,
                                truck_regnumber=ticket.truck_regnumber,
                                first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                                position_count=ticket.position_count,
                                reason=reason,
                                details=details_text,
                            )
                        )
                        manual_added += 1

                    if ticket.status != "MANUAL":
                        ticket.status = "MANUAL"
                        marked_manual += 1

                continue

            ticket = ticket_by_id.get(erp_pos.erp_weight_ticket_id)
            key_final = (erp_pos.id, external_row.external_document_id)
            seen_keys.add(key_final)

            existing_row = existing_by_key.get(key_final)

            if not existing_row:
                session.add(
                    FinalPositionMatch(
                        erp_weight_ticket_id=erp_pos.erp_weight_ticket_id,
                        erp_weight_ticket_position_id=erp_pos.id,
                        external_document_id=external_row.external_document_id,
                        external_document_item_translated_id=external_row.id,
                        erp_ticket_number=ticket.ticket_number if ticket else bm.erp_ticket_number,
                        erp_pos_number=erp_pos.pos_number,
                        erp_supplier_refno=erp_pos.supplier_refno,
                        erp_product_code=erp_code,
                        external_uuid=external_row.external_uuid,
                        external_product_code=external_row.product_code,
                        external_volume_sum=external_row.volume_sum,
                        match_status="MATCHED",
                        entry_status="OPEN",
                        first_detected_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                    )
                )
                inserted += 1
            else:
                existing_row.erp_weight_ticket_id = erp_pos.erp_weight_ticket_id
                existing_row.external_document_item_translated_id = external_row.id
                existing_row.erp_ticket_number = ticket.ticket_number if ticket else bm.erp_ticket_number
                existing_row.erp_pos_number = erp_pos.pos_number
                existing_row.erp_supplier_refno = erp_pos.supplier_refno
                existing_row.erp_product_code = erp_code
                existing_row.external_uuid = external_row.external_uuid
                existing_row.external_product_code = external_row.product_code
                existing_row.external_volume_sum = external_row.volume_sum
                existing_row.match_status = "MATCHED"
                existing_row.entry_status = "OPEN"
                existing_row.last_seen_at = now
                existing_row.resolved_at = None
                updated += 1

        for key, row in existing_by_key.items():
            if key not in seen_keys and row.entry_status == "OPEN":
                row.entry_status = "RESOLVED"
                row.resolved_at = now
                row.last_seen_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano final position matches nowe: {inserted}")
    print(f"Zaktualizowano final position matches: {updated}")
    print(f"Zamknięto final position matches: {resolved}")
    print(f"Dodano manual: {manual_added}")
    print(f"Zaktualizowano manual: {manual_updated}")
    print(f"Oznaczono jako MANUAL: {marked_manual}")
    print("KONIEC build_final_position_matches")

