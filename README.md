# saasa — Wire Inspection System

Edge-deployed visual quality inspection system for industrial wire harnesses.
Detects and classifies 7 wires per harcode scan using a YOLO detector + binary classifier pipeline.

## Architecture

```
app/                  Edge Flask app (inference + data collection)
├── ai/               ONNX inference: WireDetector + WireClassifier + InferencePipeline
├── data_collection/  Async sample collector; YOLO-format dataset exporter
├── services/         ModelService (lazy loader), InspectionService, DataCollectionService
├── db/               SQLite persistence (inspections, wire_results, detections)
├── camera/           Background-thread camera manager (MJPEG stream)
├── routes/           Flask blueprints (api, ui, barcode, camera)
├── utils/            Logging, config loader
└── config/           YAML configuration files

training/             Central-server training module (NOT deployed to edge)
├── train_detector.py     Ultralytics YOLO training
├── train_classifier.py   Torchvision MobileNetV3 training
├── export.py             PyTorch → ONNX (+ optional INT8 quantization)
├── evaluate.py           mAP / accuracy evaluation
├── prepare_dataset.py    Convert collected data → train/val splits
└── data/dataset.py       WireCropDataset class

scripts/
├── init_db.py                Initialize SQLite database
├── export_collected_data.py  Bundle edge data for training
└── update_model.py           Install new ONNX models on the edge device
```

## Edge Device Setup (Raspberry Pi / ARM SBC)

```bash
pip install -r requirements.txt   # lightweight: flask, onnxruntime, opencv-headless, etc.
mkdir -p models data/collected data/logs

# Place ONNX model files (from training machine):
#   models/wire_yolo.onnx
#   models/wire_cls.onnx

python scripts/init_db.py
python run.py
```

App runs on http://0.0.0.0:5000.

### Camera setup

Set `camera.enabled: true` in `app/config/app_config.yaml`:

```yaml
camera:
  enabled: true
  source: 0          # /dev/video0 or RTSP URL
  width: 640
  height: 480
```

### When no model is installed

`POST /api/inspect` returns HTTP 503 with:
```json
{"error": "no model loaded", "detail": "Detector model not found: models/wire_yolo.onnx ..."}
```
No fake results are generated.

## Training Workflow (Central Server)

```bash
pip install -r requirements-train.txt

# 1. Copy data/ directory from edge device to training machine
#    (or use scripts/update_model.py to push in reverse after training)

# 2. Build YOLO dataset from collected samples
python training/prepare_dataset.py --collected data/collected --out /tmp/wire_ds

# 3. Train detector
python training/train_detector.py --data /tmp/wire_ds/dataset.yaml --epochs 100

# 4. Train classifier
python training/train_classifier.py --data /tmp/wire_ds/crops --epochs 50

# 5. Export to ONNX
python training/export.py --weights runs/detect/wire_detector/weights/best.pt \
    --out models/wire_yolo.onnx
python training/export.py --model-type classifier \
    --weights runs/classify/wire_classifier/best.pth \
    --out models/wire_cls.onnx [--quantize]

# 6. Deploy to edge
python scripts/update_model.py \
    --detector models/wire_yolo.onnx \
    --classifier models/wire_cls.onnx \
    --detector-version 1.1.0 --classifier-version 1.1.0
```

## Data Collection

Every inspection automatically saves:
```
data/collected/<YYYY-MM-DD>/<inspection_id>/
    frame.jpg          full camera frame
    wire_1.jpg … wire_7.jpg   per-wire crops
    metadata.json      bbox, ai_result, confidence, final_result, model versions
```

Collection policy is set in `app/config/data_collection_config.yaml`:
- `mode: all` — collect every inspection
- `mode: low_confidence` — only when any wire confidence < threshold
- `mode: manual_override` — only when a human corrected the AI

`final_result` in `metadata.json` is patched after manual overrides are submitted,
so training labels always reflect the human-verified ground truth.

## Configuration

| File | Purpose |
|---|---|
| `app/config/app_config.yaml` | Log level, paths, camera, inference backend |
| `app/config/model_config.yaml` | Model file names, versions, thresholds |
| `app/config/data_collection_config.yaml` | Collection mode, retention, storage |
| `app/config/workflow_config.yaml` | Number of wires, pass policy |

## Running Tests

```bash
pip install pytest
pytest tests/
```

Existing DB tests and new pipeline/collector tests run without real models or cameras.
