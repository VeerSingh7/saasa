# Testing guidance for database functions

This file provides a sample test script and guidance to validate the DB helper functions in `app/db/database.py`. The script demonstrates common flows you described: checking barcode existence, creating an inspection, inserting AI results, applying a manual override, finalizing inspection, and verifying the final result.

Important: This test script is designed to run without modifying `app/db/database.py`. It will create the DB file at `data/local/inspection_data.db` used by the module. If you prefer running tests against an isolated DB file, set the environment or modify `DB_PATH` at runtime via a small wrapper — otherwise the test below uses the default path.

Place the following snippet in `tests/test_database_flow.py` (this file is a suggestion; we are not writing it to the repo automatically in this step). The script uses only the public helpers in `database.py`.

Sample test (plain Python, no pytest required):

```py
# tests/test_database_flow.py
from app.db import database as db
import os

# Optional: remove previous DB for a fresh run
db_file = os.path.join("data", "local", "inspection_data.db")
if os.path.exists(db_file):
    os.remove(db_file)

# Initialize schema
db.init_db()

barcode = "TEST-BARCODE-001"

# 1) ensure barcode is new
assert not db.is_barcode_already_scanned(barcode)

# 2) create inspection
inspection_id = db.create_inspection(barcode, product_type="test-product")
assert isinstance(inspection_id, int)

# 3) insert AI results for wires (example: 7 wires; 1=PASS, 0=FAIL)
ai_results = [1, 1, 1, 1, 1, 1, 1]
for i, ai in enumerate(ai_results, start=1):
    db.insert_wire_ai_result(inspection_id, i, ai)

# 4) finalize (should pass because all AI=1)
final_pass = db.finalize_inspection(inspection_id)
assert final_pass is True

# 5) Simulate new inspection with an AI failure, then manual override
barcode2 = "TEST-BARCODE-002"
inspection_id2 = db.create_inspection(barcode2)
ai_results2 = [1, 1, 0, 1, 1, 1, 1]
for i, ai in enumerate(ai_results2, start=1):
    db.insert_wire_ai_result(inspection_id2, i, ai)

# Finalize now would be FAIL
try:
    pass_result = db.finalize_inspection(inspection_id2)
    # If finalize_inspection didn't crash, pass_result should be False
    assert pass_result is False
except ValueError:
    # If the module's expectations about completeness are violated,
    # treat as a failed test condition
    raise

# 6) Apply manual override to wire 3 to change it to PASS
# First re-insert AI result (already present), then update manual
# For safety, call update_manual_wire_result
db.update_manual_wire_result(inspection_id2, 3, manual_result=1)

# Re-finalize and expect PASS now
final_pass2 = db.finalize_inspection(inspection_id2)
assert final_pass2 is True

print("DB flow test completed successfully")
```

Notes and improvements
- If you prefer `pytest`, convert assertions to plain asserts and name the file `test_*.py`. `pytest` will pick it up.
- The test removes the DB file at the start to ensure a fresh state. If you need to preserve real data, do not remove the DB file and instead use a separate path.
- For fully isolated tests, consider temporarily monkeypatching `app.db.database.DB_PATH` to point to a temporary file under `/tmp` or use `tempfile.NamedTemporaryFile` and supply that Path object to the module before calling `get_connection()` (this requires executing the test runner in a way that sets the variable before module usage).

Small test wrapper using `pytest` fixtures (advanced)
- Create a fixture that temporarily sets `app.db.database.DB_PATH` to a temp file and calls `init_db()` before tests, and removes it after tests.


---
This documentation documents how to test DB flows using the current helpers. It does not modify source code.
