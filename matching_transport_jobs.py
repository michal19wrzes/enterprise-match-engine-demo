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

def build_transport_header_matches():
    print("START build_transport_header_matches")

    now = datetime.utcnow()

    with SessionLocal() as session:
        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.status != "REMOVED",
            ERPWeightTicket.type == 1,
        ).all()

        documents = session.query(ExternalDocument).all()
        mapper_rows = session.query(RegionMapper).all()
        existing_rows = session.query(TransportHeaderMatch).all()

        mapper_by_inspectorate = {
            str(row.inspectorate_code).strip(): row
            for row in mapper_rows
            if row.inspectorate_code
        }

        existing_by_key = {
            (row.erp_weight_ticket_id, row.external_document_id): row
            for row in existing_rows
        }

        seen_keys = set()

        inserted = 0
        updated = 0
        resolved = 0

        for ticket in tickets:
            first_pos_mcode = str(ticket.first_pos_mcode).strip() if ticket.first_pos_mcode else None
            if not first_pos_mcode or not ticket.timestamp_in:
                continue

            for doc in documents:
                if not doc.issue_date:
                    continue

                if not registration_match(doc.car_registration_no, ticket.truck_regnumber):
                    continue

                inspectorate_4 = build_external_inspectorate_code(doc.region_code, doc.inspectorate_code)
                if not inspectorate_4:
                    continue

                mapper_row = mapper_by_inspectorate.get(inspectorate_4)
                if not mapper_row or not mapper_row.erp_unit_code:
                    continue

                erp_unit_code = str(mapper_row.erp_unit_code).strip()
                if erp_unit_code != first_pos_mcode:
                    continue

                if ticket.timestamp_in <= doc.issue_date:
                    continue

                diff_seconds = int((ticket.timestamp_in - doc.issue_date).total_seconds())
                registration_debug = f"{doc.car_registration_no} ↔ {ticket.truck_regnumber}"

                key = (ticket.id, doc.id)
                seen_keys.add(key)

                existing_row = existing_by_key.get(key)

                if not existing_row:
                    session.add(
                        TransportHeaderMatch(
                            erp_weight_ticket_id=ticket.id,
                            external_document_id=doc.id,
                            erp_ticket_number=ticket.ticket_number,
                            erp_timestamp_in=ticket.timestamp_in,
                            erp_truck_regnumber=ticket.truck_regnumber,
                            erp_first_pos_mcode=first_pos_mcode,
                            external_uuid=doc.uuid,
                            external_issue_date=doc.issue_date,
                            external_delivery_note_no=doc.delivery_note_no,
                            external_car_registration_no=doc.car_registration_no,
                            external_region_code=doc.region_code,
                            external_inspectorate_code=doc.inspectorate_code,
                            external_erp_unit_code=erp_unit_code,
                            registration_match_value=registration_debug,
                            match_key_truck_reg=ticket.truck_regnumber,
                            match_key_erp_unit_code=first_pos_mcode,
                            time_diff_seconds=diff_seconds,
                            match_status="MATCHED",
                            entry_status="OPEN",
                            first_detected_at=now,
                            last_seen_at=now,
                            resolved_at=None,
                        )
                    )
                    inserted += 1
                else:
                    existing_row.erp_ticket_number = ticket.ticket_number
                    existing_row.erp_timestamp_in = ticket.timestamp_in
                    existing_row.erp_truck_regnumber = ticket.truck_regnumber
                    existing_row.erp_first_pos_mcode = first_pos_mcode
                    existing_row.external_uuid = doc.uuid
                    existing_row.external_issue_date = doc.issue_date
                    existing_row.external_delivery_note_no = doc.delivery_note_no
                    existing_row.external_car_registration_no = doc.car_registration_no
                    existing_row.external_region_code = doc.region_code
                    existing_row.external_inspectorate_code = doc.inspectorate_code
                    existing_row.external_erp_unit_code = erp_unit_code
                    existing_row.registration_match_value = registration_debug
                    existing_row.match_key_truck_reg = ticket.truck_regnumber
                    existing_row.match_key_erp_unit_code = first_pos_mcode
                    existing_row.time_diff_seconds = diff_seconds
                    existing_row.match_status = "MATCHED"
                    existing_row.entry_status = "OPEN"
                    existing_row.last_seen_at = now
                    existing_row.resolved_at = None
                    updated += 1

        active_ticket_ids = {ticket.id for ticket in tickets}

        for key, row in existing_by_key.items():
            erp_weight_ticket_id, external_document_id = key

            if erp_weight_ticket_id not in active_ticket_ids:
                continue

            if key not in seen_keys and row.entry_status == "OPEN":
                row.entry_status = "RESOLVED"
                row.resolved_at = now
                row.last_seen_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano matchy nagłówków nowe: {inserted}")
    print(f"Zaktualizowano matchy nagłówków: {updated}")
    print(f"Zamknięto matchy nagłówków: {resolved}")
    print("KONIEC build_transport_header_matches")


