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

def build_internal_sales_matches():
    print("START build_internal_sales_matches")

    now = datetime.utcnow()

    with SessionLocal() as session:
        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type.in_([2, 3]),
            ERPWeightTicket.status == "ACTIVE",
        ).all()

        positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.type.in_([2, 3]),
            ERPWeightTicketPosition.entry_status == "OPEN",
        ).all()

        cache_rows = session.query(InternalProductSalesCache).filter(
            InternalProductSalesCache.entry_status == "OPEN",
        ).all()

        existing_matches = session.query(InternalSalesMatch).all()
        manual_rows = session.query(ToManualEntry).all()

        ticket_by_id = {t.id: t for t in tickets}

        positions_by_ticket_id = defaultdict(list)
        for pos in positions:
            positions_by_ticket_id[pos.erp_weight_ticket_id].append(pos)

        cache_by_key = defaultdict(list)
        for row in cache_rows:
            key = (
                str(row.cdu_id).strip() if row.cdu_id else None,
                str(row.ticket_number).strip() if row.ticket_number else None,
            )
            if key[0] and key[1]:
                cache_by_key[key].append(row)

        existing_by_key = {
            (row.erp_weight_ticket_position_id, row.internal_product_sales_cache_id): row
            for row in existing_matches
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

        for ticket in tickets:
            ticket_positions = positions_by_ticket_id.get(ticket.id, [])
            if not ticket_positions:
                continue

            ticket_has_missing_match = False
            missing_details = []

            for pos in ticket_positions:
                parsed_cdu_id, parsed_ticket_number = parse_internal_supplier_refno(pos.supplier_refno)

                if not parsed_cdu_id or not parsed_ticket_number:
                    ticket_has_missing_match = True
                    missing_details.append(
                        f"erp_pos_number={pos.pos_number}, supplier_refno={pos.supplier_refno}, error=Nie rozpoznano numeru REF na spółce źródłowej"
                    )
                    continue

                matched_cache_rows = cache_by_key.get((parsed_cdu_id, parsed_ticket_number), [])

                if not matched_cache_rows:
                    ticket_has_missing_match = True
                    missing_details.append(
                        f"erp_pos_number={pos.pos_number}, supplier_refno={pos.supplier_refno}, parsed_cdu_id={parsed_cdu_id}, parsed_ticket_number={parsed_ticket_number}, error=PRODUCTSALES_NOT_FOUND"
                    )
                    continue

                # jeśli będzie więcej niż jeden rekord, na razie bierzemy pierwszy;
                # później można rozbudować logikę
                cache_row = matched_cache_rows[0]

                key = (pos.id, cache_row.id)
                seen_keys.add(key)

                existing_row = existing_by_key.get(key)

                if not existing_row:
                    session.add(
                        InternalSalesMatch(
                            erp_weight_ticket_id=ticket.id,
                            erp_weight_ticket_position_id=pos.id,
                            internal_product_sales_cache_id=cache_row.id,
                            source_type=ticket.type,

                            erp_ticket_number=ticket.ticket_number,
                            erp_timestamp_in=ticket.timestamp_in,
                            erp_truck_regnumber=ticket.truck_regnumber,
                            erp_position_count=ticket.position_count,
                            erp_first_pos_supplier_refno=ticket.first_pos_supplier_refno,
                            erp_first_pos_mcode=ticket.first_pos_mcode,

                            erp_pos_number=pos.pos_number,
                            erp_supplier_refno=pos.supplier_refno,
                            erp_supplier_code=pos.supplier_code,
                            erp_product_id=pos.product_id,
                            erp_product_code=pos.product_code,
                            erp_product_text=pos.product_text,
                            erp_product_type_id=pos.product_type_id,
                            erp_quantity_rm=pos.quantity_rm,
                            erp_source_order_number=pos.source_order_number,

                            parsed_cdu_id=parsed_cdu_id,
                            parsed_ticket_number=parsed_ticket_number,

                            cache_source_db=cache_row.source_db,
                            cache_cdu_id=cache_row.cdu_id,
                            cache_ticket_number=cache_row.ticket_number,
                            productsales_id=cache_row.productsales_id,
                            sale_date=cache_row.sale_date,

                            truck_regnumber=cache_row.truck_regnumber,
                            trailer_regnumber=cache_row.trailer_regnumber,

                            cache_product_id=cache_row.product_id,
                            cache_product_code=cache_row.product_code,
                            cache_quantity_rm=cache_row.quantity_rm,

                            tsc_pefc_id=cache_row.tsc_pefc_id,
                            tsc_fsc_cw_id=cache_row.tsc_fsc_cw_id,

                            match_status="MATCHED",
                            entry_status="OPEN",
                            first_detected_at=now,
                            last_seen_at=now,
                            resolved_at=None,
                        )
                    )
                    inserted += 1
                else:
                    existing_row.source_type = ticket.type

                    existing_row.erp_ticket_number = ticket.ticket_number
                    existing_row.erp_timestamp_in = ticket.timestamp_in
                    existing_row.erp_truck_regnumber = ticket.truck_regnumber
                    existing_row.erp_position_count = ticket.position_count
                    existing_row.erp_first_pos_supplier_refno = ticket.first_pos_supplier_refno
                    existing_row.erp_first_pos_mcode = ticket.first_pos_mcode

                    existing_row.erp_pos_number = pos.pos_number
                    existing_row.erp_supplier_refno = pos.supplier_refno
                    existing_row.erp_supplier_code = pos.supplier_code
                    existing_row.erp_product_id = pos.product_id
                    existing_row.erp_product_code = pos.product_code
                    existing_row.erp_product_text = pos.product_text
                    existing_row.erp_product_type_id = pos.product_type_id
                    existing_row.erp_quantity_rm = pos.quantity_rm
                    existing_row.erp_source_order_number = pos.source_order_number

                    existing_row.parsed_cdu_id = parsed_cdu_id
                    existing_row.parsed_ticket_number = parsed_ticket_number

                    existing_row.cache_source_db = cache_row.source_db
                    existing_row.cache_cdu_id = cache_row.cdu_id
                    existing_row.cache_ticket_number = cache_row.ticket_number
                    existing_row.productsales_id = cache_row.productsales_id
                    existing_row.sale_date = cache_row.sale_date

                    existing_row.truck_regnumber = cache_row.truck_regnumber
                    existing_row.trailer_regnumber = cache_row.trailer_regnumber

                    existing_row.cache_product_id = cache_row.product_id
                    existing_row.cache_product_code = cache_row.product_code
                    existing_row.cache_quantity_rm = cache_row.quantity_rm

                    existing_row.tsc_pefc_id = cache_row.tsc_pefc_id
                    existing_row.tsc_fsc_cw_id = cache_row.tsc_fsc_cw_id

                    existing_row.match_status = "MATCHED"
                    existing_row.entry_status = "OPEN"
                    existing_row.last_seen_at = now
                    existing_row.resolved_at = None
                    updated += 1

            reason = "Nie rozpoznano numeru REF na spółce źródłowej"
            existing_manual = manual_by_ticket_reason.get((ticket.ticket_number, reason))

            if ticket_has_missing_match:
                details_text = " | ".join(missing_details)

                if existing_manual:
                    existing_manual.erp_weight_ticket_id = ticket.id
                    existing_manual.timestamp_in = ticket.timestamp_in
                    existing_manual.truck_regnumber = ticket.truck_regnumber
                    existing_manual.first_pos_supplier_refno = ticket.first_pos_supplier_refno
                    existing_manual.position_count = ticket.position_count
                    existing_manual.details = details_text
                    existing_manual.entry_status = "OPEN"
                    existing_manual.last_seen_at = now
                    existing_manual.resolved_at = None
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
                            notification_type="USER",
                            notification_status="NEW",
                            entry_status="OPEN",
                            first_detected_at=now,
                            last_seen_at=now,
                            resolved_at=None,
                        )
                    )
                    manual_added += 1

                if ticket.status != "MANUAL":
                    ticket.status = "MANUAL"
                    marked_manual += 1
            else:
                if existing_manual and existing_manual.entry_status == "OPEN":
                    existing_manual.entry_status = "RESOLVED"
                    existing_manual.resolved_at = now
                    existing_manual.last_seen_at = now

        for key, row in existing_by_key.items():
            if key not in seen_keys and row.entry_status == "OPEN":
                row.entry_status = "RESOLVED"
                row.resolved_at = now
                row.last_seen_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano internal sales matches nowe: {inserted}")
    print(f"Zaktualizowano internal sales matches: {updated}")
    print(f"Zamknięto internal sales matches: {resolved}")
    print(f"Dodano manual: {manual_added}")
    print(f"Zaktualizowano manual: {manual_updated}")
    print(f"Oznaczono ticket jako MANUAL: {marked_manual}")
    print("KONIEC build_internal_sales_matches")

