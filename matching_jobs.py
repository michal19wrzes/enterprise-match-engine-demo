"""Compatibility facade for job functions split into focused modules."""

from matching_internal_jobs import (
    build_internal_sales_matches,
)
from matching_transport_jobs import (
    build_transport_header_matches,
    build_transport_position_matches,
    build_transport_position_best_matches,
)
from matching_final_jobs import (
    build_final_position_matches,
)

__all__ = [
    "build_internal_sales_matches",
    "build_transport_header_matches",
    "build_transport_position_matches",
    "build_transport_position_best_matches",
    "build_final_position_matches",
]
