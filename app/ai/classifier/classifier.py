"""Per-wire binary classifier.

Accepts a BGR image crop of a single wire ROI and returns (label, confidence).
Uses ONNX Runtime for edge inference; no PyTorch required on the device.
"""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.ai.runtime import build_runtime

log = logging.getLogger(__name__)


class WireClassifier:
    """Classify a single wire crop as 'ok' or 'fail'.

    Returns (label: str, confidence: float) where label is one of
    cfg.classes (default ["ok", "fail"]).
    """

    def __init__(
        self,
        model_path: str | Path,
        backend: str = "onnx",
        input_size: tuple[int, int] = (224, 224),
        classes: list[str] | None = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._runtime = build_runtime(model_path, backend)
        self._input_w, self._input_h = input_size
        self._classes = classes or ["ok", "fail"]
        self._conf_thresh = confidence_threshold

    def classify(self, crop_bgr: np.ndarray) -> tuple[str, float]:
        """Classify a wire crop.

        Returns:
            (label, confidence) – label is from self._classes.
            If confidence < threshold, returns ("fail", confidence) conservatively.
        """
        img = self._preprocess(crop_bgr)
        outputs = self._runtime.run(img)
        return self._postprocess(outputs)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _preprocess(self, crop_bgr: np.ndarray) -> np.ndarray:
        img = cv2.resize(crop_bgr, (self._input_w, self._input_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        # ImageNet mean/std normalisation (common for fine-tuned classifiers)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        img = np.transpose(img, (2, 0, 1))   # HWC → CHW
        return np.expand_dims(img, 0).astype(np.float32)

    def _postprocess(self, outputs: list[np.ndarray]) -> tuple[str, float]:
        logits = outputs[0][0]  # (num_classes,)

        # Softmax
        e = np.exp(logits - logits.max())
        probs = e / e.sum()

        cls_id = int(np.argmax(probs))
        confidence = float(probs[cls_id])
        label = self._classes[cls_id] if cls_id < len(self._classes) else "fail"

        # Conservative: if confidence is below threshold, call it fail
        if confidence < self._conf_thresh:
            label = "fail"
            confidence = float(probs[self._classes.index("fail")]
                               if "fail" in self._classes else 1 - probs[0])

        return label, confidence
