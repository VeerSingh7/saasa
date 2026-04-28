"""End-to-end wire inspection inference pipeline.

Frame (BGR) → YOLO detects 7 wire bboxes → crop each → Classifier → list[WireResult]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from app.ai.detector.yolo import WireDetector
    from app.ai.classifier.classifier import WireClassifier

log = logging.getLogger(__name__)


@dataclass
class WireResult:
    """Inference result for a single wire."""
    wire_no: int                       # 1-indexed
    ai_result: int                     # 1=PASS, 0=FAIL
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, w, h in original frame pixels
    crop_bytes: bytes = field(repr=False, default=b"")  # JPEG-encoded wire crop


class InferencePipeline:
    """Orchestrates detector + classifier for a full frame.

    Usage:
        pipeline = InferencePipeline(detector, classifier, num_wires=7)
        results = pipeline.run(frame_bgr)
    """

    def __init__(
        self,
        detector: "WireDetector",
        classifier: "WireClassifier",
        num_wires: int = 7,
    ) -> None:
        self._detector = detector
        self._classifier = classifier
        self._num_wires = num_wires

    def run(self, frame_bgr: np.ndarray) -> list[WireResult]:
        """Run the full inspection pipeline on a BGR frame.

        Returns a list of WireResult of length num_wires.  If fewer than
        num_wires are detected, the missing wires are filled as FAIL with
        confidence 0.0 (conservative default — no wire found = problem).
        """
        detections = self._detector.detect(frame_bgr)

        if len(detections) < self._num_wires:
            log.warning("Detected %d wires, expected %d; missing wires treated as FAIL",
                        len(detections), self._num_wires)

        results: list[WireResult] = []

        for i in range(self._num_wires):
            wire_no = i + 1

            if i >= len(detections):
                # Wire not detected → conservative FAIL
                results.append(WireResult(
                    wire_no=wire_no,
                    ai_result=0,
                    confidence=0.0,
                    bbox=(0.0, 0.0, 0.0, 0.0),
                    crop_bytes=b"",
                ))
                continue

            det = detections[i]
            crop = self._extract_crop(frame_bgr, det.bbox)
            label, conf = self._classifier.classify(crop)
            ai_result = 1 if label == "ok" else 0

            results.append(WireResult(
                wire_no=wire_no,
                ai_result=ai_result,
                confidence=conf,
                bbox=det.bbox,
                crop_bytes=self._encode_jpeg(crop),
            ))

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_crop(
        self, frame_bgr: np.ndarray, bbox: tuple[float, float, float, float]
    ) -> np.ndarray:
        x, y, w, h = (int(v) for v in bbox)
        fh, fw = frame_bgr.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(fw, x + w)
        y2 = min(fh, y + h)
        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            crop = np.zeros((64, 64, 3), dtype=np.uint8)
        return crop

    @staticmethod
    def _encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else b""
