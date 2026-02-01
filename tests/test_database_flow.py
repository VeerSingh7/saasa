import importlib.util
import os
from pathlib import Path

# Import the database module by path to avoid importing the top-level `app`
# package which may execute application initialization code at import time.
spec = importlib.util.spec_from_file_location(
    "database",
    str(Path(__file__).resolve().parents[1] / "app" / "db" / "database.py")
)
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)


def main():
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
    pass_result = db.finalize_inspection(inspection_id2)
    assert pass_result is False

    # 6) Apply manual override to wire 3 to change it to PASS
    db.update_manual_wire_result(inspection_id2, 3, manual_result=1)

    # Re-finalize and expect PASS now
    final_pass2 = db.finalize_inspection(inspection_id2)
    assert final_pass2 is True

    print("DB flow test completed successfully")


if __name__ == "__main__":
    main()
