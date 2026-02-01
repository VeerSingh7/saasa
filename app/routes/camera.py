from flask import Blueprint, current_app, Response, stream_with_context
import time

camera_bp = Blueprint("camera", __name__, url_prefix="/camera")


@camera_bp.route("/snapshot", methods=["GET"])
def snapshot():
    """Return a single JPEG snapshot from the CameraManager if available.

    Returns 200 with content-type image/jpeg when a frame exists.
    Returns 503 if the camera manager isn't initialized or no frame is available.
    """
    cam = current_app.extensions.get("camera_manager")
    if not cam:
        return ("Camera disabled", 503)

    jpeg = cam.get_jpeg()
    if not jpeg:
        return ("No image available", 503)

    return Response(jpeg, content_type="image/jpeg")


def _mjpeg_generator(cam, interval=0.1):
    """Yield multipart MJPEG frames from the camera manager."""
    while True:
        jpeg = cam.get_jpeg()
        if jpeg:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(interval)


@camera_bp.route("/stream", methods=["GET"])
def stream():
    cam = current_app.extensions.get("camera_manager")
    if not cam:
        return ("Camera disabled", 503)

    return Response(stream_with_context(_mjpeg_generator(cam)),
                    mimetype="multipart/x-mixed-replace; boundary=frame")
