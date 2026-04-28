"""Evaluate trained models against a held-out validation set.

Detector: reports mAP50, mAP50-95 using ultralytics validation.
Classifier: reports accuracy, precision, recall, F1 per class.

Usage:
    # Evaluate detector
    python training/evaluate.py detector \
        --weights runs/detect/wire_detector/weights/best.pt \
        --data /path/to/dataset.yaml

    # Evaluate classifier
    python training/evaluate.py classifier \
        --weights runs/classify/wire_classifier/best.pth \
        --data /path/to/crops
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import torch
except ImportError:
    print("Install training deps: pip install -r requirements-train.txt")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def eval_detector(weights: str, data: str) -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics required")
        sys.exit(1)

    model = YOLO(weights)
    metrics = model.val(data=data)
    print(f"\nDetector results:")
    print(f"  mAP50:    {metrics.box.map50:.4f}")
    print(f"  mAP50-95: {metrics.box.map:.4f}")


def eval_classifier(weights: str, data: str,
                    backbone: str = "mobilenet_v3_small",
                    input_size: int = 224,
                    batch: int = 32) -> None:
    from torch.utils.data import DataLoader
    from training.data.dataset import WireCropDataset, CLASSES
    from training.train_classifier import _build_model

    num_classes = len(CLASSES)
    model = _build_model(backbone, num_classes, pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()

    val_ds = WireCropDataset(data, "val", input_size)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False)

    tp = [0] * num_classes
    fp = [0] * num_classes
    fn = [0] * num_classes
    total = correct = 0

    with torch.no_grad():
        for imgs, labels in val_dl:
            preds = model(imgs).argmax(dim=1)
            for p, l in zip(preds.tolist(), labels.tolist()):
                total += 1
                if p == l:
                    correct += 1
                    tp[l] += 1
                else:
                    fp[p] += 1
                    fn[l] += 1

    print(f"\nClassifier results on {total} samples:")
    print(f"  Accuracy: {correct/total:.4f}")
    for i, cls in enumerate(CLASSES):
        prec = tp[i] / (tp[i] + fp[i]) if (tp[i] + fp[i]) > 0 else 0.0
        rec = tp[i] / (tp[i] + fn[i]) if (tp[i] + fn[i]) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        print(f"  {cls:6s}: precision={prec:.4f}  recall={rec:.4f}  f1={f1:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate wire inspection models")
    sub = parser.add_subparsers(dest="mode", required=True)

    det = sub.add_parser("detector")
    det.add_argument("--weights", required=True)
    det.add_argument("--data", required=True, help="dataset.yaml path")

    cls_ = sub.add_parser("classifier")
    cls_.add_argument("--weights", required=True)
    cls_.add_argument("--data", required=True, help="crops/ directory path")
    cls_.add_argument("--backbone", default="mobilenet_v3_small")
    cls_.add_argument("--input-size", type=int, default=224)
    cls_.add_argument("--batch", type=int, default=32)

    args = parser.parse_args()
    if args.mode == "detector":
        eval_detector(args.weights, args.data)
    else:
        eval_classifier(args.weights, args.data,
                        backbone=args.backbone,
                        input_size=args.input_size, batch=args.batch)


if __name__ == "__main__":
    main()
