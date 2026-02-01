# Project code overview

This document provides a high-level map to the repository code so you (or a teammate) can quickly locate and understand responsibilities.

Repository root (selected files/folders):
- `run.py` — application entrypoint (likely sets up Flask app and registers blueprints).
- `requirements.txt` — Python dependencies used by the project.

Main package: `app/`
- `app/__init__.py` — application package initializer (wiring Flask app). Inspect if you need app factory behavior.

- `app/db/`
  - `database.py` — main SQLite helper for inspections, detections, wires, and barcode history (documented in `docs/database.md`).
  - `models.py` — currently empty in this workspace snapshot (placeholder for ORM models if desired).
  - `queries.py` — currently empty (recommended place for read-only SELECT helpers and more complex queries).

- `app/ai/`
  - `inference_pipeline.py` — AI inference orchestration (not inspected for code here). Use to connect AI outputs to DB writes.
  - `classifier/` and `detector/` contain model-specific code (classifier/classifier.py and detector/yolo.py). Keep model loading and inference isolated.

- `app/services/`
  - `barcode_service.py` — empty in this snapshot. Ideally, this is the correct layer to translate UI requests (barcode checks, create inspection) into calls to `app/db/database.py`.
  - Other services: `inspection_service.py`, `model_service.py`, `workflow_service.py` — likely contain business logic.

- `app/routes/`
  - `barcode.py` — defines a `Blueprint` at `/barcode`. Current `check_barcode` route returns a JSON object with `status: "new"` and the supplied barcode. You will want to connect this route to `app/services/barcode_service` to perform actual DB queries and responses.
  - `admin.py`, `inspection.py` — other route modules; inspect them to see how front-end and APIs invoke services.

- `data/` — runtime data storage
  - `local/images/`, `local/roi/` — image and region-of-interest storage

- `models/` — pre-trained model files used by AI components. Keep large binaries here; code references `model_yolo.pt` and `model_cls.pth` as defaults.

- `tests/` — place for test scripts. Tests are not present in snapshot; adding tests here is recommended.

- `scripts/init_db.py` — helper that may call `app.db.database.init_db()` to create DB schema during setup.

Notes and TODOs (based on current snapshot):
- `app/db/models.py` and `app/db/queries.py` are empty — consider adding data access helpers to `queries.py` for read operations, and use `models.py` only if migrating to an ORM.
- `app/services/barcode_service.py` is empty — implement service functions such as `check_barcode`, `handle_scan`, `get_latest_inspection`, and `apply_manual_override` here to keep routes thin.
- `app/routes/barcode.py` currently returns a stub response — wire it to the `barcode_service` to perform real DB checks.

Where to look for DB interaction patterns
- The `database.py` file contains create/insert/update helpers. Services should orchestrate these helpers and provide a clean API to routes.

"Contract" suggestions for service functions (examples):
- `check_barcode(barcode: str) -> dict` returns {"exists": bool, "latest_inspection_id": Optional[int], "inspection_count": int}
- `start_inspection(barcode: str, product_type: Optional[str]) -> int` returns created inspection id
- `submit_ai_results(inspection_id: int, ai_results: List[int]) -> None` writes 7 wire results
- `apply_manual_override(inspection_id: int, wire_no: int, manual_result: int) -> None` updates a wire and flags override
- `finalize_inspection(inspection_id: int) -> bool` returns PASS/FAIL

This structure will make routes minimal (validate input, call service, return JSON) and keep business logic testable.

Appendix: recommended small next steps (non-invasive)
- Implement small SELECT helpers in `app/db/queries.py` to read `inspections`, `wire_results`, and `detections` rows by `inspection_id`.
- Implement `app/services/barcode_service.py` functions that call `database.py` helpers and return JSON-friendly dictionaries.
- Add tests under `tests/` that import `app.db.database` functions and run against a temporary DB or the `data/local/inspection_data.db` (make sure to isolate test DB or delete it after tests).

