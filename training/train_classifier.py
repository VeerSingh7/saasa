"""Train the per-wire binary classifier (MobileNetV3-Small by default).

Usage:
    python training/train_classifier.py \
        --config training/config/classifier_train.yaml \
        --data /path/to/exported/dataset/crops \
        [--epochs 50] [--device cpu]

Expects the crops/ subfolder produced by scripts/export_collected_data.py:
    crops/
        train/ok/*.jpg  train/fail/*.jpg
        val/ok/*.jpg    val/fail/*.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from torchvision import models
except ImportError:
    print("Install training deps: pip install -r requirements-train.txt")
    sys.exit(1)

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.data.dataset import WireCropDataset


def _build_model(backbone: str, num_classes: int, pretrained: bool):
    if backbone == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        m = models.mobilenet_v3_small(weights=weights)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
        return m
    if backbone == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        m = models.resnet18(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
        return m
    raise ValueError(f"Unsupported backbone: {backbone!r}. Choose mobilenet_v3_small or resnet18.")


def train(args: argparse.Namespace) -> None:
    with open(args.config) as f:
        cfg = yaml.safe_load(f) or {}

    if args.data:
        cfg["data_dir"] = args.data
    if args.epochs:
        cfg["epochs"] = args.epochs
    if args.device:
        cfg["device"] = args.device

    data_dir = cfg.get("data_dir")
    if not data_dir:
        print("ERROR: --data is required (path to crops/ directory)")
        sys.exit(1)

    device = torch.device(cfg.get("device", "cpu"))
    input_size = int(cfg.get("input_size", 224))
    batch = int(cfg.get("batch", 32))
    num_classes = int(cfg.get("num_classes", 2))

    train_ds = WireCropDataset(data_dir, "train", input_size)
    val_ds = WireCropDataset(data_dir, "val", input_size)
    train_dl = DataLoader(train_ds, batch_size=batch, shuffle=True, num_workers=2)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=2)

    model = _build_model(
        cfg.get("backbone", "mobilenet_v3_small"),
        num_classes,
        cfg.get("pretrained", True),
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg.get("lr", 1e-3)),
        weight_decay=float(cfg.get("weight_decay", 1e-4)),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=int(cfg.get("epochs", 50))
    )

    out_dir = Path(cfg.get("output_dir", "runs/classify")) / cfg.get("model_name", "wire_classifier")
    out_dir.mkdir(parents=True, exist_ok=True)

    best_acc = 0.0
    for epoch in range(1, int(cfg.get("epochs", 50)) + 1):
        model.train()
        running_loss = 0.0
        for imgs, labels in train_dl:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        scheduler.step()

        # Validation
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for imgs, labels in val_dl:
                imgs, labels = imgs.to(device), labels.to(device)
                preds = model(imgs).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)
        acc = correct / total if total > 0 else 0.0
        print(f"Epoch {epoch:3d}  loss={running_loss/len(train_dl):.4f}  val_acc={acc:.4f}")

        if cfg.get("save_best", True) and acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), out_dir / "best.pth")
            print(f"  → saved best (acc={best_acc:.4f})")

    print(f"Training complete. Best val accuracy: {best_acc:.4f}")
    print(f"Model saved to {out_dir / 'best.pth'}")
    print(f"Export for edge with: python training/export.py --weights {out_dir / 'best.pth'} --model-type classifier")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train wire binary classifier")
    parser.add_argument("--config", default="training/config/classifier_train.yaml")
    parser.add_argument("--data", help="Path to crops/ directory")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--device")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
