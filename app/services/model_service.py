"""Lazy-loading model service.

Loads the YOLO detector and wire classifier once and caches them.
Reads paths and versions from app/config/model_config.yaml.
Safe to call from multiple threads — loading is guarded by a lock.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.utils.config_loader import load as load_cfg

log = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Raised when a required model file cannot be loaded."""


class ModelService:
    """Owns the detector and classifier; defers loading to first use.

    App startup never crashes when model files are absent — the error
    surfaces only when /api/inspect is first called.
    """

    def __init__(self, models_dir: str | Path, backend: str = "onnx") -> None:
        self._models_dir = Path(models_dir)
        self._backend = backend
        self._lock = threading.Lock()
        self._pipeline = None

    def get_pipeline(self):
        """Return the loaded InferencePipeline, loading on first call.

        Raises:
            ModelLoadError if either model file is missing or fails to load.
        """
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                self._pipeline = self._load()
        return self._pipeline

    @property
    def is_ready(self) -> bool:
        try:
            self.get_pipeline()
            return True
        except ModelLoadError:
            return False

    @property
    def detector_version(self) -> str:
        cfg = load_cfg("model_config")
        return cfg.get("detector", {}).get("model_version", "unknown")

    @property
    def classifier_version(self) -> str:
        cfg = load_cfg("model_config")
        return cfg.get("classifier", {}).get("model_version", "unknown")

    def _load(self):
        from app.ai.detector.yolo import WireDetector
        from app.ai.classifier.classifier import WireClassifier
        from app.ai.inference_pipeline import InferencePipeline

        cfg = load_cfg("model_config")
        det_cfg = cfg.get("detector", {})
        cls_cfg = cfg.get("classifier", {})
        wf_cfg = load_cfg("workflow_config")

        det_path = self._models_dir / det_cfg.get("model_file", "wire_yolo.onnx")
        cls_path = self._models_dir / cls_cfg.get("model_file", "wire_cls.onnx")

        if not det_path.exists():
            raise ModelLoadError(
                f"Detector model not found: {det_path}. "
                "Export your YOLO model to ONNX and place it in the models/ directory."
            )
        if not cls_path.exists():
            raise ModelLoadError(
                f"Classifier model not found: {cls_path}. "
                "Export your classifier to ONNX and place it in the models/ directory."
            )

        num_wires = det_cfg.get("num_wires", wf_cfg.get("num_wires", 7))
        detector = WireDetector(
            model_path=det_path,
            backend=self._backend,
            input_size=tuple(det_cfg.get("input_size", [640, 640])),
            confidence_threshold=det_cfg.get("confidence_threshold", 0.4),
            iou_threshold=det_cfg.get("iou_threshold", 0.45),
            num_wires=num_wires,
            sort_by=det_cfg.get("sort_by", "top_to_bottom"),
        )
        classifier = WireClassifier(
            model_path=cls_path,
            backend=self._backend,
            input_size=tuple(cls_cfg.get("input_size", [224, 224])),
            classes=cls_cfg.get("classes", ["ok", "fail"]),
            confidence_threshold=cls_cfg.get("confidence_threshold", 0.5),
        )

        log.info("Models loaded — detector=%s  classifier=%s  backend=%s",
                 det_path.name, cls_path.name, self._backend)
        return InferencePipeline(detector, classifier, num_wires=num_wires)