def build_transport_position_matches():
    print("START build_transport_position_matches")

    now = datetime.utcnow()

    with SessionLocal() as session:
        header_matches = session.query(TransportHeaderMatch).filter(
            TransportHeaderMatch.entry_status == "OPEN"
        ).all()

        ticket_positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.entry_status == "OPEN",
            ERPWeightTicketPosition.type == 1,
        ).all()

        external_documents = session.query(ExternalDocument).all()

        existing_rows = session.query(TransportPositionMatch).all()

        positions_by_ticket_id = defaultdict(list)
        for pos in ticket_positions:
            positions_by_ticket_id[pos.erp_weight_ticket_id].append(pos)

        external_doc_by_id = {doc.id: doc for doc in external_documents}

        existing_by_key = {
            (row.transport_header_match_id, row.erp_weight_ticket_position_id): row
            for row in existing_rows
        }

        seen_keys = set()

        inserted = 0
        updated = 0
        resolved = 0

        for hm in header_matches:
            doc = external_doc_by_id.get(hm.external_document_id)
            if not doc:
                continue

            if not doc.delivery_note_no:
                continue

            ticket_pos_list = positions_by_ticket_id.get(hm.erp_weight_ticket_id, [])
            if not ticket_pos_list:
                continue

            for pos in ticket_pos_list:
                if not supplier_refno_match(pos.supplier_refno, doc.delivery_note_no):
                    continue

                normalized_ref = normalize_supplier_refno(pos.supplier_refno)

                key = (hm.id, pos.id)
                seen_keys.add(key)

                existing_row = existing_by_key.get(key)

                if not existing_row:
                    session.add(
                        TransportPositionMatch(
                            transport_header_match_id=hm.id,
                            erp_weight_ticket_position_id=pos.id,
                            external_document_id=doc.id,
                            erp_ticket_number=hm.erp_ticket_number,
                            erp_pos_number=pos.pos_number,
                            erp_supplier_refno=pos.supplier_refno,
                            normalized_supplier_refno=normalized_ref,
                            erp_source_order_number=pos.source_order_number,
                            erp_product_code=pos.product_code,
                            erp_supplier_code=pos.supplier_code,
                            external_uuid=doc.uuid,
                            external_delivery_note_no=doc.delivery_note_no,
                            external_issue_date=doc.issue_date,
                            match_key_supplier_refno=normalized_ref,
                            match_status="MATCHED",
                            entry_status="OPEN",
                            first_detected_at=now,
                            last_seen_at=now,
                            resolved_at=None,
                        )
                    )
                    inserted += 1
                else:
                    existing_row.external_document_id = doc.id
                    existing_row.erp_ticket_number = hm.erp_ticket_number
                    existing_row.erp_pos_number = pos.pos_number
                    existing_row.erp_supplier_refno = pos.supplier_refno
                    existing_row.normalized_supplier_refno = normalized_ref
                    existing_row.erp_source_order_number = pos.source_order_number
                    existing_row.erp_product_code = pos.product_code
                    existing_row.erp_supplier_code = pos.supplier_code
                    existing_row.external_uuid = doc.uuid
                    existing_row.external_delivery_note_no = doc.delivery_note_no
                    existing_row.external_issue_date = doc.issue_date
                    existing_row.match_key_supplier_refno = normalized_ref
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

    print(f"Zapisano matchy pozycji nowe: {inserted}")
    print(f"Zaktualizowano matchy pozycji: {updated}")
    print(f"Zamknięto matchy pozycji: {resolved}")
    print("KONIEC build_transport_position_matches")


