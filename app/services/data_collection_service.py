"""Thin facade over DataCollector for use from routes.

Routes call patch_final_result() after manual overrides are saved
so that metadata.json on disk gets the human-verified label.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class DataCollectionService:
    """Delegates to the DataCollector held in app.extensions."""

    def __init__(self, collector) -> None:
        self._collector = collector

    def record_final_result(
        self,
        inspection_id: int,
        final_result: int,
        manual_overrides: dict | None = None,
    ) -> None:
        """Patch the on-disk metadata with the finalized label."""
        if self._collector is None:
            return
        try:
            self._collector.patch_final_result(inspection_id, final_result, manual_overrides)
        except Exception:
            log.exception("Failed to patch final result for inspection %s", inspection_id)
