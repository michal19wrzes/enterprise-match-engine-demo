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

def sync_oracle_candidate_positions():
    print("START sync_oracle_candidate_positions")

    now = datetime.utcnow()

    rows = fetch_oracle_candidate_positions()
    allowed_mcodes_rows = fetch_partner_unit_mcodes()
    allowed_mcodes = {
        str(row[0]).strip()
        for row in allowed_mcodes_rows
        if row[0] is not None
    }

    valid_type1_ticket_numbers, manual_type1_ticket_numbers, _, type3_ticket_numbers = classify_tickets_by_supplier_ref(
        rows,
        allowed_mcodes=allowed_mcodes,
    )

    valid_type2_ticket_numbers, manual_type2_ticket_numbers, _ = classify_type2_tickets(rows)

    print(f"Pobrano pozycji z Oracle: {len(rows)}")
    print(f"Pozycje type=1 ticketów: {len(valid_type1_ticket_numbers)}")
    print(f"Pozycje type=2 ticketów: {len(valid_type2_ticket_numbers)}")
    print(f"Pozycje type=1 manual ticketów: {len(manual_type1_ticket_numbers)}")
    print(f"Pozycje type=2 manual ticketów: {len(manual_type2_ticket_numbers)}")
    print(f"Pozycje type=3 ticketów: {len(type3_ticket_numbers)}")

    positions_by_ticket = defaultdict(list)

    for row in rows:
        ticket_number = str(row[0])
        if (
            ticket_number in valid_type1_ticket_numbers
            or ticket_number in manual_type1_ticket_numbers
            or ticket_number in valid_type2_ticket_numbers
            or ticket_number in manual_type2_ticket_numbers
            or ticket_number in type3_ticket_numbers
        ):
            positions_by_ticket[ticket_number].append(row)

    print(f"Po filtrze: {len(positions_by_ticket)} ticketów")

    inserted = 0
    updated = 0
    resolved = 0

    with SessionLocal() as session:
        tickets = session.query(ERPWeightTicket).all()
        ticket_map = {t.ticket_number: t for t in tickets}

        all_existing_positions = session.query(ERPWeightTicketPosition).all()
        existing_by_ticket_id = defaultdict(dict)

        for pos in all_existing_positions:
            if pos.pos_number is not None:
                existing_by_ticket_id[pos.erp_weight_ticket_id][pos.pos_number] = pos

        processed_ticket_ids = set()

        for ticket_number, pos_rows in positions_by_ticket.items():
            if ticket_number not in ticket_map:
                continue

            ticket = ticket_map[ticket_number]
            processed_ticket_ids.add(ticket.id)

            pos_rows = sorted(pos_rows, key=lambda r: (r[1] is None, r[1]))
            existing_pos_map = existing_by_ticket_id.get(ticket.id, {})
            seen_pos_numbers = set()

            for row in pos_rows:
                (
                    _ticket_number,
                    pos_number,
                    product_id,
                    material_supplier_id,
                    material_address_id,
                    quantity_rm,
                    supplier_refno,
                    productdisposition_id,
                    source_order_number,
                    product_code,
                    product_text,
                    product_type_id,
                    supplier_code,      
                    productprovisionposition_id,
                    productcontractposition_id,
                    source_order_product_type_id,
                ) = row

                if pos_number is None:
                    continue

                seen_pos_numbers.add(pos_number)
                existing_pos = existing_pos_map.get(pos_number)

                if not existing_pos:
                    session.add(
                        ERPWeightTicketPosition(
                            erp_weight_ticket_id=ticket.id,
                            pos_number=pos_number,
                            product_id=product_id,
                            material_supplier_id=material_supplier_id,
                            material_address_id=material_address_id,
                            quantity_rm=quantity_rm,
                            supplier_refno=supplier_refno,
                            productdisposition_id=productdisposition_id,
                            source_order_number=source_order_number,
                            product_code=product_code,
                            product_text=product_text,
                            product_type_id=product_type_id,
                            supplier_code=supplier_code,
                            productprovisionposition_id=productprovisionposition_id,
                            productcontractposition_id=productcontractposition_id,
                            source_order_product_type_id=source_order_product_type_id,
                            type=ticket.type,
                            entry_status="OPEN",
                            first_detected_at=now,
                            last_seen_at=now,
                            resolved_at=None,
                        )
                    )
                    inserted += 1
                else:
                    existing_pos.product_id = product_id
                    existing_pos.material_supplier_id = material_supplier_id
                    existing_pos.material_address_id = material_address_id
                    existing_pos.quantity_rm = quantity_rm
                    existing_pos.supplier_refno = supplier_refno
                    existing_pos.productdisposition_id = productdisposition_id
                    existing_pos.source_order_number = source_order_number
                    existing_pos.product_code = product_code
                    existing_pos.product_text = product_text
                    existing_pos.product_type_id = product_type_id
                    existing_pos.supplier_code = supplier_code
                    existing_pos.productprovisionposition_id = productprovisionposition_id
                    existing_pos.productcontractposition_id = productcontractposition_id
                    existing_pos.source_order_product_type_id = source_order_product_type_id
                    existing_pos.type = ticket.type
                    existing_pos.entry_status = "OPEN"
                    existing_pos.last_seen_at = now
                    existing_pos.resolved_at = None
                    updated += 1

            ticket.position_count = len([r for r in pos_rows if r[1] is not None])

            if pos_rows:
                first_row = pos_rows[0]
                ticket.first_pos_product_code = first_row[9]
                ticket.first_pos_mcode = first_row[12]
                ticket.first_pos_supplier_refno = first_row[6]

            for existing_pos_number, existing_pos in existing_pos_map.items():
                if existing_pos_number not in seen_pos_numbers and existing_pos.entry_status == "OPEN":
                    existing_pos.entry_status = "RESOLVED"
                    existing_pos.last_seen_at = now
                    existing_pos.resolved_at = now
                    resolved += 1

        current_ticket_ids = set(processed_ticket_ids)

        for ticket in tickets:
            if ticket.id not in current_ticket_ids:
                existing_pos_map = existing_by_ticket_id.get(ticket.id, {})
                for existing_pos in existing_pos_map.values():
                    if existing_pos.entry_status == "OPEN":
                        existing_pos.entry_status = "RESOLVED"
                        existing_pos.last_seen_at = now
                        existing_pos.resolved_at = now
                        resolved += 1

        session.commit()

    print(f"Zapisano pozycji nowe: {inserted}")
    print(f"Zaktualizowano pozycji: {updated}")
    print(f"Zamknięto pozycji: {resolved}")
    print("KONIEC sync_oracle_candidate_positions")


