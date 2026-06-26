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

def validate_source_order_product_type_match():
    print("START validate_source_order_product_type_match")

    reason_text = "Translated external product type does not match source order product type"

    with SessionLocal() as session:
        now = datetime.utcnow()

        final_matches = session.query(FinalPositionMatch).filter(
            FinalPositionMatch.entry_status == "OPEN",
        ).all()

        positions = session.query(ERPWeightTicketPosition).filter(
            ERPWeightTicketPosition.type == 1,
            ERPWeightTicketPosition.entry_status == "OPEN",
        ).all()

        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
        ).all()

        products = session.query(Product).all()

        position_by_id = {p.id: p for p in positions}
        ticket_by_id = {t.id: t for t in tickets}

        product_by_code_cdu = {
            (
                str(tp.code).strip(),
                str(tp.cdu_id).strip() if tp.cdu_id else None,
            ): tp
            for tp in products
            if tp.code
        }

        final_by_ticket = defaultdict(list)
        for fm in final_matches:
            final_by_ticket[fm.erp_weight_ticket_id].append(fm)

        inserted = 0
        updated = 0
        marked_manual = 0
        missing_product = 0
        missing_source_order_type = 0
        active_fingerprints = set()

        for ticket in tickets:
            fm_rows = final_by_ticket.get(ticket.id, [])
            if not fm_rows:
                continue

            invalid_positions = []

            ticket_cdu_id = str(ticket.cdu_id).strip() if ticket.cdu_id else None

            for fm in fm_rows:
                pos = position_by_id.get(fm.erp_weight_ticket_position_id)
                if not pos:
                    continue

                source_order_type = pos.source_order_product_type_id

                if source_order_type is None:
                    missing_source_order_type += 1
                    invalid_positions.append(
                        f"pos={pos.pos_number}, "
                        f"source_order_number={pos.source_order_number}, "
                        f"productdisposition_id={pos.productdisposition_id}, "
                        f"productprovisionposition_id={pos.productprovisionposition_id}, "
                        f"productcontractposition_id={pos.productcontractposition_id}, "
                        f"external_product_code={fm.external_product_code}, "
                        f"error=Missing product type derived from source order"
                    )
                    continue

                external_code = str(fm.external_product_code).strip() if fm.external_product_code else None

                if not external_code:
                    invalid_positions.append(
                        f"pos={pos.pos_number}, "
                        f"source_order_number={pos.source_order_number}, "
                        f"error=Brak external_product_code w final_position_matches"
                    )
                    continue

                tp = product_by_code_cdu.get((external_code, ticket_cdu_id))

                if not tp:
                    # fallback, gdy lokalnie ticket ma inne cdu_id albo product jest bez CDU
                    candidates = [
                        row for row in products
                        if row.code and str(row.code).strip() == external_code
                    ]

                    if len(candidates) == 1:
                        tp = candidates[0]

                if not tp:
                    missing_product += 1
                    invalid_positions.append(
                        f"pos={pos.pos_number}, "
                        f"source_order_number={pos.source_order_number}, "
                        f"external_product_code={external_code}, "
                        f"ticket_cdu_id={ticket_cdu_id}, "
                        f"error=Nie znaleziono product dla kodu external po translacji"
                    )
                    continue

                external_type = tp.product_type_id

                if external_type != source_order_type:
                    invalid_positions.append(
                        f"pos={pos.pos_number}, "
                        f"source_order_number={pos.source_order_number}, "
                        f"TEXT1={pos.supplier_refno}, "
                        f"external_document_id={fm.external_document_id}, "
                        f"external_product_code={external_code}, "
                        f"external_product_type_id={external_type}, "
                        f"source_order_product_type_id={source_order_type}, "
                        f"productdisposition_id={pos.productdisposition_id}, "
                        f"productprovisionposition_id={pos.productprovisionposition_id}, "
                        f"productcontractposition_id={pos.productcontractposition_id}"
                    )

            if not invalid_positions:
                continue

            details_text = " | ".join(invalid_positions)

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
    print(f"Missing source order type: {missing_source_order_type}")
    print(f"Brak product po kodzie EXT: {missing_product}")
    print("KONIEC validate_source_order_product_type_match")

