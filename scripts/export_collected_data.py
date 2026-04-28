"""CLI script to export collected inspection data to a YOLO-format dataset.

Usage:
    python scripts/export_collected_data.py --out /tmp/wire_ds [--split 0.8]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.config_loader import load as load_cfg
from app.data_collection.exporter import DatasetExporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Export collected data to YOLO dataset")
    parser.add_argument("--out", required=True, help="Output directory for the dataset")
    parser.add_argument("--split", type=float, default=0.8, help="Train fraction (default 0.8)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--collected", default=None,
                        help="Override storage_root from data_collection_config.yaml")
    args = parser.parse_args()

    dc_cfg = load_cfg("data_collection_config", defaults={"storage_root": "data/collected"})
    storage_root = args.collected or dc_cfg.get("storage_root", "data/collected")

    exporter = DatasetExporter(storage_root)
    yaml_path = exporter.export(args.out, train_split=args.split, seed=args.seed)

    print(f"\nDataset written to: {args.out}")
    print(f"dataset.yaml: {yaml_path}")
    print(f"\nNext steps:")
    print(f"  Train detector:    python training/train_detector.py --data {yaml_path}")
    print(f"  Train classifier:  python training/train_classifier.py --data {Path(args.out) / 'crops'}")


if __name__ == "__main__":
    main()