def sync_oracle_candidates():
    print("START sync_oracle_candidates")

    rows = fetch_oracle_candidates()
    print(f"Pobrano z Oracle: {len(rows)} rekordów")

    rows_pos = fetch_oracle_candidate_positions()

    allowed_mcodes_rows = fetch_partner_unit_mcodes()
    allowed_mcodes = {
        str(row[0]).strip()
        for row in allowed_mcodes_rows
        if row[0] is not None
    }

    valid_type1_ticket_numbers, manual_type1_ticket_numbers, _, type3_ticket_numbers = classify_tickets_by_supplier_ref(
        rows_pos,
        allowed_mcodes=allowed_mcodes,
    )
    valid_type2_ticket_numbers, manual_type2_ticket_numbers, _ = classify_type2_tickets(rows_pos)

    print(f"Tickety type=1 valid: {len(valid_type1_ticket_numbers)}")
    print(f"Tickety type=2 valid: {len(valid_type2_ticket_numbers)}")
    print(f"Tickety type=3 valid: {len(type3_ticket_numbers)}")
    print(f"Tickety type=2 manual: {len(manual_type2_ticket_numbers)}")
    print(f"Tickety type=1 manual: {len(manual_type1_ticket_numbers)}")

    deduped = {}
    ticket_type_map = {}

    manual_ticket_numbers_to_mark = set()
    

    for row in rows:
        ticket_number = str(row[0])

        if ticket_number in type3_ticket_numbers:
            deduped[ticket_number] = row
            ticket_type_map[ticket_number] = 3

        elif ticket_number in valid_type2_ticket_numbers:
            deduped[ticket_number] = row
            ticket_type_map[ticket_number] = 2

        elif ticket_number in manual_type2_ticket_numbers:
            deduped[ticket_number] = row
            ticket_type_map[ticket_number] = 2
            manual_ticket_numbers_to_mark.add(ticket_number)

        elif ticket_number in valid_type1_ticket_numbers:
            deduped[ticket_number] = row
            ticket_type_map[ticket_number] = 1

        elif ticket_number in manual_type1_ticket_numbers:
            deduped[ticket_number] = row
            ticket_type_map[ticket_number] = 1
            manual_ticket_numbers_to_mark.add(ticket_number)

    rows = list(deduped.values())
    print(f"Po filtrze: {len(rows)} rekordów")

    current_ticket_numbers = {str(row[0]) for row in rows}

    inserted = 0
    reactivated = 0
    removed = 0

    with SessionLocal() as session:
        existing_records = session.query(ERPWeightTicket).all()
        existing_by_ticket = {row.ticket_number: row for row in existing_records}

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
            ticket_type = ticket_type_map[ticket_number]

            if ticket_number not in existing_by_ticket:
                new_record = ERPWeightTicket(
                    ticket_number=ticket_number,
                    timestamp_in=timestamp_in,
                    processing_status=processing_status,
                    truck_regnumber=truck_regnumber,
                    vehicletype=vehicletype,
                    cdu_id="DEMO_SITE",
                    location_code=0,
                    length1=length1,
                    width1=width1,
                    height1=height1,
                    gap1=gap1,
                    quantity_rm1=quantity_rm1,
                    length2=length2,
                    width2=width2,
                    height2=height2,
                    gap2=gap2,
                    quantity_rm2=quantity_rm2,
                    type=ticket_type,
                    status="MANUAL" if ticket_number in manual_ticket_numbers_to_mark else "ACTIVE",
                )
                session.add(new_record)
                existing_by_ticket[ticket_number] = new_record
                inserted += 1
            else:
                record = existing_by_ticket[ticket_number]
                record.timestamp_in = timestamp_in
                record.processing_status = processing_status
                record.truck_regnumber = truck_regnumber
                record.vehicletype = vehicletype
                record.length1 = length1
                record.width1 = width1
                record.height1 = height1
                record.gap1 = gap1
                record.quantity_rm1 = quantity_rm1
                record.length2 = length2
                record.width2 = width2
                record.height2 = height2
                record.gap2 = gap2
                record.quantity_rm2 = quantity_rm2
                record.type = ticket_type

                if ticket_number in manual_ticket_numbers_to_mark:
                    record.status = "MANUAL"
                elif record.status == "REMOVED":
                    record.status = "ACTIVE"
                    reactivated += 1

        for record in existing_records:
            if record.ticket_number not in current_ticket_numbers and record.status in ("ACTIVE", "MANUAL"):
                record.status = "REMOVED"
                removed += 1

        session.commit()

    print(f"Dodano: {inserted}")
    print(f"Przywrócono: {reactivated}")
    print(f"Oznaczono jako REMOVED: {removed}")
    print("KONIEC sync_oracle_candidates")

