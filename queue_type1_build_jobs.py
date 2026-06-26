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

def build_output_queue():
    print("START build_output_queue")

    now = datetime.utcnow()
    OUT_SOURCE_EXT_API = 1

    BLOCKING_MANUAL_REASONS = {
        "Brak uzupełnionego pola Nr. Dok Dostawy REF w pozycji SRC02",
        "Nie rozpoznano numeru REF na spółce źródłowej",
        "ERP_EXT_POSITION_COUNT_MISMATCH",
        "Nie znaleziono dopasowania Nr. Dok. Dostawy REF do numerów w kwicie zewnętrznym",
        "Nie znaleziono dopasowania pozycji SRC do dokumentu external",
        "Nie znaleziono dopasowania nagłówka SRC do dokumentu external",
        "Brak kolejki OUT po zakończonym matchingu",
        "MISSING_PRODUCT_FACTOR",
    }

    with SessionLocal() as session:
        final_matches = session.query(FinalPositionMatch).filter(
            FinalPositionMatch.entry_status == "OPEN"
        ).all()

        tickets = session.query(ERPWeightTicket).all()

        positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.entry_status == "OPEN"
        ).all()

        documents = session.query(ExternalDocument).all()
        products = session.query(Product).all()

        existing_queues = session.query(OUTQueue).filter(
            OUTQueue.entry_status == "OPEN"
        ).all()

        existing_items = session.query(OUTQueueItem).filter(
            OUTQueueItem.entry_status == "OPEN"
        ).all()

        blocking_manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.reason.in_(BLOCKING_MANUAL_REASONS),
                ToManualEntry.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        ticket_by_id = {t.id: t for t in tickets}
        position_by_id = {p.id: p for p in positions}
        doc_by_id = {d.id: d for d in documents}

        product_by_code = {
            (str(tp.code).strip(), str(tp.cdu_id).strip() if tp.cdu_id else None): tp
            for tp in products
            if tp.code
        }

        matches_by_ticket = defaultdict(list)
        for fm in final_matches:
            matches_by_ticket[fm.erp_weight_ticket_id].append(fm)

        existing_queue_by_key = {
            (q.erp_weight_ticket_id, q.source_type): q
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

        seen_queue_keys = set()

        queue_inserted = 0
        queue_updated = 0
        queue_resolved = 0

        item_inserted = 0
        item_updated = 0
        item_resolved = 0

        skipped_manual = 0
        skipped_removed = 0
        skipped_incomplete_positions = 0
        skipped_missing_factor = 0

        for erp_weight_ticket_id, fm_rows in matches_by_ticket.items():
            queue_key = (erp_weight_ticket_id, OUT_SOURCE_EXT_API)
            seen_queue_keys.add(queue_key)

            ticket = ticket_by_id.get(erp_weight_ticket_id)
            if not ticket:
                continue

            if ticket.type != 1:
                continue

            if ticket.status == "REMOVED":
                skipped_removed += 1
                continue

            if ticket.id in blocking_manual_ticket_ids:
                skipped_manual += 1
                continue

            ticket_positions = [
                p for p in positions
                if p.erp_weight_ticket_id == ticket.id
            ]

            if not ticket_positions:
                skipped_incomplete_positions += 1
                continue

            matched_position_ids = {
                fm.erp_weight_ticket_position_id
                for fm in fm_rows
            }

            if {p.id for p in ticket_positions} != matched_position_ids:
                skipped_incomplete_positions += 1
                continue

            item_payloads = []
            total_mp = 0.0
            missing_factor = False

            for fm in fm_rows:
                pos = position_by_id.get(fm.erp_weight_ticket_position_id)
                if not pos:
                    continue

                product_code = str(pos.product_code).strip() if pos.product_code else None
                if not product_code:
                    missing_factor = True
                    break

                cdu_id = str(ticket.cdu_id).strip() if ticket.cdu_id else "DEMO_SITE"
                tp = product_by_code.get((product_code, cdu_id))

                if not tp or tp.factor_fm_rm in (None, 0):
                    missing_factor = True
                    break

                mp_amount = round_2((fm.external_volume_sum or 0) / tp.factor_fm_rm)
                total_mp += mp_amount or 0

                item_payloads.append(
                    {
                        "erp_weight_ticket_position_id": pos.id,
                        "erp_pos_number": pos.pos_number,
                        "final_position_match_id": fm.id,
                        "external_document_id": fm.external_document_id,
                        "external_uuid": fm.external_uuid,
                        "source_order_number": pos.source_order_number,
                        "supplier_refno": pos.supplier_refno,
                        "product_code": product_code,
                        "mp_amount": mp_amount,
                        "source_type": OUT_SOURCE_EXT_API,
                    }
                )

            if missing_factor:
                skipped_missing_factor += 1
                continue

            if not item_payloads:
                skipped_incomplete_positions += 1
                continue
            item_payloads = sorted(
                item_payloads,
                key=lambda x: (
                    x["erp_pos_number"] is None,
                    x["erp_pos_number"],
                    x["erp_weight_ticket_position_id"],
                )
            )
            total_mp = round_2(total_mp)

            first_item = item_payloads[0]

            representative_external_document_id = first_item["external_document_id"]
            representative_external_uuid = first_item["external_uuid"]

            representative_doc = doc_by_id.get(representative_external_document_id)
            certificate_text = representative_doc.certificate_text if representative_doc else ""
            certificate_text = certificate_text or ""

            is_fsc = 1 if "FSC:" in certificate_text else 0
            is_pefc = 1 if "PEFC:" in certificate_text else 0

            queue_row = existing_queue_by_key.get(queue_key)

            if not queue_row:
                queue_row = OUTQueue(
                    erp_weight_ticket_id=ticket.id,
                    external_document_id=representative_external_document_id,
                    ticket_number=ticket.ticket_number,
                    status="NEW",
                    supplier_refno=ticket.first_pos_supplier_refno,
                    external_uuid=representative_external_uuid,
                    truck_regnumber=ticket.truck_regnumber,
                    timestamp_in=ticket.timestamp_in,
                    vehicletype=ticket.vehicletype,
                    cont1=0,
                    cont2=0,
                    clerk="99998",
                    total_mp=total_mp,
                    position_count=len(item_payloads),
                    is_fsc=is_fsc,
                    is_pefc=is_pefc,
                    source_type=OUT_SOURCE_EXT_API,
                    entry_status="OPEN",
                    last_seen_at=now,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(queue_row)
                session.flush()

                existing_queue_by_key[queue_key] = queue_row
                existing_items_by_queue_id.setdefault(queue_row.id, {})
                queue_inserted += 1
            else:
                queue_row.external_document_id = representative_external_document_id
                queue_row.ticket_number = ticket.ticket_number
                queue_row.supplier_refno = ticket.first_pos_supplier_refno
                queue_row.external_uuid = representative_external_uuid
                queue_row.truck_regnumber = ticket.truck_regnumber
                queue_row.timestamp_in = ticket.timestamp_in
                queue_row.vehicletype = ticket.vehicletype
                queue_row.cont1 = 0
                queue_row.cont2 = 0
                queue_row.clerk = "99998"
                queue_row.total_mp = total_mp
                queue_row.position_count = len(item_payloads)
                queue_row.is_fsc = is_fsc
                queue_row.is_pefc = is_pefc
                queue_row.source_type = OUT_SOURCE_EXT_API
                queue_row.entry_status = "OPEN"
                queue_row.last_seen_at = now
                queue_row.resolved_at = None
                queue_row.updated_at = now
                queue_updated += 1

            existing_item_map = existing_items_by_queue_id.get(queue_row.id, {})
            seen_item_keys = set()

            for item in item_payloads:
                item_key = (
                    item["erp_weight_ticket_position_id"],
                    item["final_position_match_id"],
                    item["source_type"],
                )
                seen_item_keys.add(item_key)

                existing_item = existing_item_map.get(item_key)

                if not existing_item:
                    new_item = OUTQueueItem(
                        output_queue_id=queue_row.id,
                        erp_weight_ticket_position_id=item["erp_weight_ticket_position_id"],
                        final_position_match_id=item["final_position_match_id"],
                        ticket_number=ticket.ticket_number,
                        timestamp_in=ticket.timestamp_in,
                        source_order_number=item["source_order_number"],
                        supplier_refno=item["supplier_refno"],
                        product_code=item["product_code"],
                        mp_amount=item["mp_amount"],
                        entry_status="OPEN",
                        resolved_at=None,
                        last_seen_at=now,
                        status="NEW",
                        source_type=item["source_type"],
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(new_item)
                    item_inserted += 1
                else:
                    existing_item.ticket_number = ticket.ticket_number
                    existing_item.timestamp_in = ticket.timestamp_in
                    existing_item.source_order_number = item["source_order_number"]
                    existing_item.supplier_refno = item["supplier_refno"]
                    existing_item.product_code = item["product_code"]
                    existing_item.mp_amount = item["mp_amount"]
                    existing_item.entry_status = "OPEN"
                    existing_item.last_seen_at = now
                    existing_item.resolved_at = None
                    existing_item.updated_at = now
                    item_updated += 1

            for existing_item_key, existing_item in existing_item_map.items():
                if existing_item_key not in seen_item_keys and existing_item.entry_status == "OPEN":
                    existing_item.entry_status = "RESOLVED"
                    existing_item.resolved_at = now
                    existing_item.last_seen_at = now
                    existing_item.updated_at = now
                    item_resolved += 1

        for queue_key, queue_row in existing_queue_by_key.items():
            if queue_key not in seen_queue_keys and queue_row.entry_status == "OPEN":
                queue_row.entry_status = "RESOLVED"
                queue_row.resolved_at = now
                queue_row.last_seen_at = now
                queue_row.updated_at = now
                queue_resolved += 1

                for existing_item in existing_items_by_queue_id.get(queue_row.id, {}).values():
                    if existing_item.entry_status == "OPEN":
                        existing_item.entry_status = "RESOLVED"
                        existing_item.resolved_at = now
                        existing_item.last_seen_at = now
                        existing_item.updated_at = now
                        item_resolved += 1

        session.commit()

    print(f"Zapisano output_queue nowe: {queue_inserted}")
    print(f"Zaktualizowano output_queue: {queue_updated}")
    print(f"Zamknięto output_queue: {queue_resolved}")

    print(f"Zapisano output_queue_items nowe: {item_inserted}")
    print(f"Zaktualizowano output_queue_items: {item_updated}")
    print(f"Zamknięto output_queue_items: {item_resolved}")

    print(f"Pominięto przez OPEN manual blocking: {skipped_manual}")
    print(f"Pominięto REMOVED: {skipped_removed}")
    print(f"Pominięto niepełne pozycje/final match: {skipped_incomplete_positions}")
    print(f"Pominięto brak product factor: {skipped_missing_factor}")

    print("KONIEC build_output_queue")

