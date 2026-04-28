from flask import Blueprint, request, jsonify, current_app
from app.db.queries import get_inspection_by_barcode, create_inspection, get_wire_results_by_inspection
from app.db import database as db

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
        inspection_id = existing["id"] if isinstance(existing, dict) or hasattr(existing, "keys") else existing[0]
        rows = get_wire_results_by_inspection(inspection_id)
        record = {}
        for i, r in enumerate(rows, start=1):
            val = r.get("final_result") if r.get("final_result") is not None else r.get("ai_result")
            record[f"wire{i}"] = True if val == 1 else False if val == 0 else None
        record["final_result"] = existing.get("final_result") if isinstance(existing, dict) else None
        return jsonify({"valid": True, "exists": True, "existing_record": record})

    inspection_id = create_inspection(qr)
    return jsonify({"valid": True, "exists": False, "inspection_id": inspection_id})


@api_bp.route("/inspect", methods=["POST"])
def inspect():
    data = request.get_json(silent=True) or {}
    inspection_id = data.get("inspection_id")
    if not inspection_id:
        return jsonify({"error": "missing inspection_id"}), 400

    # Resolve ModelService + DataCollector from app extensions
    model_service = current_app.extensions.get("model_service")
    data_collector = current_app.extensions.get("data_collector")

    if model_service is None:
        return jsonify({"error": "model service not initialised"}), 503

    from app.services.inspection_service import InspectionService, InspectionError

    # Acquire camera frame if camera is available
    cam = current_app.extensions.get("camera_manager")
    frame_bgr = cam.get_frame() if cam is not None else None

    # For testing without a camera, accept a base64-encoded image in the request
    if frame_bgr is None and data.get("image_b64"):
        import base64
        import numpy as np
        import cv2
        try:
            img_bytes = base64.b64decode(data["image_b64"])
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            current_app.logger.exception("Failed to decode image_b64")

    svc = InspectionService(model_service, data_collector)

    # Retrieve barcode from the inspection row for data collection metadata
    barcode = ""
    try:
        conn = db.get_connection()
        row = conn.execute("SELECT barcode FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        conn.close()
        if row:
            barcode = row["barcode"]
    except Exception:
        pass

    try:
        result = svc.run(inspection_id, frame_bgr, barcode=barcode)
    except InspectionError as exc:
        current_app.logger.warning("Inspection %s failed: %s", inspection_id, exc)
        return jsonify({"error": "no model loaded", "detail": str(exc)}), 503

    return jsonify(result)


@api_bp.route("/save_manual_results", methods=["POST"])
def save_manual_results():
    data = request.get_json(silent=True) or {}
    inspection_id = data.get("inspection_id")
    if not inspection_id:
        return jsonify({"error": "missing inspection_id"}), 400

    manual = data.get("manual_results") or {}
    manual_overrides: dict[int, int] = {}

    for key, val in manual.items():
        if not key.startswith("wire"):
            continue
        try:
            wire_no = int(key.replace("wire", ""))
        except Exception:
            continue
        manual_val = 1 if bool(val) else 0
        manual_overrides[wire_no] = manual_val
        try:
            db.update_manual_wire_result(inspection_id, wire_no, manual_val)
        except Exception:
            current_app.logger.exception("Failed to update manual result")

    final: int | None = None
    try:
        computed = db.compute_final_result(inspection_id)
        if computed is not None:
            db.finalize_inspection(inspection_id)
            final = int(computed)
    except Exception:
        current_app.logger.exception("Failed to finalize inspection")

    # Patch the collected sample's metadata with the human-verified final result
    if final is not None:
        data_collector = current_app.extensions.get("data_collector")
        if data_collector is not None:
            try:
                data_collector.patch_final_result(
                    inspection_id, final,
                    manual_overrides={str(k): v for k, v in manual_overrides.items()},
                )
            except Exception:
                current_app.logger.exception("Failed to patch collected metadata")

    return jsonify({"status": "ok"})
