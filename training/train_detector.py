"""Train the YOLO wire detector using ultralytics.

Usage:
    python training/train_detector.py \
        --config training/config/detector_train.yaml \
        --data /path/to/exported/dataset.yaml \
        [--epochs 100] [--device cpu]

The best checkpoint is saved to runs/detect/wire_detector/weights/best.pt.
Export it for edge deployment with:
    python training/export.py --weights runs/detect/wire_detector/weights/best.pt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml required: pip install pyyaml")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    print("ultralytics required: pip install -r requirements-train.txt")
    sys.exit(1)


def _load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def train(args: argparse.Namespace) -> None:
    cfg = _load_config(args.config)

    # CLI args override config file
    if args.data:
        cfg["data"] = args.data
    if args.epochs:
        cfg["epochs"] = args.epochs
    if args.device:
        cfg["device"] = args.device

    if not cfg.get("data"):
        print("ERROR: --data is required (path to dataset.yaml)")
        sys.exit(1)

    model = YOLO(cfg.get("model", "yolov8n.pt"))
    model.train(
        data=cfg["data"],
        epochs=cfg.get("epochs", 100),
        batch=cfg.get("batch", 16),
        imgsz=cfg.get("imgsz", 640),
        device=cfg.get("device", "cpu"),
        workers=cfg.get("workers", 4),
        optimizer=cfg.get("optimizer", "AdamW"),
        lr0=cfg.get("lr0", 0.001),
        weight_decay=cfg.get("weight_decay", 0.0005),
        flipud=cfg.get("flipud", 0.0),
        fliplr=cfg.get("fliplr", 0.5),
        mosaic=cfg.get("mosaic", 0.5),
        project=cfg.get("project", "runs/detect"),
        name=cfg.get("name", "wire_detector"),
        save_period=cfg.get("save_period", 10),
        patience=cfg.get("patience", 20),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO wire detector")
    parser.add_argument("--config", default="training/config/detector_train.yaml")
    parser.add_argument("--data", help="Path to dataset.yaml")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--device")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
