"""YOLO-based wire detector.

Wraps an ONNX (or PyTorch) YOLO model and returns bounding-box detections
sorted by vertical position (top → bottom) so wire_no maps 1–7 predictably.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.ai.runtime import build_runtime

log = logging.getLogger(__name__)


@dataclass
class Detection:
    """A single wire bounding-box detection."""
    class_name: str
    confidence: float
    # absolute pixel coords (x, y, w, h) in the original frame
    bbox: tuple[float, float, float, float]


class WireDetector:
    """Detects wire ROIs in a BGR frame using a YOLO ONNX model.

    Returns detections sorted by `sort_by` so index 0 = wire_no 1, etc.
    """

    def __init__(
        self,
        model_path: str | Path,
        backend: str = "onnx",
        input_size: tuple[int, int] = (640, 640),
        confidence_threshold: float = 0.4,
        iou_threshold: float = 0.45,
        num_wires: int = 7,
        sort_by: str = "top_to_bottom",
    ) -> None:
        self._runtime = build_runtime(model_path, backend)
        self._input_w, self._input_h = input_size
        self._conf_thresh = confidence_threshold
        self._iou_thresh = iou_threshold
        self._num_wires = num_wires
        self._sort_by = sort_by

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        """Run detection on a BGR frame; return sorted wire detections."""
        img, scale_x, scale_y = self._preprocess(frame_bgr)
        outputs = self._runtime.run(img)
        detections = self._postprocess(outputs, scale_x, scale_y,
                                       frame_bgr.shape[1], frame_bgr.shape[0])
        return self._sort(detections)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _preprocess(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, float, float]:
        h_orig, w_orig = frame_bgr.shape[:2]
        img = cv2.resize(frame_bgr, (self._input_w, self._input_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))   # HWC → CHW
        img = np.expand_dims(img, 0)          # add batch dim
        return img, w_orig / self._input_w, h_orig / self._input_h

    def _postprocess(
        self,
        outputs: list[np.ndarray],
        scale_x: float,
        scale_y: float,
        orig_w: int,
        orig_h: int,
    ) -> list[Detection]:
        """Decode YOLOv8 ONNX output → list[Detection].

        YOLOv8 export shape: [1, 4+nc, num_anchors] (transposed from anchor-first).
        """
        raw = outputs[0]
        if raw.ndim == 3 and raw.shape[1] < raw.shape[2]:
            raw = np.transpose(raw, (0, 2, 1))   # → (batch, anchors, 4+nc)

        preds = raw[0]
        detections: list[Detection] = []
        for row in preds:
            cx, cy, bw, bh = row[:4]
            scores = row[4:]
            cls_id = int(np.argmax(scores))
            conf = float(scores[cls_id])
            if conf < self._conf_thresh:
                continue
            x = max(0.0, (cx - bw / 2) * scale_x)
            y = max(0.0, (cy - bh / 2) * scale_y)
            w = max(1.0, min(bw * scale_x, orig_w - x))
            h = max(1.0, min(bh * scale_y, orig_h - y))
            detections.append(Detection(str(cls_id), conf, (x, y, w, h)))

        return self._nms(detections) if detections else []

    def _nms(self, detections: list[Detection]) -> list[Detection]:
        boxes = [[d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3]] for d in detections]
        scores = [d.confidence for d in detections]
        indices = cv2.dnn.NMSBoxes(boxes, scores, self._conf_thresh, self._iou_thresh)
        if len(indices) == 0:
            return []
        return [detections[i] for i in indices.flatten()]

    def _sort(self, detections: list[Detection]) -> list[Detection]:
        if self._sort_by == "top_to_bottom":
            return sorted(detections, key=lambda d: d.bbox[1])
        if self._sort_by == "left_to_right":
            return sorted(detections, key=lambda d: d.bbox[0])
        return detections
