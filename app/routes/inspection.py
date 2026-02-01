from flask import Blueprint, request, jsonify

inspection_bp = Blueprint(
    "inspection",
    __name__,
    url_prefix="/inspection"
)

@inspection_bp.route("/start", methods=["POST"])
def start_inspection():
    return jsonify({
        "status": "inspection_started"
    })
