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

def validate_type1_active_without_output_to_manual():
    print("START validate_type1_active_without_output_to_manual")

    REASON_MISSING_HEADER = "Nie znaleziono dopasowania nagłówka SRC do dokumentu external"
    REASON_MISSING_POSITION = "Nie znaleziono dopasowania pozycji SRC do dokumentu external"
    REASON_MISSING_BEST = "Nie wybrano najlepszego dopasowania pozycji SRC do dokumentu external"
    REASON_MISSING_FINAL = "Nie zbudowano finalnego dopasowania pozycji SRC do dokumentu external"

    reasons = {
        REASON_MISSING_HEADER,
        REASON_MISSING_POSITION,
        REASON_MISSING_BEST,
        REASON_MISSING_FINAL,
    }

    with SessionLocal() as session:
        now = datetime.utcnow()

        # Celowo NIE filtrujemy po status == ACTIVE.
        # Łapiemy każdy type=1, który nie jest REMOVED i nie ma ani OPEN OUT, ani OPEN manuala.
        tickets = session.query(ERPWeightTicket).filter(
            ERPWeightTicket.type == 1,
            ERPWeightTicket.status != "REMOVED",
        ).all()

        open_output_ticket_ids = {
            row[0]
            for row in session.query(OUTQueue.erp_weight_ticket_id)
            .filter(
                OUTQueue.entry_status == "OPEN",
                OUTQueue.source_type == 1,
                OUTQueue.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        open_manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        header_ticket_ids = {
            row[0]
            for row in session.query(TransportHeaderMatch.erp_weight_ticket_id)
            .filter(
                TransportHeaderMatch.entry_status == "OPEN",
                TransportHeaderMatch.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        position_match_ticket_ids = {
            row[0]
            for row in session.query(ERPWeightTicketPosition.erp_weight_ticket_id)
            .join(
                TransportPositionMatch,
                TransportPositionMatch.erp_weight_ticket_position_id == ERPWeightTicketPosition.id,
            )
            .filter(
                ERPWeightTicketPosition.entry_status == "OPEN",
                ERPWeightTicketPosition.type == 1,
                TransportPositionMatch.entry_status == "OPEN",
            )
            .distinct()
            .all()
        }

        best_match_ticket_ids = {
            row[0]
            for row in session.query(ERPWeightTicketPosition.erp_weight_ticket_id)
            .join(
                TransportPositionBestMatch,
                TransportPositionBestMatch.erp_weight_ticket_position_id == ERPWeightTicketPosition.id,
            )
            .filter(
                ERPWeightTicketPosition.entry_status == "OPEN",
                ERPWeightTicketPosition.type == 1,
                TransportPositionBestMatch.entry_status == "OPEN",
            )
            .distinct()
            .all()
        }

        final_match_ticket_ids = {
            row[0]
            for row in session.query(FinalPositionMatch.erp_weight_ticket_id)
            .filter(
                FinalPositionMatch.entry_status == "OPEN",
                FinalPositionMatch.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        inserted = 0
        updated = 0
        marked_manual = 0
        skipped_pz = 0
        skipped_manual = 0

        active_fingerprints = set()

        print(f"TYPE1 not REMOVED tickets: {len(tickets)}")
        print(f"OPEN OUT ticket ids: {len(open_output_ticket_ids)}")
        print(f"OPEN manual ticket ids: {len(open_manual_ticket_ids)}")

        for ticket in tickets:
            if ticket.id in open_output_ticket_ids:
                skipped_pz += 1
                continue

            if ticket.id in open_manual_ticket_ids:
                skipped_manual += 1
                continue

            if ticket.id not in header_ticket_ids:
                reason_text = REASON_MISSING_HEADER
                reason_source = "MISSING_HEADER_MATCH"
            elif ticket.id not in position_match_ticket_ids:
                reason_text = REASON_MISSING_POSITION
                reason_source = "HEADER_EXISTS_BUT_NO_POSITION_MATCH"
            elif ticket.id not in best_match_ticket_ids:
                reason_text = REASON_MISSING_BEST
                reason_source = "POSITION_MATCH_EXISTS_BUT_NO_BEST_MATCH"
            elif ticket.id not in final_match_ticket_ids:
                reason_text = REASON_MISSING_FINAL
                reason_source = "BEST_MATCH_EXISTS_BUT_NO_FINAL_MATCH"
            else:
                reason_source = "FINAL_EXISTS_BUT_NO_OUT_QUEUE"

                print(
                    f"FINAL EXISTS BUT NO OUT QUEUE -> retry failed "
                    f"ticket_id={ticket.id}, "
                    f"ticket_number={ticket.ticket_number}"
                )

                details_text = (
                    f"ticket_number={ticket.ticket_number}, "
                    f"type={ticket.type}, "
                    f"current_ticket_status={ticket.status}, "
                    f"truck_regnumber={ticket.truck_regnumber}, "
                    f"timestamp_in={ticket.timestamp_in}, "
                    f"first_pos_mcode={ticket.first_pos_mcode}, "
                    f"first_pos_supplier_refno={ticket.first_pos_supplier_refno}, "
                    f"position_count={ticket.position_count}, "
                    f"reason_source={reason_source}"
                )

                active_fingerprints.add(
                    build_manual_entry_fingerprint(
                        ticket.ticket_number,
                        ADMIN_REASON_FINAL_RETRY_FAILED,
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
                    reason=ADMIN_REASON_FINAL_RETRY_FAILED,
                    details=details_text,
                    notification_type="ADMIN",
                    now=now,
                )

                if created:
                    inserted += 1
                else:
                    updated += 1

                continue

            details_text = (
                f"ticket_number={ticket.ticket_number}, "
                f"type={ticket.type}, "
                f"current_ticket_status={ticket.status}, "
                f"truck_regnumber={ticket.truck_regnumber}, "
                f"timestamp_in={ticket.timestamp_in}, "
                f"first_pos_mcode={ticket.first_pos_mcode}, "
                f"first_pos_supplier_refno={ticket.first_pos_supplier_refno}, "
                f"position_count={ticket.position_count}, "
                f"reason_source={reason_source}"
            )

            active_fingerprints.add(
                build_manual_entry_fingerprint(
                    ticket.ticket_number,
                    reason_text,
                    details_text,
                )
            )

            print(
                f"MANUAL CANDIDATE ticket_id={ticket.id}, "
                f"ticket_number={ticket.ticket_number}, "
                f"reason={reason_text}"
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


        session.commit()

    print(f"Dodano manual: {inserted}")
    print(f"Zaktualizowano manual: {updated}")
    print(f"Oznaczono MANUAL: {marked_manual}")
    print(f"Pominięto - ma OUT: {skipped_pz}")
    print(f"Pominięto - ma manual: {skipped_manual}")
    print("KONIEC validate_type1_active_without_output_to_manual")

