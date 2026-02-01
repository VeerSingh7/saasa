"""Test update_manual_result in `app.db.queries`.

Flow:
- create fresh DB
- create inspection
- insert AI wire results with one failing wire
- finalize -> expect FAIL
- call update_manual_result to override failing wire to PASS
- finalize -> expect PASS
"""

from app.db import database as db
from app.db import queries as q


def test_update_manual_result():
    barcode = "TEST-UPDATE-MANUAL-001"
    inspection_id = db.create_inspection(barcode)

    # AI results: wire 3 fails
    ai_results = [1, 1, 0, 1, 1, 1, 1]
    for i, ai in enumerate(ai_results, start=1):
        q.insert_wire_result(inspection_id, i, ai, confidence=0.9, image_path=None)

    # Finalize now should be FAIL
    res_before = q.finalize_inspection(inspection_id)
    assert res_before is False

    # Apply manual override to wire 3
    q.update_manual_result(inspection_id, 3, 1)

    # Re-finalize and expect PASS
    res_after = q.finalize_inspection(inspection_id)
    assert res_after is True

    # Also check the wire row manual_result
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT manual_result FROM wire_results WHERE inspection_id = ? AND wire_no = ?", (inspection_id, 3))
    row = cur.fetchone()
    conn.close()
    assert row is not None and int(row[0]) == 1
