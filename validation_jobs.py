"""Compatibility facade for validation jobs."""

from matching_validation_jobs import (
    validate_erp_duplicate_product_per_supplier_ref,
    validate_header_without_position_match,
    validate_missing_header_match,
    validate_missing_supplier_refno_position_matches,
    validate_position_count_erp_vs_external_translated,
    validate_type1_active_without_output_to_manual,
)
from source_validation_jobs import (
    validate_missing_article_no_mapping,
    validate_missing_region_mapping,
    validate_source_order_product_type_match,
)

__all__ = [
    "validate_erp_duplicate_product_per_supplier_ref",
    "validate_header_without_position_match",
    "validate_missing_header_match",
    "validate_missing_supplier_refno_position_matches",
    "validate_position_count_erp_vs_external_translated",
    "validate_type1_active_without_output_to_manual",
    "validate_missing_article_no_mapping",
    "validate_missing_region_mapping",
    "validate_source_order_product_type_match",
]
