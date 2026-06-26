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

def sync_article_no_mapper():
    print("START sync_article_no_mapper")

    csv_path = Path(__file__).resolve().parent / "product_to_external_mapper.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku CSV: {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)

    print(f"Wczytano z CSV: {len(rows)} rekordów")

    inserted = 0
    updated = 0

    with SessionLocal() as session:
        existing_records = session.query(ArticleNoMapper).all()
        existing_by_article_no = {
            (str(r.article_no).strip() if r.article_no else ""): r
            for r in existing_records
        }

        for row in rows:
            article_no = str(row.get("articleNo", "")).strip()
            product_code = str(row.get("PRODUCT-kod", "")).strip()
            example_uuid = str(row.get("example_uuid", "")).strip()
            species_code = str(row.get("speciesCode", "")).strip()
            assortment_code = str(row.get("assortmentCode", "")).strip()
            dimensional_class = str(row.get("dimensionalClass", "")).strip()

            if not article_no:
                continue

            if article_no not in existing_by_article_no:
                session.add(
                    ArticleNoMapper(
                        article_no=article_no,
                        product_code=product_code or None,
                        example_uuid=example_uuid or None,
                        species_code=species_code or None,
                        assortment_code=assortment_code or None,
                        dimensional_class=dimensional_class or None,
                    )
                )
                inserted += 1
            else:
                record = existing_by_article_no[article_no]
                record.product_code = product_code or None
                record.example_uuid = example_uuid or None
                record.species_code = species_code or None
                record.assortment_code = assortment_code or None
                record.dimensional_class = dimensional_class or None
                updated += 1

        session.commit()

    print(f"Dodano article mapper: {inserted}")
    print(f"Zaktualizowano article mapper: {updated}")
    print("KONIEC sync_article_no_mapper")


from collections import defaultdict

def sync_region_mapper():
    print("START sync_region_mapper")

    csv_path = Path(__file__).resolve().parent / "mapper_region.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku CSV: {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)

    print(f"Wczytano z CSV: {len(rows)} rekordów")

    inserted = 0
    updated = 0

    with SessionLocal() as session:
        existing_records = session.query(RegionMapper).all()
        existing_by_key = {
            (str(r.region_code or ""), str(r.inspectorate_code or "")): r
            for r in existing_records
        }

        for row in rows:
            region_code = str(row.get("Kod REGION", "")).strip()
            inspectorate_code = str(row.get("Kod jednostki", "")).strip()
            region_name = str(row.get("REGION", "")).strip()
            inspectorate_name = str(row.get("Jednostka", "")).strip()
            postal_code = str(row.get("Kod pocztowy", "")).strip()
            voivodeship = str(row.get("województwo", "")).strip()
            erp_unit_code = str(row.get("MCODE", "")).strip()

            key = (region_code, inspectorate_code)

            if key not in existing_by_key:
                session.add(
                    RegionMapper(
                        region_code=region_code or None,
                        inspectorate_code=inspectorate_code or None,
                        region_name=region_name or None,
                        inspectorate_name=inspectorate_name or None,
                        postal_code=postal_code or None,
                        voivodeship=voivodeship or None,
                        erp_unit_code=erp_unit_code or None,
                    )
                )
                inserted += 1
            else:
                record = existing_by_key[key]
                record.region_name = region_name or None
                record.inspectorate_name = inspectorate_name or None
                record.postal_code = postal_code or None
                record.voivodeship = voivodeship or None
                record.erp_unit_code = erp_unit_code or None
                updated += 1

        session.commit()

    print(f"Dodano mapper RDEXT: {inserted}")
    print(f"Zaktualizowano mapper RDEXT: {updated}")
    print("KONIEC sync_region_mapper")

def sync_products():
    print("START sync_products")

    rows = fetch_products()
    print(f"Pobrano products: {len(rows)}")

    inserted = 0
    updated = 0

    with SessionLocal() as session:
        existing = {
            tp.product_id: tp
            for tp in session.query(Product).all()
        }

        for row in rows:
            (
                product_id,
                code,
                cdu_id,
                text,
                product_type_id,
                factor_fm_rm,
            ) = row

            if product_id not in existing:
                session.add(
                    Product(
                        product_id=product_id,
                        code=code,
                        cdu_id=cdu_id,
                        text=text,
                        product_type_id=product_type_id,
                        factor_fm_rm=factor_fm_rm,
                    )
                )
                inserted += 1
            else:
                tp = existing[product_id]
                tp.code = code
                tp.cdu_id = cdu_id
                tp.text = text
                tp.product_type_id = product_type_id
                tp.factor_fm_rm = factor_fm_rm
                updated += 1

        session.commit()

    print(f"Dodano products: {inserted}")
    print(f"Zaktualizowano products: {updated}")
    print("KONIEC sync_products")
