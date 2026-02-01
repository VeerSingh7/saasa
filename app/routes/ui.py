from flask import Blueprint, render_template, request, redirect, url_for
from app.db.queries import (
    get_inspection_by_barcode,
    create_inspection,
    get_wire_results_by_inspection,
    update_manual_result,
    finalize_inspection
)

ui_bp = Blueprint("ui", __name__)

@ui_bp.route("/", methods=["GET", "POST"])
def barcode():
    if request.method == "POST":
        barcode = request.form["barcode"].strip()

        inspection = get_inspection_by_barcode(barcode)

        if inspection:
            return redirect(url_for("ui.inspection", inspection_id=inspection["id"]))
        else:
            inspection_id = create_inspection(barcode)
            return redirect(url_for("ui.inspection", inspection_id=inspection_id))

    return render_template("barcode.html")

@ui_bp.route("/inspection/<int:inspection_id>", methods=["GET", "POST"])
def inspection(inspection_id):
    if request.method == "POST":
        for wire_no in range(1, 8):
            key = f"wire_{wire_no}"
            if key in request.form:
                update_manual_result(
                    inspection_id,
                    wire_no,
                    int(request.form[key])
                )

        final_result = finalize_inspection(inspection_id)
    else:
        final_result = None

    wires = get_wire_results_by_inspection(inspection_id)

    return render_template(
        "inspection.html",
        inspection_id=inspection_id,
        wires=wires,
        final_result=final_result
    )

