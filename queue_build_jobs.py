"""Compatibility facade for output queue build jobs."""

from queue_type1_build_jobs import build_output_queue
from queue_type2_build_jobs import build_output_queue_type2

__all__ = ["build_output_queue", "build_output_queue_type2"]
