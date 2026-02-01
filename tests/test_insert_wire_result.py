"""Test the `insert_wire_result` function in `app.db.queries`.

This script initializes a fresh DB, creates an inspection, calls
`insert_wire_result`, and then attempts to read back the inserted row.

Run with:
    PYTHONPATH=. python3 tests/test_insert_wire_result.py

Note: If `insert_wire_result` expects columns that are not present in
the current DB schema (e.g. `confidence`, `image_path`, `created_at`),
this script will surface the SQLite error so you can fix the mismatch.
"""

from pathlib import Path
from app.db import database as db
from app.db import queries as q


def test_insert_wire_result():
    # Create an inspection
    barcode = "TEST-INSERT-WIRE-001"
    inspection_id = db.create_inspection(barcode)

    # Insert a wire result
    q.insert_wire_result(
        inspection_id=inspection_id,
        wire_no=1,
        ai_result=1,
        confidence=0.92,
        image_path="/tmp/example.jpg",
    )

    # Read back the row to verify values
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM wire_results WHERE inspection_id = ? AND wire_no = ?",
        (inspection_id, 1),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "No row found in wire_results for the inserted wire"

    row_dict = dict(row)

    assert int(row_dict.get("ai_result")) == 1
    assert float(row_dict.get("confidence")) == 0.92
    assert row_dict.get("image_path") == "/tmp/example.jpg"
