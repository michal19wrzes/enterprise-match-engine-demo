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

def sync_external_documents():
    print("START sync_external_documents")

    raw_docs = fetch_recent_external_documents(
        max_pages=15,
        hours_back=375,
        document_type_codes="KW",
    )
    print(f"Pobrano pełnych dokumentów: {len(raw_docs)}")

    cutoff = datetime.now() - timedelta(hours=375)
    docs = []

    for doc in raw_docs:
        issue_date = parse_external_datetime(doc.get("issueDate"))
        if issue_date and issue_date >= cutoff:
            docs.append(doc)

    print(f"Po filtrze godzinowym : {len(docs)}")

    inserted = 0
    updated = 0

    with SessionLocal() as session:
        for doc in docs:
            doc_uuid = doc["uuid"]
            issue_date = parse_external_datetime(doc.get("issueDate"))

            existing = session.query(ExternalDocument).filter_by(uuid=doc_uuid).first()

            if not existing:
                external_doc = ExternalDocument(
                    uuid=doc.get("uuid"),
                    delivery_note_no=doc.get("deliveryNoteNo"),
                    region_code=doc.get("regionCode"),
                    inspectorate_code=doc.get("inspectorateCode"),
                    source_location_name=doc.get("sourceLocationName"),
                    issue_date=issue_date,
                    issuer_name=doc.get("issuerName"),
                    contract_major_identifier=doc.get("contractMajorIdentifier"),
                    contract_minor_identifier=doc.get("contractMinorIdentifier"),
                    transport_driver_name=doc.get("transportDriverName"),
                    carrier_name=doc.get("carrierName"),
                    car_registration_no=doc.get("carRegistrationNo"),
                    certificate_text=doc.get("certificateText"),
                    eudr_ref_no=doc.get("eudrRefNo"),
                    eudr_ver_code=doc.get("eudrVerCode"),
                    volume=doc.get("volume"),
                    weight=doc.get("weight"),
                    raw_json=json.dumps(doc, ensure_ascii=False),
                )
                session.add(external_doc)
                session.flush()
                document_id = external_doc.id
                inserted += 1
            else:
                existing.delivery_note_no = doc.get("deliveryNoteNo")
                existing.region_code = doc.get("regionCode")
                existing.inspectorate_code = doc.get("inspectorateCode")
                existing.source_location_name = doc.get("sourceLocationName")
                existing.issue_date = issue_date
                existing.issuer_name = doc.get("issuerName")
                existing.contract_major_identifier = doc.get("contractMajorIdentifier")
                existing.contract_minor_identifier = doc.get("contractMinorIdentifier")
                existing.transport_driver_name = doc.get("transportDriverName")
                existing.carrier_name = doc.get("carrierName")
                existing.car_registration_no = doc.get("carRegistrationNo")
                existing.certificate_text = doc.get("certificateText")
                existing.eudr_ref_no = doc.get("eudrRefNo")
                existing.eudr_ver_code = doc.get("eudrVerCode")
                existing.volume = doc.get("volume")
                existing.weight = doc.get("weight")
                existing.raw_json = json.dumps(doc, ensure_ascii=False)

                session.query(ExternalDocumentItem).filter_by(external_document_id=existing.id).delete()
                document_id = existing.id
                updated += 1

            for item in doc.get("items", []):
                session.add(
                    ExternalDocumentItem(
                        external_document_id=document_id,
                        position_no=item.get("positionNo"),
                        species_code=item.get("speciesCode"),
                        assortment_code=item.get("assortmentCode"),
                        dimensional_class=item.get("dimensionalClass"),
                        article_no=item.get("articleNo"),
                        forest_area=item.get("forestArea"),
                        wod_name=item.get("wodName"),
                        stock_no=item.get("stockNo"),
                        section_no=item.get("sectionNo"),
                        length=item.get("length"),
                        diameter=item.get("diameter"),
                        quantity=item.get("quantity"),
                        volume=item.get("volume"),
                        weight=item.get("weight"),
                    )
                )

        session.commit()

    print(f"Dodano EXT: {inserted}")
    print(f"Zaktualizowano EXT: {updated}")
    print("KONIEC sync_external_documents")

