"""YOLOv8 wire detector — frame in, ROIs out."""

from pathlib import Path
from datetime import date
from ultralytics import YOLO
import yaml
import numpy as np
import logging

logger = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[3]


def _load_cfg():
    p = _ROOT / "app" / "config" / "model_config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


def _resolve_variant(cfg: dict) -> str:
    expiry = cfg.get("expiry")
    if expiry and date.today() >= date.fromisoformat(str(expiry)):
        return cfg.get("fallback", "lite")
    return cfg.get("active", "full")


class YOLODetector:
    def __init__(self, model_path=None, device=None):
        cfg = _load_cfg()
        yolo_cfg = cfg.get("yolo", {})
        variant = _resolve_variant(cfg)

        if model_path is None:
            model_path = (
                _ROOT / "models" / "yolo" / variant
                / yolo_cfg.get("weights", "model_yolo.pt")
            )

        self.conf = yolo_cfg.get("conf", 0.25)
        self.iou = yolo_cfg.get("iou", 0.45)
        self.img_size = yolo_cfg.get("img_size", 640)
        self.device = device or yolo_cfg.get("device", "cpu")

        logger.info("Loading YOLO: %s", model_path)
        self.model = YOLO(str(model_path))
        self.model.to(self.device)

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection on a BGR frame.

        Returns
        -------
        list of dicts, each with:
            bbox  : [x1, y1, x2, y2]  (int, pixel coords)
            conf  : float
            cls   : int
            label : str
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.img_size,
            device=self.device,
            verbose=False,
        )

        detections = []
        boxes = results[0].boxes
        if boxes is not None and len(boxes):
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int).tolist()
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": round(float(box.conf[0]), 4),
                    "cls": int(box.cls[0]),
                    "label": self.model.names[int(box.cls[0])],
                })

        logger.info("Detected %d object(s)", len(detections))
        return detections
