# saasa — Master Reference Document

Wire harness visual inspection system deployed on edge devices (Raspberry Pi / ARM SBC).
Scans a barcode, captures a camera frame, runs AI detection + classification on 7 wires,
stores results, and continuously collects labelled samples for future model retraining.

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Dependency Split](#2-dependency-split)
3. [Configuration](#3-configuration)
4. [Database Schema](#4-database-schema)
5. [AI Inference Layer](#5-ai-inference-layer)
6. [Service Layer](#6-service-layer)
7. [Data Collection Layer](#7-data-collection-layer)
8. [Flask Routes](#8-flask-routes)
9. [Camera Manager](#9-camera-manager)
10. [Frontend](#10-frontend)
11. [Training Module](#11-training-module)
12. [Scripts](#12-scripts)
13. [Tests](#13-tests)
14. [End-to-End Data Flows](#14-end-to-end-data-flows)
15. [Deployment Cheatsheet](#15-deployment-cheatsheet)

---

## 1. Repository Layout

```
saasa/
├── run.py                              Entry point — flask run
├── requirements.txt                    Edge runtime deps (no torch)
├── requirements-train.txt              Training deps (torch, ultralytics, etc.)
├── README.md                           Quick-start guide
├── master.md                           ← this file
├── .gitignore
│
├── app/                                Edge Flask application
│   ├── __init__.py                     create_app() factory
│   │
│   ├── ai/                             Inference pipeline
│   │   ├── runtime.py                  OnnxRuntime / PytorchRuntime abstraction
│   │   ├── inference_pipeline.py       Orchestrator: frame → list[WireResult]
│   │   ├── detector/
│   │   │   └── yolo.py                 WireDetector — YOLO ONNX wrapper
│   │   └── classifier/
│   │       └── classifier.py           WireClassifier — binary crop classifier
│   │
│   ├── data_collection/                Async on-disk sample collection
│   │   ├── storage.py                  Storage protocol + FilesystemStorage
│   │   ├── collector.py                DataCollector — background queue + writer
│   │   └── exporter.py                 DatasetExporter — YOLO-format export
│   │
│   ├── services/                       Business logic
│   │   ├── model_service.py            ModelService — lazy ONNX loader
│   │   ├── inspection_service.py       InspectionService — end-to-end workflow
│   │   └── data_collection_service.py  DataCollectionService — metadata patcher
│   │
│   ├── routes/                         Flask blueprints
│   │   ├── api.py                      /api/* — JSON API (inspect, validate_qr, save_manual)
│   │   ├── ui.py                       / and /inspection/<id> — HTML form views
│   │   ├── barcode.py                  /barcode/check
│   │   ├── camera.py                   /camera/snapshot, /camera/stream
│   │   └── inspection.py               /inspection/start (stub)
│   │
│   ├── camera/
│   │   └── manager.py                  CameraManager — background-thread frame capture
│   │
│   ├── db/
│   │   ├── database.py                 All SQL — schema init, CRUD, finalization
│   │   ├── queries.py                  Read-friendly wrappers (used by routes/tests)
│   │   └── __init__.py                 Re-exports public query API
│   │
│   ├── utils/
│   │   ├── logger.py                   setup_logging() / get_logger()
│   │   └── config_loader.py            YAML loader with env-var overrides
│   │
│   └── config/
│       ├── app_config.yaml             Log level, paths, camera, inference backend
│       ├── model_config.yaml           Model file names, versions, thresholds
│       ├── data_collection_config.yaml Collection policy, retention, storage root
│       └── workflow_config.yaml        Wire count, pass policy
│
├── training/                           Training module — NOT deployed to edge
│   ├── train_detector.py               Ultralytics YOLO training script
│   ├── train_classifier.py             Torchvision MobileNetV3 training script
│   ├── export.py                       PyTorch → ONNX export + INT8 quantization
│   ├── evaluate.py                     mAP / accuracy evaluation
│   ├── prepare_dataset.py              Collected data → YOLO dataset
│   ├── data/
│   │   └── dataset.py                  WireCropDataset (PyTorch Dataset)
│   └── config/
│       ├── detector_train.yaml         YOLO training hyperparameters
│       └── classifier_train.yaml       Classifier training hyperparameters
│
├── scripts/
│   ├── init_db.py                      Initialize SQLite schema
│   ├── export_collected_data.py        CLI — bundle edge data into YOLO dataset
│   └── update_model.py                 CLI — install new ONNX models on edge
│
├── tests/
│   ├── conftest.py                     Pytest fixtures (isolated DB per test)
│   ├── test_database_flow.py           End-to-end DB workflow
│   ├── test_compute_final_result.py    SQL aggregation logic
│   ├── test_insert_wire_result.py      Wire result persistence
│   ├── test_update_manual_result.py    Manual override path
│   ├── test_inference_pipeline.py      Pipeline with stub runtime (no models needed)
│   └── test_data_collector.py         Storage, collector, filter, patch tests
│
├── static/
│   ├── main.js                         SPA JavaScript (QR validation, inspect flow)
│   ├── style.css                       Design system (Pravantia Industrial)
│   └── img/
│       ├── blueprint.png               Wire assembly diagram shown in UI
│       └── logo.png
│
└── templates/
    └── barcode.html                    Single-page inspection UI
```

---

## 2. Dependency Split

### `requirements.txt` — Edge device only

```
flask>=3.0
opencv-python-headless>=4.9    # no GUI, smaller footprint on ARM
onnxruntime>=1.18              # ARM wheels available via pip
numpy>=1.24
Pillow>=10.0
PyYAML>=6.0
```

**Never install `torch`, `ultralytics`, or `torchvision` on the edge device.**

### `requirements-train.txt` — Central training server

```
-r requirements.txt
ultralytics>=8.3
torch>=2.1
torchvision>=0.16
pandas>=2.0
matplotlib>=3.7
onnx>=1.15
onnxsim>=0.4
```

---

## 3. Configuration

All YAML files live in `app/config/`. Loaded by `app/utils/config_loader.load(name)`.
Top-level keys can be overridden with environment variables prefixed `SAASA_<UPPER_KEY>`.

### `app_config.yaml`

| Key | Default | Purpose |
|---|---|---|
| `log_level` | `INFO` | Root logging level |
| `log_file` | `data/logs/saasa.log` | Optional file sink |
| `models_dir` | `models` | Directory containing ONNX model files |
| `data_dir` | `data` | Root for DB, crops, logs |
| `inference_backend` | `onnx` | `onnx` (edge) or `pytorch` (dev) |
| `camera.enabled` | `false` | Enable CameraManager on startup |
| `camera.source` | `0` | cv2.VideoCapture source |
| `camera.width/height` | `640/480` | Capture resolution |

### `model_config.yaml`

| Key | Purpose |
|---|---|
| `backend` | `onnx` or `pytorch` |
| `detector.model_file` | Filename inside `models_dir` (e.g. `wire_yolo.onnx`) |
| `detector.model_version` | Stored in DB `inspections.yolo_model_version` |
| `detector.input_size` | `[640, 640]` — resize target before ONNX inference |
| `detector.confidence_threshold` | NMS pre-filter (default `0.4`) |
| `detector.num_wires` | Expected wire count (default `7`) |
| `detector.sort_by` | `top_to_bottom` or `left_to_right` |
| `classifier.model_file` | e.g. `wire_cls.onnx` |
| `classifier.classes` | `["ok", "fail"]` — index 0 = ok |
| `classifier.confidence_threshold` | Below this → conservative "fail" |

### `data_collection_config.yaml`

| Key | Default | Purpose |
|---|---|---|
| `enabled` | `true` | Master switch |
| `mode` | `all` | `all`, `low_confidence`, or `manual_override` |
| `low_conf_threshold` | `0.7` | Threshold for `low_confidence` mode |
| `storage_root` | `data/collected` | Base directory for written samples |
| `max_queue` | `256` | Collector queue depth (drops on overflow) |
| `retention_days` | `30` | Auto-delete folders older than N days |

### `workflow_config.yaml`

| Key | Default | Purpose |
|---|---|---|
| `num_wires` | `7` | Expected wires per inspection |
| `pass_policy` | `all` | All wires must pass (any 0 → overall FAIL) |

---

## 4. Database Schema

**Location:** `data/local/inspection_data.db` (SQLite, created on startup via `init_db()`)

### `inspections`
```
id                      INTEGER PK AUTOINCREMENT
barcode                 TEXT NOT NULL
product_type            TEXT
inspection_time         DATETIME DEFAULT CURRENT_TIMESTAMP
final_result            INTEGER  -- 1=PASS, 0=FAIL, NULL=not finalized
override_used           INTEGER  -- 1 if any wire was manually overridden
yolo_model_version      TEXT     -- populated by InspectionService
classifier_model_version TEXT
synced                  INTEGER DEFAULT 0
```

### `wire_results`
```
id              INTEGER PK AUTOINCREMENT
inspection_id   INTEGER FK → inspections.id
wire_no         INTEGER CHECK(1–7)  UNIQUE per inspection
ai_result       INTEGER  -- 1=PASS, 0=FAIL (raw model output)
manual_result   INTEGER  -- NULL unless human overrode
final_result    INTEGER  -- COALESCE(manual_result, ai_result)
confidence      REAL     -- classifier confidence score
image_path      TEXT     -- path to wire crop JPEG
created_at      DATETIME
```

**Pass/fail rule:** `MIN(final_result across all 7 wires)` — any single 0 makes the whole inspection FAIL.

### `detections`
```
id               INTEGER PK
inspection_id    INTEGER FK
detection_index  INTEGER
class_name       TEXT
confidence       REAL
bbox_x/y/w/h     REAL  -- absolute pixel coords in original frame
```

### `barcode_history`
```
barcode           TEXT PK
first_seen        DATETIME
last_seen         DATETIME
inspection_count  INTEGER
```
Used for fast duplicate barcode detection without scanning `inspections`.

### Key functions in `app/db/database.py`

| Function | Signature | Notes |
|---|---|---|
| `init_db()` | `→ None` | Creates schema; safe to call repeatedly |
| `create_inspection` | `(barcode, product_type, yolo_model, classifier_model) → int` | Returns new `id`; upserts `barcode_history` |
| `insert_wire_ai_result` | `(inspection_id, wire_no, ai_result, confidence=None, image_path=None) → None` | INSERT OR REPLACE |
| `update_manual_wire_result` | `(inspection_id, wire_no, manual_result) → None` | Sets `override_used=1` on the inspection row |
| `compute_final_result` | `(inspection_id) → int\|None` | None if < 7 wires; 0/1 otherwise |
| `finalize_inspection` | `(inspection_id) → bool` | Writes `final_result` to `inspections`; returns True=PASS |

`app/db/queries.py` exposes read-friendly wrappers (`get_inspection_by_barcode`, `get_wire_results_by_inspection`, etc.) used by routes and tests.

---

## 5. AI Inference Layer

### `app/ai/runtime.py` — Backend abstraction

```python
build_runtime(model_path, backend="onnx") → OnnxRuntime | PytorchRuntime
```

Both expose the same interface:
```python
runtime.run(image: np.ndarray) → list[np.ndarray]
runtime.input_name  → str
runtime.input_shape → tuple
```

**`OnnxRuntime`** uses `onnxruntime.InferenceSession` — works on CPU/ARM, no torch needed.  
**`PytorchRuntime`** loads via `torch.load` — dev boxes only.

---

### `app/ai/detector/yolo.py` — Wire detector

```python
class WireDetector:
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]
```

**`Detection` dataclass:** `class_name, confidence, bbox(x,y,w,h)`

**Pipeline:**
1. Resize frame to `input_size`, normalize to float32, transpose HWC→CHW, add batch dim
2. Run ONNX session
3. Decode YOLOv8 output tensor `(1, 4+nc, num_anchors)` → filter by confidence → NMS via `cv2.dnn.NMSBoxes`
4. Sort by `top_to_bottom` (y-coord) or `left_to_right` (x-coord) so wire index matches wire number

**Missing wire handling:** if fewer than `num_wires` detected, the pipeline fills missing slots as FAIL (conservative).

---

### `app/ai/classifier/classifier.py` — Per-wire classifier

```python
class WireClassifier:
    def classify(self, crop_bgr: np.ndarray) -> tuple[str, float]
    # returns ("ok" | "fail", confidence)
```

**Pipeline:**
1. Resize to `input_size`, RGB, float32/255, ImageNet mean/std normalization, CHW batch
2. Run ONNX session → logits → softmax → argmax
3. If `confidence < threshold` → conservative "fail" regardless of argmax

---

### `app/ai/inference_pipeline.py` — Orchestrator

```python
class InferencePipeline:
    def run(self, frame_bgr: np.ndarray) -> list[WireResult]
```

**`WireResult` dataclass:** `wire_no(1–7), ai_result(0/1), confidence, bbox, crop_bytes(JPEG)`

**Steps:**
1. `WireDetector.detect(frame)` → sorted detections
2. For each wire slot 1–7:
   - Extract crop from frame using bbox
   - `WireClassifier.classify(crop)` → label, confidence
   - `ai_result = 1 if label == "ok" else 0`
   - JPEG-encode the crop into `crop_bytes`
3. Slots with no detection → `WireResult(ai_result=0, confidence=0.0, crop_bytes=b"")`

---

## 6. Service Layer

### `app/services/model_service.py` — `ModelService`

Lazy singleton. `get_pipeline()` loads models on first call and caches; thread-safe via `threading.Lock`.

```python
ModelService(models_dir, backend="onnx")
  .get_pipeline()       → InferencePipeline   # raises ModelLoadError if files missing
  .is_ready             → bool
  .detector_version     → str                 # read from model_config.yaml
  .classifier_version   → str
```

**App startup behaviour:** models are NOT loaded at startup. First `POST /api/inspect` triggers loading. If ONNX files are absent the route returns **503** — no fake results ever.

Registered as `app.extensions["model_service"]` in `create_app()`.

---

### `app/services/inspection_service.py` — `InspectionService`

```python
InspectionService(model_service, data_collector=None)
  .run(inspection_id, frame_bgr, barcode="") → dict
```

**Steps:**
1. `model_service.get_pipeline()` — raises `InspectionError` if not ready
2. `pipeline.run(frame_bgr)` → `list[WireResult]`
3. For each wire: save crop JPEG to `data/crops/<inspection_id>/wire_N.jpg`; call `db.insert_wire_ai_result(..., confidence=, image_path=)`
4. UPDATE `inspections.yolo_model_version` and `classifier_model_version`
5. Enqueue `CollectionSample` in DataCollector (non-blocking)
6. Return JSON dict: `{status, detections, failed_wires, annotated_image}` — same shape the frontend already expects

**`InspectionError`** is caught in the route and returned as 503.

---

### `app/services/data_collection_service.py` — `DataCollectionService`

Thin facade:
```python
DataCollectionService(collector)
  .record_final_result(inspection_id, final_result, manual_overrides)
```
Called after `/api/save_manual_results` finalizes the inspection to patch `metadata.json` with the human-verified label.

---

## 7. Data Collection Layer

### `app/data_collection/storage.py`

**`Storage` protocol** (runtime-checkable):
```python
write_bytes(relative_path, data)
write_json(relative_path, obj)
read_json(relative_path) → dict
list(prefix="") → Iterator[str]
exists(relative_path) → bool
```

**`FilesystemStorage(root)`** — concrete implementation. All paths are relative to `root`.

**`CloudStorage`** — stub that raises `NotImplementedError`. Plug in S3/GCS/Azure by implementing the same protocol.

---

### `app/data_collection/collector.py` — `DataCollector`

```python
DataCollector(storage, mode="all", low_conf_threshold=0.7, max_queue=256, retention_days=30)
  .enqueue(sample: CollectionSample)           # non-blocking; drops if queue full
  .patch_final_result(inspection_id, final_result, manual_overrides)
  .stop()                                       # graceful drain + shutdown
```

**`CollectionSample` dataclass:** `inspection_id, barcode, frame_jpeg, wire_results[], detector_version, classifier_version, final_result, manual_overrides, wire_crops`

**Background writer** drains the queue and writes to:
```
<storage_root>/<YYYY-MM-DD>/<inspection_id>/
    frame.jpg
    wire_1.jpg … wire_7.jpg    (when crop_bytes provided)
    metadata.json
```

**`metadata.json` fields:**
```json
{
  "inspection_id": 42,
  "barcode": "BC-001",
  "timestamp": "2026-04-29T...",
  "detector_version": "1.0.0",
  "classifier_version": "1.0.0",
  "final_result": null,        ← patched after manual override
  "manual_overrides": {},
  "wires": [
    {"wire_no": 1, "ai_result": 1, "confidence": 0.92, "bbox": [x,y,w,h]},
    ...
  ]
}
```

**Collection modes:**
| Mode | Collects when |
|---|---|
| `all` | Every inspection |
| `low_confidence` | Any wire confidence < `low_conf_threshold` |
| `manual_override` | Human corrected at least one wire |

**Retention:** On startup, folders older than `retention_days` are deleted. Set `0` to disable.

Registered as `app.extensions["data_collector"]` in `create_app()`.

---

### `app/data_collection/exporter.py` — `DatasetExporter`

```python
DatasetExporter(storage_root)
  .export(out_dir, train_split=0.8, seed=42) → Path  # returns dataset.yaml path
```

**Output layout:**
```
<out_dir>/
    dataset.yaml               ultralytics descriptor
    images/train/  images/val/ full-frame JPEGs
    labels/train/  labels/val/ YOLO txt files (one line per wire)
    crops/train/ok/  crops/train/fail/   per-wire crops for classifier training
    crops/val/ok/    crops/val/fail/
```

**YOLO label format (one line per wire):**
```
<class_id> <cx> <cy> <w> <h>   (all values normalised 0–1)
```
`class_id = 0` (ok) or `1` (fail). Uses `final_result` — post manual override — as ground truth.

---

## 8. Flask Routes

### `app/routes/api.py` — `/api/*`

| Endpoint | Method | Request body | Response |
|---|---|---|---|
| `/api/validate_qr` | POST | `{qr_code, force_proceed}` | `{valid, exists, inspection_id?, existing_record?}` |
| `/api/inspect` | POST | `{inspection_id, image_b64?}` | `{status, detections[], failed_wires[], annotated_image}` or 503 |
| `/api/save_manual_results` | POST | `{inspection_id, manual_results: {wireN: bool}}` | `{status: "ok"}` |

**`/api/inspect` flow:**
1. Resolve `model_service` from `app.extensions` — 503 if absent
2. Acquire BGR frame from `CameraManager.get_frame()` or decode `image_b64` from request
3. Look up `barcode` from `inspections` for metadata
4. Call `InspectionService.run()` — 503 on `InspectionError`
5. Return JSON (same shape as the original random stub — frontend unchanged)

**`/api/save_manual_results` flow:**
1. Apply each `update_manual_wire_result()`
2. `compute_final_result()` + `finalize_inspection()`
3. `data_collector.patch_final_result()` to update `metadata.json`

---

### `app/routes/ui.py` — HTML form views

| Endpoint | View |
|---|---|
| `GET/POST /` | Barcode entry form |
| `GET/POST /inspection/<id>` | Manual override form |

---

### `app/routes/camera.py`

| Endpoint | Returns |
|---|---|
| `GET /camera/snapshot` | Single JPEG frame |
| `GET /camera/stream` | MJPEG multipart stream |

Only registered if `ENABLE_CAMERA` is set in app config.

---

## 9. Camera Manager

`app/camera/manager.py` — `CameraManager`

Runs a daemon thread that reads frames from `cv2.VideoCapture` and stores the latest JPEG in memory behind an `RLock`.

```python
CameraManager(source=0, width=640, height=480, fallback_image=None, reopen_interval=5.0)
  .get_frame()  → np.ndarray | None   # BGR numpy array
  .get_jpeg()   → bytes | None        # latest JPEG bytes
  .stop()
```

Auto-reconnects on camera failure after `reopen_interval` seconds. Serves a fallback JPEG image if the camera is unavailable.

---

## 10. Frontend

**`templates/barcode.html`** — Single-page inspection UI with two steps.

**`static/main.js`** — SPA controller

| Step | What happens |
|---|---|
| Step 1 — QR Entry | User types barcode → `POST /api/validate_qr` → if new, store `inspection_id` and go to Step 2; if exists, show previous result with option to re-inspect |
| Step 2 — Inspection | Live camera feed (`/camera/stream` or fallback); user hits Inspect → `POST /api/inspect` → wire result cards update; user adjusts dropdowns → Submit → `POST /api/save_manual_results` → back to Step 1 |

**`static/style.css`** — Pravantia Industrial design system: dark purple sidebar (#2D0A4E), green PASS (#16A34A), red FAIL (#DC2626).

The JavaScript JSON contract (`detections[]`, `failed_wires[]`, `status`, `annotated_image`) is preserved exactly — no frontend changes required after the backend rewire.

---

## 11. Training Module

The `training/` directory is **never imported by `app/`** and is not installed on the edge device.

### `training/prepare_dataset.py`
Wraps `DatasetExporter`. Takes `data/collected/` from the edge and produces a YOLO dataset.

```bash
python training/prepare_dataset.py --collected data/collected --out /tmp/wire_ds
```

### `training/train_detector.py`
Wraps `ultralytics YOLO.train()`. Config from `training/config/detector_train.yaml`.

```bash
python training/train_detector.py --data /tmp/wire_ds/dataset.yaml --epochs 100
```
Best checkpoint: `runs/detect/wire_detector/weights/best.pt`

### `training/train_classifier.py`
Trains MobileNetV3-Small (or ResNet18) with `WireCropDataset`.

```bash
python training/train_classifier.py --data /tmp/wire_ds/crops --epochs 50
```
Best checkpoint: `runs/classify/wire_classifier/best.pth`

### `training/export.py`
Exports to ONNX. Optional `--quantize` applies INT8 dynamic quantization for smaller ARM models.

```bash
# Detector
python training/export.py --weights runs/detect/.../best.pt --out models/wire_yolo.onnx

# Classifier
python training/export.py --model-type classifier \
    --weights runs/classify/.../best.pth --out models/wire_cls.onnx [--quantize]
```

### `training/evaluate.py`
```bash
python training/evaluate.py detector --weights best.pt --data dataset.yaml
python training/evaluate.py classifier --weights best.pth --data crops/
```

### `training/data/dataset.py` — `WireCropDataset`
PyTorch `Dataset` over `crops/{split}/{ok,fail}/` folders. Applies train/val augmentation transforms.

### Training config files

**`training/config/detector_train.yaml`** — YOLO base model, epochs, batch, lr, augmentation flags.
**`training/config/classifier_train.yaml`** — backbone, pretrained, input size, lr, output dir.

---

## 12. Scripts

### `scripts/init_db.py`
Creates the SQLite schema. Safe to run multiple times.
```bash
python scripts/init_db.py
```

### `scripts/export_collected_data.py`
CLI wrapper for `DatasetExporter`. Run on the edge to produce a portable dataset bundle.
```bash
python scripts/export_collected_data.py --out /tmp/wire_ds [--split 0.8]
```

### `scripts/update_model.py`
Copies new ONNX files into `models/` and updates version strings in `model_config.yaml`.
Restart the Flask app after running.
```bash
python scripts/update_model.py \
    --detector /path/to/wire_yolo.onnx \
    --classifier /path/to/wire_cls.onnx \
    --detector-version 1.1.0 --classifier-version 1.1.0
```

---

## 13. Tests

Run with: `pytest tests/`  No real models or camera required.

| Test file | What it covers |
|---|---|
| `test_database_flow.py` | End-to-end inspection DB workflow |
| `test_compute_final_result.py` | SQL aggregation (incomplete / all-pass / one-fail / manual override) |
| `test_insert_wire_result.py` | Wire result persistence including confidence + image_path |
| `test_update_manual_result.py` | Manual override path and final result recomputation |
| `test_inference_pipeline.py` | Full pipeline with stub ONNX runtime — no real models needed |
| `test_data_collector.py` | Storage, collector write, metadata content, patch, mode filters |

**`tests/conftest.py`** — Pytest fixture that creates a fresh `inspection_data.db` in a temp directory for each test function (no test pollution).

---

## 14. End-to-End Data Flows

### A. Inspection on the Edge

```
Operator scans barcode
        │
        ▼
POST /api/validate_qr
  └─ create_inspection(barcode) → inspection_id (in DB)
        │
        ▼
POST /api/inspect
  ├─ CameraManager.get_frame() → frame_bgr
  ├─ ModelService.get_pipeline() → InferencePipeline
  ├─ pipeline.run(frame) → [WireResult × 7]
  ├─ db.insert_wire_ai_result(×7)       writes wire_results rows
  ├─ DataCollector.enqueue(sample)      async → disk
  └─ return {status, detections[]}
        │
        ▼
Operator reviews & adjusts dropdowns
        │
        ▼
POST /api/save_manual_results
  ├─ db.update_manual_wire_result(×N overrides)
  ├─ db.finalize_inspection()           writes inspections.final_result
  └─ DataCollector.patch_final_result() updates metadata.json on disk
```

### B. Training Loop (Central Server)

```
Edge device: data/collected/<date>/<id>/{frame.jpg, metadata.json, wire_N.jpg}
        │
        │  (copy to training server via USB / rsync / manual)
        ▼
python training/prepare_dataset.py --collected data/collected --out /tmp/ds
        │  produces: /tmp/ds/dataset.yaml, images/, labels/, crops/
        ▼
python training/train_detector.py --data /tmp/ds/dataset.yaml
        │  → runs/detect/wire_detector/weights/best.pt
        ▼
python training/train_classifier.py --data /tmp/ds/crops
        │  → runs/classify/wire_classifier/best.pth
        ▼
python training/export.py --weights best.pt --out models/wire_yolo.onnx
python training/export.py --model-type classifier --weights best.pth --out models/wire_cls.onnx
        │
        │  (copy ONNX files back to edge device)
        ▼
python scripts/update_model.py --detector wire_yolo.onnx --classifier wire_cls.onnx
        │
        ▼
Restart Flask app → ModelService lazy-loads new models on next /api/inspect
```

### C. No Model Installed

```
POST /api/inspect
  └─ ModelService.get_pipeline()
       └─ raises ModelLoadError("Detector model not found: models/wire_yolo.onnx ...")
            └─ InspectionError caught in route
                 └─ HTTP 503 {"error": "no model loaded", "detail": "..."}
```
No fake results are ever returned.

### D. Data Collection — Manual Override Feedback Loop

```
AI labels (ai_result) written to DB + metadata.json at inspection time
        │
Operator overrides wire 3: FAIL → PASS
        │
POST /api/save_manual_results
  └─ db.update_manual_wire_result(3, 1)    DB final_result updated
  └─ DataCollector.patch_final_result()    metadata.json final_result patched
        │
On next training run: metadata.json final_result (human-verified) used as label
→ manual corrections automatically improve training data quality
```

---

## 15. Deployment Cheatsheet

### First-time edge setup

```bash
pip install -r requirements.txt
mkdir -p models data/collected data/logs
python scripts/init_db.py
# copy ONNX files to models/wire_yolo.onnx and models/wire_cls.onnx
python run.py
# → http://0.0.0.0:5000
```

### Enable camera

Edit `app/config/app_config.yaml`:
```yaml
camera:
  enabled: true
  source: 0       # or /dev/video0, or an RTSP URL
```

### Update models after retraining

```bash
python scripts/update_model.py \
    --detector /path/to/wire_yolo.onnx \
    --classifier /path/to/wire_cls.onnx \
    --detector-version 1.2.0 --classifier-version 1.2.0
# restart Flask app
```

### Export and ship training data

```bash
python scripts/export_collected_data.py --out /tmp/wire_ds
# copy /tmp/wire_ds to training server
```

### Run tests

```bash
pip install pytest
pytest tests/ -v
```

### Environment variable overrides (edge)

Any top-level key in `app_config.yaml` can be overridden at runtime:
```bash
SAASA_LOG_LEVEL=DEBUG SAASA_INFERENCE_BACKEND=pytorch python run.py
```
