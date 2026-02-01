"""Tests for compute_final_result in `app.db.queries`.

Scenarios covered:
- incomplete wires (<7) -> None
- all AI pass -> 1
- one AI fail -> 0
- manual override changes final result -> 1
"""
from app.db import database as db
from app.db import queries as q


def test_incomplete():
    inspection_id = db.create_inspection("CF-INCOMPLETE")
    # insert only 3 wires
    for i in range(1, 4):
        q.insert_wire_result(inspection_id, i, 1)

    res = q.compute_final_result(inspection_id)
    assert res is None


def test_all_pass():
    inspection_id = db.create_inspection("CF-ALL-PASS")
    for i in range(1, 8):
        q.insert_wire_result(inspection_id, i, 1)

    res = q.compute_final_result(inspection_id)
    assert int(res) == 1


def test_one_fail():
    inspection_id = db.create_inspection("CF-ONE-FAIL")
    vals = [1, 1, 0, 1, 1, 1, 1]
    for i, v in enumerate(vals, start=1):
        q.insert_wire_result(inspection_id, i, v)

    res = q.compute_final_result(inspection_id)
    assert int(res) == 0


def test_manual_override():
    inspection_id = db.create_inspection("CF-MANUAL")
    vals = [1, 1, 0, 1, 1, 1, 1]
    for i, v in enumerate(vals, start=1):
        q.insert_wire_result(inspection_id, i, v)

    # override wire 3 to pass
    q.update_manual_result(inspection_id, 3, 1)

    res = q.compute_final_result(inspection_id)
    assert int(res) == 1
