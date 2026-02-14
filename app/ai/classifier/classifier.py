"""ResNet wire-colour classifier — ROIs in, labels out."""

from pathlib import Path
from datetime import date
import yaml
import logging

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import models, transforms

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


_TRANSFORM = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])


class WireClassifier:
    def __init__(self, model_path=None, device=None):
        cfg = _load_cfg()
        cls_cfg = cfg.get("classifier", {})
        variant = _resolve_variant(cfg)

        if model_path is None:
            model_path = (
                _ROOT / "models" / "classifier" / variant
                / cls_cfg.get("weights", "model_cls.pth")
            )

        self.class_names = cls_cfg.get("class_names", [])
        num_classes = cls_cfg.get("num_classes", len(self.class_names))
        arch = cls_cfg.get("architecture", "resnet50")
        self.device = device or cls_cfg.get("device", "cpu")

        # Build model
        model_fn = getattr(models, arch)
        self.model = model_fn(weights=None)
        self.model.fc = torch.nn.Linear(self.model.fc.in_features, num_classes)

        # Load weights
        logger.info("Loading classifier: %s", model_path)
        state = torch.load(str(model_path), map_location=self.device,
                           weights_only=False)
        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]
        self.model.load_state_dict(state, strict=False)
        self.model.to(self.device)
        self.model.eval()

    def classify(self, rois: list[np.ndarray]) -> list[str]:
        """Classify a list of BGR crop ROIs.

        Parameters
        ----------
        rois : list of numpy arrays, each a BGR cropped image.

        Returns
        -------
        list of str — predicted colour label for each ROI,
                      in the same order as the input.
        """
        labels = []
        for crop in rois:
            if crop is None or crop.size == 0:
                labels.append("unknown")
                continue

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor = _TRANSFORM(rgb).unsqueeze(0).to(self.device)

            with torch.no_grad():
                probs = F.softmax(self.model(tensor), dim=1)[0]

            idx = int(probs.argmax())
            label = self.class_names[idx] if idx < len(self.class_names) else str(idx)
            labels.append(label)

        logger.info("Classified %d ROI(s)", len(labels))
        return labels