def build_transport_position_best_matches():
    print("START build_transport_position_best_matches")

    now = datetime.utcnow()

    with SessionLocal() as session:
        header_matches = session.query(TransportHeaderMatch).filter(
            TransportHeaderMatch.entry_status == "OPEN"
        ).all()

        position_matches = session.query(TransportPositionMatch).filter(
            TransportPositionMatch.entry_status == "OPEN"
        ).all()

        erp_type1_position_ids = {
            row.id
            for row in session.query(ERPWeightTicketPosition).filter(
                ERPWeightTicketPosition.entry_status == "OPEN",
                ERPWeightTicketPosition.type == 1,
            ).all()
        }

        existing_rows = session.query(TransportPositionBestMatch).all()

        header_by_id = {hm.id: hm for hm in header_matches}

        existing_by_erp_position_id = {
            row.erp_weight_ticket_position_id: row
            for row in existing_rows
        }

        best_by_erp_position = {}

        for pm in position_matches:
            if pm.erp_weight_ticket_position_id not in erp_type1_position_ids:
                continue

            hm = header_by_id.get(pm.transport_header_match_id)
            if not hm:
                continue

            key = pm.erp_weight_ticket_position_id
            current_diff = hm.time_diff_seconds if hm.time_diff_seconds is not None else 999999999

            if key not in best_by_erp_position:
                best_by_erp_position[key] = (pm, hm, current_diff)
            else:
                _, _, best_diff = best_by_erp_position[key]
                if current_diff < best_diff:
                    best_by_erp_position[key] = (pm, hm, current_diff)

        seen_position_ids = set()

        inserted = 0
        updated = 0
        resolved = 0

        for erp_position_id, (pm, hm, diff_seconds) in best_by_erp_position.items():
            seen_position_ids.add(erp_position_id)

            existing_row = existing_by_erp_position_id.get(erp_position_id)

            if not existing_row:
                session.add(
                    TransportPositionBestMatch(
                        transport_position_match_id=pm.id,
                        transport_header_match_id=pm.transport_header_match_id,
                        erp_weight_ticket_position_id=pm.erp_weight_ticket_position_id,
                        external_document_id=pm.external_document_id,
                        erp_ticket_number=pm.erp_ticket_number,
                        erp_pos_number=pm.erp_pos_number,
                        external_uuid=pm.external_uuid,
                        external_delivery_note_no=pm.external_delivery_note_no,
                        time_diff_seconds=diff_seconds,
                        match_status="BEST_MATCH",
                        entry_status="OPEN",
                        first_detected_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                    )
                )
                inserted += 1
            else:
                existing_row.transport_position_match_id = pm.id
                existing_row.transport_header_match_id = pm.transport_header_match_id
                existing_row.external_document_id = pm.external_document_id
                existing_row.erp_ticket_number = pm.erp_ticket_number
                existing_row.erp_pos_number = pm.erp_pos_number
                existing_row.external_uuid = pm.external_uuid
                existing_row.external_delivery_note_no = pm.external_delivery_note_no
                existing_row.time_diff_seconds = diff_seconds
                existing_row.match_status = "BEST_MATCH"
                existing_row.entry_status = "OPEN"
                existing_row.last_seen_at = now
                existing_row.resolved_at = None
                updated += 1

        for erp_position_id, row in existing_by_erp_position_id.items():
            if row.erp_weight_ticket_position_id not in erp_type1_position_ids:
                continue

            if erp_position_id not in seen_position_ids and row.entry_status == "OPEN":
                row.entry_status = "RESOLVED"
                row.resolved_at = now
                row.last_seen_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano best matches pozycji nowe: {inserted}")
    print(f"Zaktualizowano best matches pozycji: {updated}")
    print(f"Zamknięto best matches pozycji: {resolved}")
    print("KONIEC build_transport_position_best_matches")

