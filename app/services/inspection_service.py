"""End-to-end inspection workflow service.

Ties together: camera frame acquisition → inference pipeline → DB persistence
→ data collection sample enqueue.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import cv2
import numpy as np

from app.db import database as db
from app.utils.config_loader import load as load_cfg

log = logging.getLogger(__name__)


class InspectionError(Exception):
    """Raised when an inspection cannot proceed (e.g., no model loaded)."""


class InspectionService:
    """Runs a full wire inspection given a barcode and an image source.

    Designed to be called from the /api/inspect route.
    """

    def __init__(self, model_service, data_collector=None) -> None:
        self._model_service = model_service
        self._data_collector = data_collector

    def run(
        self,
        inspection_id: int,
        frame_bgr: np.ndarray | None,
        barcode: str = "",
    ) -> dict:
        """Run inference and persist results.

        Args:
            inspection_id: Existing inspection row to write wire results into.
            frame_bgr:     BGR image from the camera (or None if camera unavailable).
            barcode:       Barcode string (used for data collection metadata).

        Returns:
            dict with keys: status, detections, failed_wires, annotated_image

        Raises:
            InspectionError if models are not loaded or no frame is available.
        """
        try:
            pipeline = self._model_service.get_pipeline()
        except Exception as exc:
            raise InspectionError(str(exc)) from exc

        if frame_bgr is None:
            raise InspectionError("No camera frame available. Is the camera connected?")

        wire_results = pipeline.run(frame_bgr)

        # Persist per-wire AI results to DB
        crop_paths: dict[int, str] = {}
        for wr in wire_results:
            image_path = None
            if wr.crop_bytes:
                image_path = self._save_crop(inspection_id, wr.wire_no, wr.crop_bytes)
                crop_paths[wr.wire_no] = image_path
            db.insert_wire_ai_result(
                inspection_id, wr.wire_no, wr.ai_result,
                confidence=round(wr.confidence, 4),
                image_path=image_path,
            )

        # Update inspection row with model versions
        self._update_model_versions(inspection_id)

        # Enqueue data collection sample (non-blocking)
        if self._data_collector is not None:
            self._enqueue_sample(inspection_id, barcode, frame_bgr, wire_results)

        # Build response (same JSON shape as the old random stub)
        failed_wires = [{"wire": wr.wire_no} for wr in wire_results if wr.ai_result == 0]
        detections = [
            {
                "wire_id": wr.wire_no,
                "color": "black",
                "ai_result": wr.ai_result,
                "confidence": round(wr.confidence, 4),
                "bbox": list(wr.bbox),
            }
            for wr in wire_results
        ]

        return {
            "status": "PASS" if not failed_wires else "FAIL",
            "detections": detections,
            "failed_wires": failed_wires,
            "annotated_image": "/camera/snapshot",
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _save_crop(self, inspection_id: int, wire_no: int, jpeg_bytes: bytes) -> str:
        cfg = load_cfg("app_config", defaults={"data_dir": "data"})
        data_dir = Path(cfg["data_dir"])
        crops_dir = data_dir / "crops" / str(inspection_id)
        crops_dir.mkdir(parents=True, exist_ok=True)
        path = crops_dir / f"wire_{wire_no}.jpg"
        path.write_bytes(jpeg_bytes)
        return str(path)

    def _update_model_versions(self, inspection_id: int) -> None:
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE inspections SET yolo_model_version=?, classifier_model_version=? WHERE id=?",
                (self._model_service.detector_version,
                 self._model_service.classifier_version,
                 inspection_id),
            )
            conn.commit()
            conn.close()
        except Exception:
            log.exception("Failed to update model version on inspection %s", inspection_id)

    def _enqueue_sample(self, inspection_id, barcode, frame_bgr, wire_results) -> None:
        from app.data_collection.collector import CollectionSample
        try:
            _, jpeg_bytes = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            sample = CollectionSample(
                inspection_id=inspection_id,
                barcode=barcode,
                frame_jpeg=jpeg_bytes.tobytes(),
                wire_results=[
                    {
                        "wire_no": wr.wire_no,
                        "ai_result": wr.ai_result,
                        "confidence": round(wr.confidence, 4),
                        "bbox": list(wr.bbox),
                    }
                    for wr in wire_results
                ],
                detector_version=self._model_service.detector_version,
                classifier_version=self._model_service.classifier_version,
            )
            self._data_collector.enqueue(sample)
        except Exception:
            log.exception("Failed to enqueue data collection sample for inspection %s",
                          inspection_id)
