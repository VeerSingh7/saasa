"""Public DB API for the application.

This module re-exports the read-friendly helpers from `app.db.queries` so
other modules can import `from app.db import get_inspection_by_barcode` etc.
Keep low-level `database.py` internal to `app.db`.
"""
from .queries import (
    get_inspection_by_barcode,
    create_inspection,
    get_wire_results_by_inspection,
    insert_wire_result,
    update_manual_result,
    finalize_inspection,
)

__all__ = [
    "get_inspection_by_barcode",
    "create_inspection",
    "get_wire_results_by_inspection",
    "insert_wire_result",
    "update_manual_result",
    "finalize_inspection",
]
