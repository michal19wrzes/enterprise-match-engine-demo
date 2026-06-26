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

def sync_internal_product_sales_cache():
    print("START sync_internal_product_sales_cache")

    now = datetime.utcnow()

    rows_x = fetch_internal_product_sales_x()
    rows_y = fetch_internal_product_sales_y()

    all_rows = rows_x + rows_y
    print(f"Pobrano internal productsales: {len(all_rows)}")

    inserted = 0
    updated = 0
    resolved = 0

    with SessionLocal() as session:
        existing_rows = session.query(InternalProductSalesCache).all()
        existing_by_key = {
            (row.source_db, row.cdu_id, row.ticket_number, row.productsales_id): row
            for row in existing_rows
        }

        seen_keys = set()

        for (
            source_db,
            cdu_id,
            ticket_number,
            productsales_id,
            sale_date,
            truck_regnumber,
            trailer_regnumber,
            product_id,
            product_code,
            quantity_rm,
            tsc_pefc_id,
            tsc_fsc_cw_id,
        ) in all_rows:
            source_db = str(source_db).strip() if source_db else None
            cdu_id = str(cdu_id).strip() if cdu_id else None
            ticket_number = str(ticket_number).strip() if ticket_number else None
            product_code = str(product_code).strip() if product_code else None

            if not source_db or not cdu_id or not ticket_number or not productsales_id:
                continue

            key = (source_db, cdu_id, ticket_number, productsales_id)
            seen_keys.add(key)

            existing = existing_by_key.get(key)

            if not existing:
                session.add(
                    InternalProductSalesCache(
                        source_db=source_db,
                        cdu_id=cdu_id,
                        ticket_number=ticket_number,
                        productsales_id=productsales_id,
                        sale_date=sale_date,
                        truck_regnumber=truck_regnumber,
                        trailer_regnumber=trailer_regnumber,
                        product_id=product_id,
                        product_code=product_code,
                        quantity_rm=quantity_rm,
                        tsc_pefc_id=tsc_pefc_id,
                        tsc_fsc_cw_id=tsc_fsc_cw_id,
                        entry_status="OPEN",
                        first_detected_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                    )
                )
                inserted += 1
            else:
                existing.sale_date = sale_date
                existing.truck_regnumber = truck_regnumber
                existing.trailer_regnumber = trailer_regnumber
                existing.product_id = product_id
                existing.product_code = product_code
                existing.quantity_rm = quantity_rm
                existing.tsc_pefc_id = tsc_pefc_id
                existing.tsc_fsc_cw_id = tsc_fsc_cw_id
                existing.entry_status = "OPEN"
                existing.last_seen_at = now
                existing.resolved_at = None
                updated += 1

        for key, row in existing_by_key.items():
            if key not in seen_keys and row.entry_status == "OPEN":
                row.entry_status = "RESOLVED"
                row.resolved_at = now
                row.last_seen_at = now
                resolved += 1

        session.commit()

    print(f"Dodano cache internal sales: {inserted}")
    print(f"Zaktualizowano cache internal sales: {updated}")
    print(f"Zamknięto cache internal sales: {resolved}")
    print("KONIEC sync_internal_product_sales_cache")

