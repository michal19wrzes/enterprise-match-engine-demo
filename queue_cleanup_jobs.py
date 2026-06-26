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

def delete_output_queue_for_manual_tickets():
    print("START delete_output_queue_for_manual_tickets")

    with SessionLocal() as session:
        now = datetime.utcnow()

        manual_ticket_ids = {
            row[0]
            for row in session.query(ToManualEntry.erp_weight_ticket_id)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.erp_weight_ticket_id.isnot(None),
            )
            .distinct()
            .all()
        }

        queues = session.query(OUTQueue).filter(
            OUTQueue.entry_status == "OPEN",
            OUTQueue.erp_weight_ticket_id.in_(manual_ticket_ids),
        ).all()

        resolved_queues = 0
        resolved_items = 0

        for queue in queues:
            queue.entry_status = "RESOLVED"
            queue.resolved_at = now
            queue.updated_at = now
            resolved_queues += 1

            items = session.query(OUTQueueItem).filter(
                OUTQueueItem.output_queue_id == queue.id,
                OUTQueueItem.entry_status == "OPEN",
            ).all()

            for item in items:
                item.entry_status = "RESOLVED"
                item.resolved_at = now
                item.updated_at = now
                resolved_items += 1

        session.commit()

    print(f"Zamknięto output_queue dla manuali: {resolved_queues}")
    print(f"Zamknięto output_queue_items dla manuali: {resolved_items}")
    print("KONIEC delete_output_queue_for_manual_tickets")


def delete_output_queue_for_removed_tickets():
    print("START delete_output_queue_for_removed_tickets")

    with SessionLocal() as session:
        removed_ticket_ids = [
            row[0]
            for row in session.query(ERPWeightTicket.id).filter(
                ERPWeightTicket.status == "REMOVED"
            ).all()
        ]

        if not removed_ticket_ids:
            print("Brak ticketów REMOVED do cleanupu output_queue")
            print("KONIEC delete_output_queue_for_removed_tickets")
            return

        queue_ids = [
            row[0]
            for row in session.query(OUTQueue.id).filter(
                OUTQueue.erp_weight_ticket_id.in_(removed_ticket_ids)
            ).all()
        ]

        deleted_items = 0
        deleted_queues = 0

        if queue_ids:
            deleted_items = session.query(OUTQueueItem).filter(
                OUTQueueItem.output_queue_id.in_(queue_ids)
            ).delete(synchronize_session=False)
            session.flush()

            deleted_queues = session.query(OUTQueue).filter(
                OUTQueue.id.in_(queue_ids)
            ).delete(synchronize_session=False)
            session.flush()

        session.commit()

    print(f"Usunięto output_queue_items dla REMOVED ticketów: {deleted_items}")
    print(f"Usunięto output_queue dla REMOVED ticketów: {deleted_queues}")
    print("KONIEC delete_output_queue_for_removed_tickets")


def delete_finished_output_queue():
    print("START delete_finished_output_queue")

    with SessionLocal() as session:
        queues = session.query(OUTQueue).filter(
            OUTQueue.status == "DONE",
            OUTQueue.entry_status == "OPEN",
        ).all()

        deleted_queues = 0
        deleted_items = 0
        skipped_no_items = 0
        skipped_not_all_done = 0

        for queue in queues:
            queue_items = session.query(OUTQueueItem).filter(
                OUTQueueItem.output_queue_id == queue.id,
            ).all()

            if not queue_items:
                skipped_no_items += 1
                continue

            if not all(item.status == "DONE" for item in queue_items):
                skipped_not_all_done += 1
                continue

            deleted_items += session.query(OUTQueueItem).filter(
                OUTQueueItem.output_queue_id == queue.id,
            ).delete(synchronize_session=False)

            session.delete(queue)
            deleted_queues += 1

        session.commit()

    print(f"Usunięto output_queue: {deleted_queues}")
    print(f"Usunięto output_queue_items: {deleted_items}")
    print(f"Pominięto bez itemów: {skipped_no_items}")
    print(f"Pominięto, bo nie wszystkie itemy DONE: {skipped_not_all_done}")
    print("KONIEC delete_finished_output_queue")


def delete_manual_entries_for_removed_tickets():
    print("START delete_manual_entries_for_removed_tickets")

    with SessionLocal() as session:
        removed_ticket_numbers = [
            row[0]
            for row in session.query(ERPWeightTicket.ticket_number).filter(
                ERPWeightTicket.status == "REMOVED"
            ).all()
        ]

        if not removed_ticket_numbers:
            print("Brak ticketów REMOVED do cleanupu manual entry")
            print("KONIEC delete_manual_entries_for_removed_tickets")
            return

        deleted_manual = session.query(ToManualEntry).filter(
            ToManualEntry.ticket_number.in_(removed_ticket_numbers)
        ).delete(synchronize_session=False)

        session.commit()

    print(f"Usunięto manual entry dla REMOVED ticketów: {deleted_manual}")
    print("KONIEC delete_manual_entries_for_removed_tickets")

