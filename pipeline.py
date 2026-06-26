"""Top-level orchestration for the demo matching pipeline."""

from database import init_db
from jobs import (
    build_final_position_matches,
    build_internal_sales_matches,
    build_output_queue,
    build_output_queue_type2,
    build_transport_header_matches,
    build_transport_position_best_matches,
    build_transport_position_matches,
    delete_finished_output_queue,
    delete_manual_entries_for_removed_tickets,
    delete_output_queue_for_manual_tickets,
    delete_output_queue_for_removed_tickets,
    rebuild_external_item_aggregates,
    rebuild_external_item_translated,
    send_manual_entry_email,
    send_program_started_email,
    sync_article_no_mapper,
    sync_external_documents,
    sync_internal_product_sales_cache,
    sync_oracle_candidate_positions,
    sync_oracle_candidates,
    sync_products,
    sync_region_mapper,
    sync_ticket_status_from_manual_entries,
    sync_to_manual_entry,
    sync_type2_invalid_supplier_refno_manual_entries,
    validate_erp_duplicate_product_per_supplier_ref,
    validate_header_without_position_match,
    validate_missing_article_no_mapping,
    validate_missing_header_match,
    validate_missing_region_mapping,
    validate_missing_supplier_refno_position_matches,
    validate_position_count_erp_vs_external_translated,
    validate_source_order_product_type_match,
    validate_type1_active_without_output_to_manual,
)


def refresh_reference_data() -> None:
    sync_region_mapper()
    sync_products()
    sync_article_no_mapper()


def ingest_source_data() -> None:
    sync_oracle_candidates()
    sync_oracle_candidate_positions()
    sync_external_documents()
    rebuild_external_item_aggregates()


def validate_source_inputs() -> None:
    validate_missing_article_no_mapping()
    validate_missing_region_mapping()
    sync_ticket_status_from_manual_entries()


def process_internal_sales() -> None:
    rebuild_external_item_translated()
    sync_internal_product_sales_cache()
    build_internal_sales_matches()
    sync_type2_invalid_supplier_refno_manual_entries()
    sync_to_manual_entry()
    validate_erp_duplicate_product_per_supplier_ref()
    sync_ticket_status_from_manual_entries()


def build_matches() -> None:
    build_transport_header_matches()
    build_transport_position_matches()
    build_transport_position_best_matches()
    build_final_position_matches()


def validate_matches() -> None:
    validate_source_order_product_type_match()
    validate_missing_header_match()
    validate_header_without_position_match()
    validate_missing_supplier_refno_position_matches()
    validate_position_count_erp_vs_external_translated()
    sync_ticket_status_from_manual_entries()


def build_and_clean_output_queue() -> None:
    build_output_queue()
    build_output_queue_type2()
    delete_output_queue_for_manual_tickets()
    delete_finished_output_queue()
    delete_output_queue_for_removed_tickets()
    delete_manual_entries_for_removed_tickets()
    sync_ticket_status_from_manual_entries()


def run_safety_net() -> None:
    validate_type1_active_without_output_to_manual()
    sync_ticket_status_from_manual_entries()
    build_output_queue()
    validate_type1_active_without_output_to_manual()
    delete_output_queue_for_manual_tickets()


def send_notifications() -> None:
    try:
        send_manual_entry_email()
    except Exception as exc:
        print(f"Could not send manual-review email: {exc}")

    try:
        send_program_started_email()
    except Exception as exc:
        print(f"Could not send startup email: {exc}")


def run_pipeline() -> None:
    init_db()
    refresh_reference_data()
    ingest_source_data()
    validate_source_inputs()
    process_internal_sales()
    build_matches()
    validate_matches()
    build_and_clean_output_queue()
    run_safety_net()
    send_notifications()
