"""Query helpers that adapt `app.db.database` functions for the UI/routes.

This module provides small read-friendly helpers expected by templates
and routes. It intentionally keeps return values as plain dicts/lists
so templates can iterate and access keys easily.
"""
from typing import Optional, List, Dict
from app.db import database as db
from app.db.database import get_connection
from datetime import datetime


def get_inspection_by_barcode(barcode: str) -> Optional[Dict]:
    """Return the latest inspection row for a barcode as a dict, or None."""
    latest_id = db.get_latest_inspection_id(barcode)
    if latest_id is None:
        return None

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inspections WHERE id = ?", (latest_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def create_inspection(barcode: str, product_type: Optional[str] = None) -> int:
    """Wrapper around database.create_inspection.

    Returns the newly created inspection id.
    """
    return db.create_inspection(barcode, product_type=product_type)


def get_wire_results_by_inspection(inspection_id: int) -> List[Dict]:
    """Return list of wire_result rows (ordered by wire_no) as dicts."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT wire_no, ai_result, manual_result, final_result FROM wire_results WHERE inspection_id = ? ORDER BY wire_no",
        (inspection_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_manual_result(inspection_id: int, wire_no: int, manual_result: int) -> None:
    """Apply manual override for a given wire."""
    db.update_manual_wire_result(inspection_id, wire_no, manual_result)


def insert_wire_result(inspection_id: int, wire_no: int, ai_result: int,
                       confidence=None, image_path=None) -> None:
    """Insert or replace a wire AI result (thin wrapper for tests and routes)."""
    db.insert_wire_ai_result(inspection_id, wire_no, ai_result,
                             confidence=confidence, image_path=image_path)


def compute_final_result(inspection_id: int):
    """Compute final pass/fail for an inspection (None if < 7 wires present)."""
    return db.compute_final_result(inspection_id)


def finalize_inspection(inspection_id: int) -> bool:
    """Finalize inspection and return True for PASS else False.

    Delegates to `database.finalize_inspection`.
    """
    return db.finalize_inspection(inspection_id)

