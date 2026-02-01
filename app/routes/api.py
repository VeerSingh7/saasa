from flask import Blueprint, request, jsonify, current_app
from app.db.queries import get_inspection_by_barcode, create_inspection, get_wire_results_by_inspection
from app.db import database as db
import random

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/validate_qr", methods=["POST"])
def validate_qr():
    data = request.get_json(silent=True) or {}
    qr = data.get("qr_code") or data.get("barcode")
    force = bool(data.get("force_proceed"))

    if not qr:
        return jsonify({"valid": False, "message": "missing qr_code"}), 400

    existing = get_inspection_by_barcode(qr)
    if existing and not force:
        inspection_id = existing["id"] if isinstance(existing, dict) or hasattr(existing, 'keys') else existing[0]
        rows = get_wire_results_by_inspection(inspection_id)
        # convert rows into wireN booleans by final_result if present else ai_result
        record = {}
        for i, r in enumerate(rows, start=1):
            val = r.get("final_result") if r.get("final_result") is not None else r.get("ai_result")
            record[f"wire{i}"] = True if val == 1 else False if val == 0 else None

        # include final result
        record["final_result"] = existing.get("final_result") if isinstance(existing, dict) else None

        return jsonify({"valid": True, "exists": True, "existing_record": record})

    # create new inspection and return its id to the client
    inspection_id = create_inspection(qr)
    return jsonify({"valid": True, "exists": False, "inspection_id": inspection_id})


@api_bp.route("/inspect", methods=["POST"])
def inspect():
    data = request.get_json(silent=True) or {}
    inspection_id = data.get("inspection_id")
    if not inspection_id:
        return jsonify({"error": "missing inspection_id"}), 400

    # Simulate AI detections for 7 wires. In real app, run model and save detections
    detections = []
    failed_wires = []
    for wire in range(1, 8):
        # random pass/fail for demo; favor pass
        passed = random.random() > 0.1
        ai_result = 1 if passed else 0
        detections.append({"wire_id": wire, "color": "black", "ai_result": ai_result})
        if ai_result == 0:
            failed_wires.append({"wire": wire})
        # save wire result
        try:
            db.insert_wire_ai_result(inspection_id, wire, ai_result)
        except Exception:
            current_app.logger.exception("Failed to insert wire ai result")

    status = "PASS" if len(failed_wires) == 0 else "FAIL"

    # annotated_image: point to camera snapshot if camera available else fallback static image
    if current_app.extensions.get("camera_manager"):
        annotated = "/camera/snapshot"
    else:
        annotated = "/static/img/fallback.jpg"

    return jsonify({
        "status": status,
        "detections": detections,
        "failed_wires": failed_wires,
        "annotated_image": annotated
    })


@api_bp.route("/save_manual_results", methods=["POST"])
def save_manual_results():
    data = request.get_json(silent=True) or {}
    inspection_id = data.get("inspection_id")
    if not inspection_id:
        return jsonify({"error": "missing inspection_id"}), 400

    manual = data.get("manual_results") or {}

    # manual is expected as { wireN: true/false }
    for key, val in manual.items():
        if not key.startswith("wire"):
            continue
        try:
            wire_no = int(key.replace("wire", ""))
        except Exception:
            continue
        manual_val = 1 if bool(val) else 0
        try:
            db.update_manual_wire_result(inspection_id, wire_no, manual_val)
        except Exception:
            current_app.logger.exception("Failed to update manual result")

    # finalize if possible
    try:
        final = db.compute_final_result(inspection_id)
        # store final result into inspections if complete
        if final is not None:
            db.finalize_inspection(inspection_id)
    except Exception:
        current_app.logger.exception("Failed to finalize inspection")

    return jsonify({"status": "ok"})
