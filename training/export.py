"""Export trained PyTorch models to ONNX for edge deployment.

Supports:
  - YOLO detector (ultralytics checkpoint → ONNX via ultralytics export)
  - Binary classifier (torchvision checkpoint → ONNX via torch.onnx.export)

Optional INT8 quantization for smaller, faster ARM models.

Usage:
    # Export YOLO detector
    python training/export.py \
        --weights runs/detect/wire_detector/weights/best.pt \
        --out models/wire_yolo.onnx

    # Export classifier
    python training/export.py \
        --weights runs/classify/wire_classifier/best.pth \
        --model-type classifier \
        --out models/wire_cls.onnx \
        [--quantize]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import torch
    import yaml
except ImportError:
    print("Install training deps: pip install -r requirements-train.txt")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def export_detector(weights: str, out: str, imgsz: int = 640) -> None:
    """Export ultralytics YOLO checkpoint to ONNX."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics required: pip install ultralytics")
        sys.exit(1)

    model = YOLO(weights)
    # ultralytics export writes the ONNX next to the weights file
    model.export(format="onnx", imgsz=imgsz, simplify=True, opset=12)

    # Move to requested output path
    default_out = Path(weights).with_suffix(".onnx")
    if default_out.exists() and str(default_out) != out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        default_out.rename(out)

    print(f"Detector ONNX saved to {out}")


def export_classifier(
    weights: str,
    out: str,
    backbone: str = "mobilenet_v3_small",
    input_size: int = 224,
    num_classes: int = 2,
    quantize: bool = False,
) -> None:
    """Export torchvision classifier state-dict to ONNX."""
    from training.train_classifier import _build_model

    model = _build_model(backbone, num_classes, pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()

    if quantize:
        model = torch.quantization.quantize_dynamic(
            model, {torch.nn.Linear, torch.nn.Conv2d}, dtype=torch.qint8
        )

    dummy = torch.randn(1, 3, input_size, input_size)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model, dummy, str(out_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=12,
    )

    # Simplify graph for cleaner ARM execution
    try:
        import onnx
        from onnxsim import simplify as onnxsim

        m = onnx.load(str(out_path))
        m_sim, ok = onnxsim(m)
        if ok:
            onnx.save(m_sim, str(out_path))
            print("ONNX graph simplified.")
    except ImportError:
        print("onnxsim not installed — skipping simplification (install with pip install onnxsim)")

    print(f"Classifier ONNX saved to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PyTorch model to ONNX for edge")
    parser.add_argument("--weights", required=True, help="Path to .pt or .pth checkpoint")
    parser.add_argument("--out", required=True, help="Output ONNX file path")
    parser.add_argument("--model-type", choices=["detector", "classifier"],
                        default="detector", help="Which model type to export")
    parser.add_argument("--backbone", default="mobilenet_v3_small",
                        help="Classifier backbone (only for --model-type classifier)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Input image size for YOLO export")
    parser.add_argument("--input-size", type=int, default=224,
                        help="Input size for classifier export")
    parser.add_argument("--num-classes", type=int, default=2)
    parser.add_argument("--quantize", action="store_true",
                        help="Apply INT8 dynamic quantization (classifier only)")
    args = parser.parse_args()

    if args.model_type == "detector":
        export_detector(args.weights, args.out, args.imgsz)
    else:
        export_classifier(
            args.weights, args.out,
            backbone=args.backbone,
            input_size=args.input_size,
            num_classes=args.num_classes,
            quantize=args.quantize,
        )


if __name__ == "__main__":
    main()
