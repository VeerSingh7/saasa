"""Convert collected inspection data into a YOLO-format training dataset.

This is a convenience wrapper around app.data_collection.exporter.DatasetExporter.
Run it on the central training machine after copying the data/ directory from the edge.

Usage:
    python training/prepare_dataset.py \
        --collected data/collected \
        --out /tmp/wire_dataset \
        [--split 0.8] [--seed 42]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_collection.exporter import DatasetExporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare YOLO dataset from collected data")
    parser.add_argument("--collected", default="data/collected",
                        help="Root of the collected data directory")
    parser.add_argument("--out", required=True, help="Output dataset directory")
    parser.add_argument("--split", type=float, default=0.8,
                        help="Train fraction (0–1); remainder → val")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    exporter = DatasetExporter(args.collected)
    yaml_path = exporter.export(args.out, train_split=args.split, seed=args.seed)
    print(f"\nDataset ready: {yaml_path}")
    print(f"Use '--data {yaml_path}' with training/train_detector.py")
    print(f"Use '--data {Path(args.out) / 'crops'}' with training/train_classifier.py")


if __name__ == "__main__":
    main()
