from flask import Blueprint, request, jsonify
from app.db.queries import get_inspection_by_barcode, create_inspection


barcode_bp = Blueprint("barcode", __name__, url_prefix="/barcode")


@barcode_bp.route("/check", methods=["POST"])
def check_barcode():
    """Check barcode existence and return inspection status.

    Request JSON: { "barcode": "..." }
    Response JSON: { "status": "existing"|"new", "barcode": "...", "inspection_id": int|null }
    """
    data = request.get_json(silent=True) or {}
    barcode = data.get("barcode")
    if not barcode:
        return jsonify({"error": "missing barcode"}), 400

    inspection = get_inspection_by_barcode(barcode)
    if inspection:
        return jsonify({
            "status": "existing",
            "barcode": barcode,
            "inspection_id": inspection["id"] if isinstance(inspection, dict) or hasattr(inspection, 'keys') else inspection[0]
        })

    # create a new inspection and return its id
    inspection_id = create_inspection(barcode)
    return jsonify({"status": "new", "barcode": barcode, "inspection_id": inspection_id})
