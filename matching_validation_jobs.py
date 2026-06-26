"""Compatibility facade for job functions split into focused modules."""

from validation_pipeline_safety_jobs import (
    validate_type1_active_without_output_to_manual,
)
from validation_header_position_jobs import (
    validate_header_without_position_match,
    validate_missing_header_match,
    validate_missing_supplier_refno_position_matches,
)
from validation_final_consistency_jobs import (
    validate_position_count_erp_vs_external_translated,
    validate_erp_duplicate_product_per_supplier_ref,
)

__all__ = [
    "validate_type1_active_without_output_to_manual",
    "validate_header_without_position_match",
    "validate_missing_header_match",
    "validate_missing_supplier_refno_position_matches",
    "validate_position_count_erp_vs_external_translated",
    "validate_erp_duplicate_product_per_supplier_ref",
]
