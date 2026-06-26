"""Compatibility facade for synchronization jobs."""

from external_sync_jobs import (
    rebuild_external_item_aggregates,
    rebuild_external_item_translated,
    sync_external_documents,
)
from mapper_sync_jobs import sync_article_no_mapper, sync_products, sync_region_mapper
from source_sync_jobs import (
    build_to_manual_entry,
    sync_internal_product_sales_cache,
    sync_oracle_candidate_positions,
    sync_oracle_candidates,
    sync_to_manual_entry,
    sync_type2_invalid_supplier_refno_manual_entries,
)
from status_sync_jobs import sync_ticket_status_from_manual_entries, sync_ticket_status_from_outputs

__all__ = [
    "rebuild_external_item_aggregates",
    "rebuild_external_item_translated",
    "sync_external_documents",
    "sync_article_no_mapper",
    "sync_products",
    "sync_region_mapper",
    "build_to_manual_entry",
    "sync_internal_product_sales_cache",
    "sync_oracle_candidate_positions",
    "sync_oracle_candidates",
    "sync_to_manual_entry",
    "sync_type2_invalid_supplier_refno_manual_entries",
    "sync_ticket_status_from_manual_entries",
    "sync_ticket_status_from_outputs",
]
