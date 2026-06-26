"""Public compatibility facade for pipeline job functions.

`app.py` and `scheduler.py` import from this module. Implementations live in
focused modules so the codebase stays reviewable.
"""

from external_sync_jobs import (
    rebuild_external_item_aggregates,
    rebuild_external_item_translated,
    sync_external_documents,
)
from jobs_common import (
    build_manual_entry_fingerprint,
    classify_tickets_by_supplier_ref,
    classify_type2_tickets,
    floor_2,
    get_manual_notification_type,
    is_type3_supplier_refno,
    mark_ticket_as_manual_by_id,
    resolve_missing_manual_entries,
    round_2,
    upsert_manual_entry,
)
from mapper_sync_jobs import sync_article_no_mapper, sync_products, sync_region_mapper
from matching_jobs import (
    build_final_position_matches,
    build_internal_sales_matches,
    build_transport_header_matches,
    build_transport_position_best_matches,
    build_transport_position_matches,
)
from matching_validation_jobs import (
    validate_erp_duplicate_product_per_supplier_ref,
    validate_header_without_position_match,
    validate_missing_header_match,
    validate_missing_supplier_refno_position_matches,
    validate_position_count_erp_vs_external_translated,
    validate_type1_active_without_output_to_manual,
)
from notification_jobs import (
    send_manual_entry_email,
    send_program_started_email,
)
from queue_jobs import (
    build_output_queue,
    build_output_queue_type2,
    delete_finished_output_queue,
    delete_manual_entries_for_removed_tickets,
    delete_output_queue_for_manual_tickets,
    delete_output_queue_for_removed_tickets,
)
from source_sync_jobs import (
    build_to_manual_entry,
    sync_internal_product_sales_cache,
    sync_oracle_candidate_positions,
    sync_oracle_candidates,
    sync_to_manual_entry,
    sync_type2_invalid_supplier_refno_manual_entries,
)
from source_validation_jobs import (
    validate_missing_article_no_mapping,
    validate_missing_region_mapping,
    validate_source_order_product_type_match,
)
from status_sync_jobs import sync_ticket_status_from_manual_entries, sync_ticket_status_from_outputs

__all__ = [
    "validate_source_order_product_type_match",
    "validate_missing_article_no_mapping",
    "validate_missing_region_mapping",
    "validate_type1_active_without_output_to_manual",
    "validate_header_without_position_match",
    "validate_missing_header_match",
    "validate_missing_supplier_refno_position_matches",
    "validate_position_count_erp_vs_external_translated",
    "validate_erp_duplicate_product_per_supplier_ref",
    "build_output_queue_type2",
    "build_output_queue",
    "delete_output_queue_for_manual_tickets",
    "delete_output_queue_for_removed_tickets",
    "delete_finished_output_queue",
    "delete_manual_entries_for_removed_tickets",
    "build_internal_sales_matches",
    "build_transport_position_best_matches",
    "build_transport_position_matches",
    "build_transport_header_matches",
    "build_final_position_matches",
    "sync_ticket_status_from_outputs",
    "sync_ticket_status_from_manual_entries",
    "sync_internal_product_sales_cache",
    "sync_type2_invalid_supplier_refno_manual_entries",
    "sync_article_no_mapper",
    "sync_region_mapper",
    "rebuild_external_item_aggregates",
    "sync_products",
    "sync_to_manual_entry",
    "sync_oracle_candidate_positions",
    "sync_external_documents",
    "sync_oracle_candidates",
    "rebuild_external_item_translated",
    "build_to_manual_entry",
    "send_program_started_email",
    "send_manual_entry_email",
    "is_type3_supplier_refno",
    "mark_ticket_as_manual_by_id",
    "round_2",
    "classify_type2_tickets",
    "build_manual_entry_fingerprint",
    "get_manual_notification_type",
    "upsert_manual_entry",
    "resolve_missing_manual_entries",
    "floor_2",
    "classify_tickets_by_supplier_ref",
]
