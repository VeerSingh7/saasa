"""Drop a new ONNX model into the models/ directory and update model_config.yaml.

Run this on the edge device after receiving a freshly trained ONNX export.

Usage:
    python scripts/update_model.py \
        --detector /path/to/wire_yolo.onnx \
        --classifier /path/to/wire_cls.onnx \
        [--detector-version 1.1.0] [--classifier-version 1.1.0]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml required: pip install pyyaml")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.config_loader import load as load_cfg

CONFIG_PATH = Path("app/config/model_config.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install new ONNX models on the edge device")
    parser.add_argument("--detector", help="Path to new detector ONNX file")
    parser.add_argument("--classifier", help="Path to new classifier ONNX file")
    parser.add_argument("--detector-version", default=None)
    parser.add_argument("--classifier-version", default=None)
    parser.add_argument("--models-dir", default="models")
    args = parser.parse_args()

    if not args.detector and not args.classifier:
        print("ERROR: Provide at least one of --detector or --classifier")
        sys.exit(1)

    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_cfg("model_config", defaults={})

    if args.detector:
        src = Path(args.detector)
        dst_name = cfg.get("detector", {}).get("model_file", "wire_yolo.onnx")
        dst = models_dir / dst_name
        shutil.copy2(src, dst)
        print(f"Detector installed: {dst}")
        if args.detector_version:
            if "detector" not in cfg:
                cfg["detector"] = {}
            cfg["detector"]["model_version"] = args.detector_version

    if args.classifier:
        src = Path(args.classifier)
        dst_name = cfg.get("classifier", {}).get("model_file", "wire_cls.onnx")
        dst = models_dir / dst_name
        shutil.copy2(src, dst)
        print(f"Classifier installed: {dst}")
        if args.classifier_version:
            if "classifier" not in cfg:
                cfg["classifier"] = {}
            cfg["classifier"]["model_version"] = args.classifier_version

    # Write updated config
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
    print(f"\nmodel_config.yaml updated.")
    print("Restart the Flask app to load the new model.")


if __name__ == "__main__":
    main()
