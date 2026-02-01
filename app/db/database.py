"""
Database module for AI Inspection System
Supports:
- Multiple detections per inspection
- Wire-level AI + manual override
- Final inspection result calculation
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------------
# Database path (kept OUTSIDE code bundle / exe)
# ------------------------------------------------------------------
DB_PATH = Path("data/local/inspection_data.db")


# ------------------------------------------------------------------
# Connection
# ------------------------------------------------------------------
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
 

# ------------------------------------------------------------------
# Initialize Database
# ------------------------------------------------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------
    # Inspections (1 per barcode scan)
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT NOT NULL,
        product_type TEXT,
        inspection_time DATETIME DEFAULT CURRENT_TIMESTAMP,

        final_result INTEGER,           -- 1 = PASS, 0 = FAIL
        override_used INTEGER DEFAULT 0,

        yolo_model_version TEXT,
        classifier_model_version TEXT,

        synced INTEGER DEFAULT 0
    )
    """)

    # -------------------------
    # YOLO Detections (many per inspection)
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_id INTEGER,
        detection_index INTEGER,
        class_name TEXT,
        confidence REAL,

        bbox_x REAL,
        bbox_y REAL,
        bbox_w REAL,
        bbox_h REAL,

        FOREIGN KEY (inspection_id) REFERENCES inspections(id)
    )
    """)

    # -------------------------
    # Wire-level Results (wire1–7)
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wire_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_id INTEGER,
        wire_no INTEGER CHECK(wire_no BETWEEN 1 AND 7),

        ai_result INTEGER,          -- 1 = PASS, 0 = FAIL
        manual_result INTEGER,      -- NULL if not overridden
        final_result INTEGER,       -- manual if exists else ai

        confidence REAL,
        image_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (inspection_id) REFERENCES inspections(id),
        UNIQUE (inspection_id, wire_no)
    )
    """)

    # -------------------------
    # Barcode History (fast duplicate check)
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS barcode_history (
        barcode TEXT PRIMARY KEY,
        first_seen DATETIME,
        last_seen DATETIME,
        inspection_count INTEGER DEFAULT 1
    )
    """)

    conn.commit()
    # Ensure optional columns exist for backward compatibility
    _ensure_wire_results_columns()

    conn.close()


def _ensure_wire_results_columns():
    """Ensure wire_results has optional columns added by newer code.

    This will ALTER TABLE to add columns if they do not exist. Safe to call
    multiple times.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(wire_results)")
    existing = {row[1] for row in cursor.fetchall()}  # row[1] is name

    # Columns we expect in newer schema
    additions = [
        ("confidence", "REAL"),
        ("image_path", "TEXT"),
        ("created_at", "DATETIME")
    ]

    for col, coltype in additions:
        if col not in existing:
            try:
                cursor.execute(f"ALTER TABLE wire_results ADD COLUMN {col} {coltype}")
            except Exception:
                # best effort: ignore errors (e.g., concurrent schema change)
                pass

    conn.commit()
    conn.close()


def create_inspection(barcode, product_type=None,
                      yolo_model="model_yolo.pt",
                      classifier_model="model_cls.pth"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO inspections (
            barcode, product_type,
            yolo_model_version, classifier_model_version
        )
        VALUES (?, ?, ?, ?)
    """, (barcode, product_type, yolo_model, classifier_model))

    inspection_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO barcode_history (barcode, first_seen, last_seen, inspection_count)
        VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
        ON CONFLICT(barcode) DO UPDATE SET
            last_seen = CURRENT_TIMESTAMP,
            inspection_count = inspection_count + 1
    """, (barcode,))

    conn.commit()
    conn.close()
    return inspection_id

def insert_detection(inspection_id, detection_index,
                     class_name, confidence, bbox):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO detections (
            inspection_id, detection_index,
            class_name, confidence,
            bbox_x, bbox_y, bbox_w, bbox_h
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inspection_id,
        detection_index,
        class_name,
        confidence,
        bbox[0], bbox[1], bbox[2], bbox[3]
    ))

    conn.commit()
    conn.close()
def insert_wire_ai_result(inspection_id, wire_no, ai_result):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO wire_results (
            inspection_id, wire_no,
            ai_result, final_result
        )
        VALUES (?, ?, ?, ?)
    """, (
        inspection_id,
        wire_no,
        int(ai_result),
        int(ai_result)
    ))

    conn.commit()
    conn.close()
def update_manual_wire_result(inspection_id, wire_no, manual_result):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE wire_results SET
            manual_result = ?,
            final_result = ?
        WHERE inspection_id = ? AND wire_no = ?
    """, (
        int(manual_result),
        int(manual_result),
        inspection_id,
        wire_no
    ))

    cursor.execute("""
        UPDATE inspections SET override_used = 1
        WHERE id = ?
    """, (inspection_id,))

    conn.commit()
    conn.close()


def is_barcode_already_scanned(barcode):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT inspection_count FROM barcode_history
        WHERE barcode = ?
    """, (barcode,))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_latest_inspection_id(barcode):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM inspections
        WHERE barcode = ?
        ORDER BY inspection_time DESC
        LIMIT 1
    """, (barcode,))

    row = cursor.fetchone()
    conn.close()

    return row["id"] if row else None

def finalize_inspection(inspection_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MIN(COALESCE(manual_result, ai_result)) AS final_result
        FROM wire_results
        WHERE inspection_id = ?
    """, (inspection_id,))

    row = cursor.fetchone()

    if row is None or row["final_result"] is None:
        conn.close()
        raise ValueError("Wire results incomplete for inspection")

    final_pass = int(row["final_result"])

    cursor.execute("""
        UPDATE inspections
        SET final_result = ?,
            override_used = CASE
                WHEN EXISTS (
                    SELECT 1 FROM wire_results
                    WHERE inspection_id = ?
                      AND manual_result IS NOT NULL
                )
                THEN 1 ELSE 0
            END
        WHERE id = ?
    """, (final_pass, inspection_id, inspection_id))

    conn.commit()
    conn.close()

    return bool(final_pass)
def compute_final_result(inspection_id):
    """
    Computes final inspection result using pure SQL.

    Rule:
    - Use manual_result if present, else ai_result
    - All 7 wires must be present
    - Final result = AND of all wire results
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            CASE
                WHEN COUNT(*) < 7 THEN NULL
                ELSE MIN(COALESCE(manual_result, ai_result))
            END AS final_result
        FROM wire_results
        WHERE inspection_id = ?
    """, (inspection_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    # final_result will be:
    # 1 -> PASS
    # 0 -> FAIL
    # None -> INCOMPLETE
    return row["final_result"]


