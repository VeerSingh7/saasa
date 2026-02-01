# Database module documentation

File: `app/db/database.py`

This document describes the database schema, the main functions exposed by the module, their inputs, outputs, side-effects, and example usage patterns from a test or UI.

## Database file
- Location used at runtime: `data/local/inspection_data.db` (the code creates parent directories if missing).
- SQLite is used via Python `sqlite3` and rows are returned as `sqlite3.Row`.

## Tables
- `inspections`
  - Columns: `id` (PK), `barcode`, `product_type`, `inspection_time` (timestamp),
    `final_result` (INTEGER: 1=PASS, 0=FAIL), `override_used` (0/1),
    `yolo_model_version`, `classifier_model_version`, `synced`.
  - One row per barcode scan / inspection.

- `detections`
  - Many rows per inspection, YOLO detections. Columns include `inspection_id`,
    `detection_index`, `class_name`, `confidence`, and bounding box floats.

- `wire_results`
  - Wire-level (wire 1..7) results. Columns: `inspection_id`, `wire_no` (1-7),
    `ai_result` (0/1), `manual_result` (nullable), `final_result`.
  - Unique constraint on `(inspection_id, wire_no)`.

- `barcode_history`
  - Fast check for duplicates: `barcode` (PK), `first_seen`, `last_seen`, `inspection_count`.

## Important module-level variables
- `DB_PATH` — `Path("data/local/inspection_data.db")` — the DB location.

## Connection helpers
- `get_connection()`
  - Ensures `DB_PATH.parent` exists, opens SQLite connection, sets `row_factory` to `sqlite3.Row`.
  - Returns: sqlite3.Connection.

- `init_db()`
  - Creates tables if they don't exist. Commits and closes connection.
  - Side-effects: creates DB file and parent directories.

## CRUD / Utility functions (summary)
All functions open a connection (via `get_connection()`), perform SQL statements, commit (when modifying), and close the connection.

- `create_inspection(barcode, product_type=None, yolo_model="model_yolo.pt", classifier_model="model_cls.pth") -> inspection_id`
  - Inserts a new `inspections` row (barcode, product_type, models) and updates/creates `barcode_history` via `INSERT ... ON CONFLICT DO UPDATE`.
  - Returns: integer `inspection_id` (the new row id).
  - Notes: `inspection_time` uses SQLite `CURRENT_TIMESTAMP`.

- `insert_detection(inspection_id, detection_index, class_name, confidence, bbox)`
  - Inserts a detection row into `detections`.
  - `bbox` expected as a tuple/list of 4 floats: (x, y, w, h).
  - Returns: None.

- `insert_wire_ai_result(inspection_id, wire_no, ai_result)`
  - Inserts or replaces into `wire_results` a row with `ai_result` and sets `final_result` to the same AI value.
  - `ai_result` expected to be truthy/0/1 (function casts to int).
  - Returns: None.

- `update_manual_wire_result(inspection_id, wire_no, manual_result)`
  - Updates an existing `wire_results` row's `manual_result` and `final_result` to the given `manual_result`.
  - Also sets `override_used = 1` in the associated `inspections` row.
  - Returns: None.

- `is_barcode_already_scanned(barcode) -> bool`
  - Returns True if an entry exists in `barcode_history` for `barcode`, else False.
  - Note: returns existence only (not count). Useful for a quick duplicate check before creating a new inspection.

- `get_latest_inspection_id(barcode) -> Optional[int]`
  - Returns the `id` of the most recent `inspections` row for the barcode, ordered by `inspection_time DESC`.
  - Returns `None` if no inspection exists.

- `finalize_inspection(inspection_id) -> bool`
  - There are two definitions of `finalize_inspection` in the file. The latter definition in the file shadow/overrides the earlier one. The effective behavior is the latter function (see note below).
  - Effective behavior (from the second definition):
    - Queries `MIN(COALESCE(manual_result, ai_result)) AS final_result` from `wire_results` for the inspection.
    - If no final_result found or is NULL, raises ValueError("Wire results incomplete for inspection").
    - Interprets `final_pass = int(row["final_result"])`. Note: because the SQL uses MIN(), a single 0 will make final_result 0 (FAIL); all 1s means PASS.
    - Updates `inspections.final_result` with that value.
    - Also sets `override_used = 1` if any `wire_results.manual_result IS NOT NULL` (i.e., a manual override was applied), otherwise `override_used = 0`.
    - Returns `bool(final_pass)` where True means PASS.
  - Usage: Call after all `wire_results` rows for the inspection have been written/updated.

## Caveat: duplicate `finalize_inspection` definitions
- The file contains two `finalize_inspection` definitions. The first computes the overall final pass via iterating over rows and checking manual/ai values; the second uses an SQL aggregation (`MIN(COALESCE(...))`). Because Python loads the second definition later, the second one is the effective function at runtime. Be aware when reading the file: behavior equals the second implementation.

## Example usage (from a test or UI layer)
```py
from app.db import database as db

# quick duplicate check
if db.is_barcode_already_scanned(barcode):
    latest_id = db.get_latest_inspection_id(barcode)
    # fetch more details from DB if you wish (e.g., query inspections/detections tables)
else:
    inspection_id = db.create_inspection(barcode, product_type="widget")
    # insert AI wire results (example for 7 wires)
    for wire_no, ai in enumerate(ai_results, start=1):
        db.insert_wire_ai_result(inspection_id, wire_no, ai)
    # later, if manual override occurs for wire 3:
    db.update_manual_wire_result(inspection_id, 3, manual_result=1)
    # finalize and compute final_result
    final_pass = db.finalize_inspection(inspection_id)
    # final_pass is True for PASS, False for FAIL
```

## Error handling notes
- Many functions do not raise explicit errors for missing rows; e.g., updating a manual result will succeed even if the row doesn't exist (the UPDATE affects zero rows). The caller should ensure `insert_wire_ai_result` has been called for each wire before calling `update_manual_wire_result` or `finalize_inspection`.
- `finalize_inspection` will raise ValueError if wire results are missing or incomplete (per the second implementation).

## Recommendations (non-invasive)
- When calling `update_manual_wire_result`, ensure that `insert_wire_ai_result` has created the `wire_results` row (or call `insert_wire_ai_result` first). This module uses `INSERT OR REPLACE` for AI results.
- If the UI needs detailed inspection/wire-level rows, add simple SELECT helper functions (not included in this module) or use a small DAO wrapper in `app/db/queries.py` (currently empty) to fetch rows as dictionaries.


---

Created by automation: documents runtime behavior without modifying source files.