def validate_missing_article_no_mapping():
    print("START validate_missing_article_no_mapping")

    reason_text = "Brak mapowania PRODUCT article_no do product_code"

    with SessionLocal() as session:
        now = datetime.utcnow()

        aggregates = session.query(ExternalDocumentItemAggregate).filter(
            ExternalDocumentItemAggregate.entry_status == "OPEN",
        ).all()

        documents = session.query(ExternalDocument).all()
        mapper_rows = session.query(ArticleNoMapper).all()

        doc_by_id = {d.id: d for d in documents}

        mapped_article_nos = {
            str(row.article_no).strip()
            for row in mapper_rows
            if row.article_no
        }

        inserted = 0
        updated = 0
        active_fingerprints = set()

        for agg in aggregates:
            article_no = str(agg.article_no).strip() if agg.article_no else None

            if not article_no:
                continue

            if article_no in mapped_article_nos:
                continue

            doc = doc_by_id.get(agg.external_document_id)

            details_text = (
                f"external_document_id={agg.external_document_id}, "
                f"external_uuid={doc.uuid if doc else None}, "
                f"article_no={article_no}, "
                f"volume_sum={agg.volume_sum}"
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    None,
                    reason_text,
                    details_text,
                )
            )

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=None,
                ticket_number=None,
                timestamp_in=None,
                truck_regnumber=doc.car_registration_no if doc else None,
                first_pos_supplier_refno=None,
                position_count=None,
                reason=reason_text,
                details=details_text,
                now=now,
            )

            if created:
                inserted += 1
            else:
                updated += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {reason_text},
            now=now,
        )

        session.commit()

    print(f"Dodano manual PRODUCT mapper: {inserted}")
    print(f"Zaktualizowano manual PRODUCT mapper: {updated}")
    print("KONIEC validate_missing_article_no_mapping")

def validate_missing_region_mapping():
    print("START validate_missing_region_mapping")

    reason_text = "Brak mapowania REGION inspectorate do ERP unit code"

    with SessionLocal() as session:
        now = datetime.utcnow()

        documents = session.query(ExternalDocument).all()
        mapper_rows = session.query(RegionMapper).all()

        mapper_by_inspectorate = {
            str(row.inspectorate_code).strip(): row
            for row in mapper_rows
            if row.inspectorate_code
        }

        inserted = 0
        updated = 0
        active_fingerprints = set()

        for doc in documents:
            inspectorate_4 = build_external_inspectorate_code(
                doc.region_code,
                doc.inspectorate_code,
            )

            if not inspectorate_4:
                continue

            mapper_row = mapper_by_inspectorate.get(inspectorate_4)

            if mapper_row and mapper_row.erp_unit_code:
                continue

            details_text = (
                f"external_document_id={doc.id}, "
                f"external_uuid={doc.uuid}, "
                f"region_code={doc.region_code}, "
                f"inspectorate_code={doc.inspectorate_code}, "
                f"inspectorate_4={inspectorate_4}, "
                f"delivery_note_no={doc.delivery_note_no}, "
                f"car_registration_no={doc.car_registration_no}"
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    None,
                    reason_text,
                    details_text,
                )
            )

            _, created, _ = upsert_manual_entry(
                session,
                erp_weight_ticket_id=None,
                ticket_number=None,
                timestamp_in=doc.issue_date,
                truck_regnumber=doc.car_registration_no,
                first_pos_supplier_refno=None,
                position_count=None,
                reason=reason_text,
                details=details_text,
                now=now,
            )

            if created:
                inserted += 1
            else:
                updated += 1

        resolve_missing_manual_entries(
            session,
            active_fingerprints,
            {reason_text},
            now=now,
        )

        session.commit()

    print(f"Dodano manual REGION mapper: {inserted}")
    print(f"Zaktualizowano manual REGION mapper: {updated}")
    print("KONIEC validate_missing_region_mapping")
