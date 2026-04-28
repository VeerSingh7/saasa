"""Async data collector for inspection samples.

DataCollector owns a background writer thread and a bounded queue.
Calling enqueue() is non-blocking — samples are persisted asynchronously
so inference latency is not affected.

Directory layout written to storage:
    <YYYY-MM-DD>/<inspection_id>/
        frame.jpg           — full camera frame JPEG
        wire_1.jpg … wire_7.jpg  — per-wire crops
        metadata.json       — bbox, ai_result, confidence, final_result, model versions
"""
from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.data_collection.storage import FilesystemStorage

log = logging.getLogger(__name__)


@dataclass
class CollectionSample:
    """Everything needed to persist one inspection sample."""
    inspection_id: int
    barcode: str
    frame_jpeg: bytes
    wire_results: list[dict]           # [{wire_no, ai_result, confidence, bbox}, ...]
    detector_version: str = "unknown"
    classifier_version: str = "unknown"
    # Populated after /api/save_manual_results finalizes the inspection
    final_result: int | None = None
    manual_overrides: dict = field(default_factory=dict)  # {wire_no: manual_result}
    wire_crops: dict[int, bytes] = field(default_factory=dict)  # wire_no → JPEG bytes


class DataCollector:
    """Background-thread collector.

    enqueue() never blocks the calling thread; if the queue is full the
    sample is dropped with a warning (better to lose a sample than stall
    the inspection workflow).
    """

    def __init__(
        self,
        storage: "FilesystemStorage",
        mode: str = "all",
        low_conf_threshold: float = 0.7,
        max_queue: int = 256,
        retention_days: int = 30,
    ) -> None:
        self._storage = storage
        self._mode = mode
        self._low_conf_threshold = low_conf_threshold
        self._queue: queue.Queue[CollectionSample | None] = queue.Queue(maxsize=max_queue)
        self._thread = threading.Thread(target=self._worker, daemon=True, name="data-collector")
        self._thread.start()

        if retention_days > 0:
            self._cleanup_old(retention_days)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, sample: CollectionSample) -> None:
        """Enqueue a sample for async disk write.  Never blocks."""
        if not self._should_collect(sample):
            return
        try:
            self._queue.put_nowait(sample)
        except queue.Full:
            log.warning("Data collection queue full — dropping sample for inspection %s",
                        sample.inspection_id)

    def patch_final_result(self, inspection_id: int, final_result: int,
                           manual_overrides: dict | None = None) -> None:
        """Update the final_result in an already-written metadata.json.

        Called after /api/save_manual_results so training labels reflect
        the human-verified outcome, not just the raw AI prediction.
        """
        today = date.today().isoformat()
        meta_path = f"{today}/{inspection_id}/metadata.json"
        if not self._storage.exists(meta_path):
            log.debug("No collected metadata for inspection %s — skipping patch", inspection_id)
            return
        meta = self._storage.read_json(meta_path)
        meta["final_result"] = final_result
        if manual_overrides:
            meta["manual_overrides"] = manual_overrides
        self._storage.write_json(meta_path, meta)

    def stop(self) -> None:
        """Graceful shutdown: drain queue then stop worker."""
        self._queue.put(None)  # sentinel
        self._thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        while True:
            sample = self._queue.get()
            if sample is None:
                break
            try:
                self._write(sample)
            except Exception:
                log.exception("Failed to persist collection sample %s", sample.inspection_id)
            finally:
                self._queue.task_done()

    def _write(self, sample: CollectionSample) -> None:
        today = date.today().isoformat()
        base = f"{today}/{sample.inspection_id}"

        # Full frame
        self._storage.write_bytes(f"{base}/frame.jpg", sample.frame_jpeg)

        # Per-wire crops (if provided by InspectionService)
        for wr in sample.wire_results:
            wn = wr["wire_no"]
            if wn in sample.wire_crops:
                self._storage.write_bytes(f"{base}/wire_{wn}.jpg", sample.wire_crops[wn])

        # Metadata
        meta = {
            "inspection_id": sample.inspection_id,
            "barcode": sample.barcode,
            "timestamp": datetime.utcnow().isoformat(),
            "detector_version": sample.detector_version,
            "classifier_version": sample.classifier_version,
            "final_result": sample.final_result,
            "manual_overrides": sample.manual_overrides,
            "wires": sample.wire_results,
        }
        self._storage.write_json(f"{base}/metadata.json", meta)
        log.debug("Collected sample for inspection %s → %s", sample.inspection_id, base)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _should_collect(self, sample: CollectionSample) -> bool:
        if self._mode == "all":
            return True
        if self._mode == "manual_override":
            return bool(sample.manual_overrides)
        if self._mode == "low_confidence":
            return any(
                wr.get("confidence", 1.0) < self._low_conf_threshold
                for wr in sample.wire_results
            )
        return True

    # ------------------------------------------------------------------
    # Retention cleanup
    # ------------------------------------------------------------------

    def _cleanup_old(self, retention_days: int) -> None:
        try:
            cutoff = date.today() - timedelta(days=retention_days)
            # storage root is a FilesystemStorage — iterate date directories
            root: Path = self._storage.root  # type: ignore[attr-defined]
            if not root.exists():
                return
            for d in root.iterdir():
                if not d.is_dir():
                    continue
                try:
                    folder_date = date.fromisoformat(d.name)
                except ValueError:
                    continue
                if folder_date < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
                    log.info("Removed old collected data folder: %s", d)
        except Exception:
            log.exception("Error during data retention cleanup")
