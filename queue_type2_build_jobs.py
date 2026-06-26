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

def build_output_queue_type2():
    print("START build_output_queue_type2")

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

        matches = session.query(InternalSalesMatch).filter(
            InternalSalesMatch.entry_status == "OPEN",
        ).all()

        existing_queues = session.query(OUTQueue).all()
        existing_items = session.query(OUTQueueItem).all()
        manual_rows = session.query(ToManualEntry).all()

        position_by_id = {p.id: p for p in positions}

        matches_by_ticket = defaultdict(list)
        for m in matches:
            matches_by_ticket[m.erp_weight_ticket_id].append(m)

        existing_queue_by_key = {
            (q.erp_weight_ticket_id, q.external_document_id, q.source_type): q
            for q in existing_queues
        }

        existing_items_by_queue_id = defaultdict(dict)
        for item in existing_items:
            item_key = (
                item.erp_weight_ticket_position_id,
                item.final_position_match_id,
                item.source_type,
            )
            existing_items_by_queue_id[item.output_queue_id][item_key] = item

        manual_by_ticket_reason = {
            (row.ticket_number, row.reason): row
            for row in manual_rows
            if row.ticket_number and row.reason
        }

        seen_queue_keys = set()

        queue_inserted = 0
        queue_updated = 0
        queue_resolved = 0

        item_inserted = 0
        item_updated = 0
        item_resolved = 0

        manual_added = 0
        manual_updated = 0
        marked_manual = 0

        for ticket in tickets:
            queue_source_type = ticket.type
            ticket_matches = matches_by_ticket.get(ticket.id, [])
            if not ticket_matches:
                continue

            unique_matches_by_position = {}
            for m in ticket_matches:
                if m.erp_weight_ticket_position_id not in unique_matches_by_position:
                    unique_matches_by_position[m.erp_weight_ticket_position_id] = m

            unique_matches = list(unique_matches_by_position.values())

            reason = "TYPE2_MORE_THAN_ONE_POSITION"
            details_text = None

            if len(unique_matches) > 1:
                details_text = " | ".join(
                    f"erp_weight_ticket_position_id={m.erp_weight_ticket_position_id}, "
                    f"erp_pos_number={m.erp_pos_number}, "
                    f"supplier_refno={m.erp_supplier_refno}, "
                    f"product_code={m.erp_product_code}"
                    for m in unique_matches
                )

                existing_manual = manual_by_ticket_reason.get((ticket.ticket_number, reason))
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

                queue_key = (ticket.id, None, queue_source_type)
                existing_queue = existing_queue_by_key.get(queue_key)
                if existing_queue and existing_queue.entry_status == "OPEN":
                    existing_queue.entry_status = "RESOLVED"
                    existing_queue.resolved_at = now
                    existing_queue.last_seen_at = now
                    queue_resolved += 1

                    for existing_item in existing_items_by_queue_id.get(existing_queue.id, {}).values():
                        if existing_item.source_type == queue_source_type and existing_item.entry_status == "OPEN":
                            existing_item.entry_status = "RESOLVED"
                            existing_item.resolved_at = now
                            existing_item.last_seen_at = now
                            item_resolved += 1

                continue

            match_row = unique_matches[0]
            pos = position_by_id.get(match_row.erp_weight_ticket_position_id)
            if not pos:
                continue

            mp_amount = floor_2(pos.quantity_rm or 0)
            total_mp = mp_amount

            is_fsc = 1 if match_row.tsc_fsc_cw_id is not None else 0
            is_pefc = 1 if match_row.tsc_pefc_id is not None else 0

            queue_key = (ticket.id, None, queue_source_type)
            seen_queue_keys.add(queue_key)

            queue_row = existing_queue_by_key.get(queue_key)

            if not queue_row:
                queue_row = OUTQueue(
                    erp_weight_ticket_id=ticket.id,
                    external_document_id=None,
                    ticket_number=ticket.ticket_number,
                    supplier_refno=ticket.first_pos_supplier_refno,
                    external_uuid=None,
                    truck_regnumber=ticket.truck_regnumber,
                    timestamp_in=ticket.timestamp_in,
                    vehicletype=ticket.vehicletype,
                    source_type=queue_source_type,
                    clerk="99998",
                    cont1=0,
                    cont2=0,
                    total_mp=total_mp,
                    position_count=1,
                    is_fsc=is_fsc,
                    is_pefc=is_pefc,
                    status="NEW",
                    entry_status="OPEN",
                    last_seen_at=now,
                    resolved_at=None,
                )
                session.add(queue_row)
                session.flush()

                existing_queue_by_key[queue_key] = queue_row
                existing_items_by_queue_id.setdefault(queue_row.id, {})
                queue_inserted += 1
            else:
                queue_row.ticket_number = ticket.ticket_number
                queue_row.supplier_refno = ticket.first_pos_supplier_refno
                queue_row.external_document_id = None
                queue_row.external_uuid = None
                queue_row.truck_regnumber = ticket.truck_regnumber
                queue_row.timestamp_in = ticket.timestamp_in
                queue_row.vehicletype = ticket.vehicletype
                queue_row.source_type = queue_source_type
                queue_row.clerk = "99998"
                queue_row.cont1 = 0
                queue_row.cont2 = 0
                queue_row.total_mp = total_mp
                queue_row.position_count = 1
                queue_row.is_fsc = is_fsc
                queue_row.is_pefc = is_pefc
                queue_row.entry_status = "OPEN"
                queue_row.last_seen_at = now
                queue_row.resolved_at = None
                queue_updated += 1

            fallback_reason = "Nie znaleziono dopasowania Nr. Dok. Dostawy REF do numerów w kwicie zewnetrznym - fallback"

            existing_manual = manual_by_ticket_reason.get((ticket.ticket_number, fallback_reason))
            if existing_manual and existing_manual.entry_status == "OPEN":
                existing_manual.entry_status = "RESOLVED"
                existing_manual.resolved_at = now
                existing_manual.last_seen_at = now

            existing_item_map = existing_items_by_queue_id.get(queue_row.id, {})
            seen_item_keys = set()

            item_key = (
                match_row.erp_weight_ticket_position_id,
                None,
                queue_source_type,
            )
            seen_item_keys.add(item_key)

            existing_item = existing_item_map.get(item_key)

            if not existing_item:
                new_item = OUTQueueItem(
                    output_queue_id=queue_row.id,
                    erp_weight_ticket_position_id=match_row.erp_weight_ticket_position_id,
                    final_position_match_id=None,
                    ticket_number=ticket.ticket_number,
                    timestamp_in=ticket.timestamp_in,
                    source_order_number=match_row.erp_source_order_number,
                    supplier_refno=match_row.erp_supplier_refno,
                    product_code=pos.product_code,
                    source_type=queue_source_type,
                    mp_amount=mp_amount,
                    status="NEW",
                    entry_status="OPEN",
                    last_seen_at=now,
                    resolved_at=None,
                )
                session.add(new_item)
                item_inserted += 1
            else:
                existing_item.ticket_number = ticket.ticket_number
                existing_item.timestamp_in = ticket.timestamp_in
                existing_item.source_order_number = match_row.erp_source_order_number
                existing_item.supplier_refno = match_row.erp_supplier_refno
                existing_item.product_code = pos.product_code
                existing_item.source_type = queue_source_type
                existing_item.mp_amount = mp_amount
                existing_item.entry_status = "OPEN"
                existing_item.last_seen_at = now
                existing_item.resolved_at = None
                item_updated += 1

            for existing_item_key, existing_item in existing_item_map.items():
                if existing_item.source_type != queue_source_type:
                    continue

                if existing_item_key not in seen_item_keys and existing_item.entry_status == "OPEN":
                    existing_item.entry_status = "RESOLVED"
                    existing_item.resolved_at = now
                    existing_item.last_seen_at = now
                    item_resolved += 1

        for queue_key, queue_row in existing_queue_by_key.items():
            if queue_row.source_type not in (2, 3):
                continue

            if queue_key not in seen_queue_keys and queue_row.entry_status == "OPEN":
                queue_row.entry_status = "RESOLVED"
                queue_row.resolved_at = now
                queue_row.last_seen_at = now
                queue_resolved += 1

                for existing_item in existing_items_by_queue_id.get(queue_row.id, {}).values():
                    if existing_item.source_type not in (2, 3):
                        continue

                    if existing_item.entry_status == "OPEN":
                        existing_item.entry_status = "RESOLVED"
                        existing_item.resolved_at = now
                        existing_item.last_seen_at = now
                        item_resolved += 1

        session.commit()

    print(f"Zapisano output_queue type=2 nowe: {queue_inserted}")
    print(f"Zaktualizowano output_queue type=2: {queue_updated}")
    print(f"Zamknięto output_queue type=2: {queue_resolved}")

    print(f"Zapisano output_queue_items type=2 nowe: {item_inserted}")
    print(f"Zaktualizowano output_queue_items type=2: {item_updated}")
    print(f"Zamknięto output_queue_items type=2: {item_resolved}")

    print(f"Dodano manual: {manual_added}")
    print(f"Zaktualizowano manual: {manual_updated}")
    print(f"Oznaczono ticket jako MANUAL: {marked_manual}")

    print("KONIEC build_output_queue_type2")