def rebuild_external_item_aggregates():
    print("START rebuild_external_item_aggregates")

    now = datetime.utcnow()

    with SessionLocal() as session:
        rows = (
            session.query(
                ExternalDocumentItem.external_document_id,
                func.min(ExternalDocumentItem.position_no).label("first_position_no"),
                ExternalDocumentItem.article_no,
                func.sum(ExternalDocumentItem.quantity).label("quantity_sum"),
                func.sum(ExternalDocumentItem.volume).label("volume_sum"),
                func.sum(ExternalDocumentItem.weight).label("weight_sum"),
            )
            .group_by(
                ExternalDocumentItem.external_document_id,
                ExternalDocumentItem.article_no,
            )
            .all()
        )

        existing_rows = session.query(ExternalDocumentItemAggregate).all()
        existing_by_key = {
            (
                row.external_document_id,
                str(row.article_no).strip() if row.article_no else None,
            ): row
            for row in existing_rows
            if row.article_no
        }

        seen_keys = set()

        inserted = 0
        updated = 0
        resolved = 0

        for row in rows:
            article_no = str(row.article_no).strip() if row.article_no else None
            if not article_no:
                continue

            key = (row.external_document_id, article_no)
            seen_keys.add(key)

            existing_row = existing_by_key.get(key)

            first_position_no = row.first_position_no
            volume_sum = float(row.volume_sum) if row.volume_sum is not None else None

            if not existing_row:
                session.add(
                    ExternalDocumentItemAggregate(
                        external_document_id=row.external_document_id,
                        position_no=first_position_no,
                        article_no=article_no,
                        volume_sum=volume_sum,
                        entry_status="OPEN",
                        first_detected_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                    )
                )
                inserted += 1
            else:
                existing_row.position_no = first_position_no
                existing_row.volume_sum = volume_sum
                existing_row.entry_status = "OPEN"
                existing_row.last_seen_at = now
                existing_row.resolved_at = None
                updated += 1

        for key, existing_row in existing_by_key.items():
            if key not in seen_keys and existing_row.entry_status == "OPEN":
                existing_row.entry_status = "RESOLVED"
                existing_row.last_seen_at = now
                existing_row.resolved_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano agregatów external nowe: {inserted}")
    print(f"Zaktualizowano agregatów EXT: {updated}")
    print(f"Zamknięto agregatów EXT: {resolved}")
    print("KONIEC rebuild_external_item_aggregates")

def rebuild_external_item_translated():
    print("START rebuild_external_item_translated")

    now = datetime.utcnow()

    with SessionLocal() as session:
        aggregates = session.query(ExternalDocumentItemAggregate).all()
        documents = session.query(ExternalDocument).all()
        article_mapper = session.query(ArticleNoMapper).all()
        existing_rows = session.query(ExternalDocumentItemTranslated).all()

        doc_by_id = {d.id: d for d in documents}
        mapper_by_article_no = {
            str(m.article_no).strip(): (str(m.product_code).strip() if m.product_code else None)
            for m in article_mapper
            if m.article_no
        }

        existing_by_key = {
            (row.external_document_id, str(row.product_code).strip() if row.product_code else None): row
            for row in existing_rows
            if row.product_code
        }

        grouped = {}
        seen_keys = set()

        inserted = 0
        updated = 0
        resolved = 0
        manual_added = 0

        existing_manual_keys = {
            (row.reason, row.details)
            for row in session.query(ToManualEntry).all()
            if row.reason and row.details
        }

        for agg in aggregates:
            article_no = str(agg.article_no).strip() if agg.article_no else None
            doc = doc_by_id.get(agg.external_document_id)

            if not doc or not article_no:
                continue

            product_code = mapper_by_article_no.get(article_no)

            if not product_code:
                reason = "MISSING_ARTICLE_MAPPING"
                details = f"external_uuid={doc.uuid}, article_no={article_no}"

                if (reason, details) not in existing_manual_keys:
                    session.add(
                        ToManualEntry(
                            erp_weight_ticket_id=None,
                            ticket_number=None,
                            timestamp_in=None,
                            truck_regnumber=doc.car_registration_no,
                            first_pos_supplier_refno=None,
                            position_count=None,
                            reason=reason,
                            details=details,
                        )
                    )
                    manual_added += 1
                    existing_manual_keys.add((reason, details))
                continue

            key = (agg.external_document_id, product_code)

            if key not in grouped:
                grouped[key] = {
                    "external_document_id": agg.external_document_id,
                    "external_uuid": doc.uuid,
                    "product_code": product_code,
                    "volume_sum": 0.0,
                    "source_count": 0,
                    "article_no_set": set(),
                }

            grouped[key]["volume_sum"] += float(agg.volume_sum or 0)
            grouped[key]["source_count"] += 1
            grouped[key]["article_no_set"].add(article_no)

        for key, row in grouped.items():
            seen_keys.add(key)
            existing_row = existing_by_key.get(key)

            article_no_list = " | ".join(sorted(row["article_no_set"]))

            if not existing_row:
                session.add(
                    ExternalDocumentItemTranslated(
                        external_document_id=row["external_document_id"],
                        external_uuid=row["external_uuid"],
                        product_code=row["product_code"],
                        volume_sum=row["volume_sum"],
                        source_count=row["source_count"],
                        article_no_list=article_no_list,
                        entry_status="OPEN",
                        first_detected_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                    )
                )
                inserted += 1
            else:
                existing_row.external_uuid = row["external_uuid"]
                existing_row.volume_sum = row["volume_sum"]
                existing_row.source_count = row["source_count"]
                existing_row.article_no_list = article_no_list
                existing_row.entry_status = "OPEN"
                existing_row.last_seen_at = now
                existing_row.resolved_at = None
                updated += 1

        for key, existing_row in existing_by_key.items():
            if key not in seen_keys and existing_row.entry_status == "OPEN":
                existing_row.entry_status = "RESOLVED"
                existing_row.last_seen_at = now
                existing_row.resolved_at = now
                resolved += 1

        session.commit()

    print(f"Zapisano external translated nowe: {inserted}")
    print(f"Zaktualizowano external translated: {updated}")
    print(f"Zamknięto external translated: {resolved}")
    print(f"Dodano manual (brak article mapping): {manual_added}")
    print("KONIEC rebuild_external_item_translated")
