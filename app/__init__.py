"""Flask application factory."""
from pathlib import Path

from flask import Flask
from jinja2 import FileSystemLoader


def create_app(test_config=None):
    project_root = Path(__file__).resolve().parents[1]

    app = Flask(
        __name__,
        static_folder=str(project_root / "static"),
    )
    app.secret_key = app.config.get("SECRET_KEY", "dev-secret-key")
    app.jinja_loader = FileSystemLoader(str(project_root / "templates"))

    if test_config:
        app.config.update(test_config)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    from app.utils.logger import setup_logging
    from app.utils.config_loader import load as load_cfg
    app_cfg = load_cfg("app_config", defaults={
        "log_level": "INFO",
        "log_file": None,
        "models_dir": "models",
        "data_dir": "data",
        "inference_backend": "onnx",
    })
    setup_logging(app_cfg.get("log_level", "INFO"), app_cfg.get("log_file"))

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    try:
        from app.db import database as _db
        _db.init_db()
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Model service (lazy — loads on first /api/inspect call)
    # ------------------------------------------------------------------
    models_dir = project_root / app_cfg.get("models_dir", "models")
    from app.services.model_service import ModelService
    model_service = ModelService(
        models_dir=models_dir,
        backend=app_cfg.get("inference_backend", "onnx"),
    )
    app.extensions = getattr(app, "extensions", {})
    app.extensions["model_service"] = model_service

    # ------------------------------------------------------------------
    # Data collector (async background writer)
    # ------------------------------------------------------------------
    dc_cfg = load_cfg("data_collection_config", defaults={
        "enabled": True,
        "mode": "all",
        "low_conf_threshold": 0.7,
        "max_queue": 256,
        "retention_days": 30,
        "storage_root": "data/collected",
    })
    if not test_config and dc_cfg.get("enabled", True):
        from app.data_collection.storage import FilesystemStorage
        from app.data_collection.collector import DataCollector
        storage_root = project_root / dc_cfg.get("storage_root", "data/collected")
        storage = FilesystemStorage(storage_root)
        collector = DataCollector(
            storage=storage,
            mode=dc_cfg.get("mode", "all"),
            low_conf_threshold=float(dc_cfg.get("low_conf_threshold", 0.7)),
            max_queue=int(dc_cfg.get("max_queue", 256)),
            retention_days=int(dc_cfg.get("retention_days", 30)),
        )
        app.extensions["data_collector"] = collector

        @app.teardown_appcontext
        def _stop_collector(exception=None):
            try:
                collector.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from app.routes.barcode import barcode_bp
    from app.routes.inspection import inspection_bp
    from app.routes.ui import ui_bp
    from app.routes.camera import camera_bp
    from app.routes.api import api_bp

    app.register_blueprint(barcode_bp)
    app.register_blueprint(inspection_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp)

    # ------------------------------------------------------------------
    # Camera (optional)
    # ------------------------------------------------------------------
    cam_cfg = app_cfg.get("camera", {})
    enable_camera = (
        app.config.get("ENABLE_CAMERA", False)
        or (isinstance(cam_cfg, dict) and cam_cfg.get("enabled", False))
    )
    if enable_camera:
        camera_cfg = {**cam_cfg, **(app.config.get("CAMERA") or {})}
        fallback = camera_cfg.get("fallback_image") or str(
            project_root / "static" / "img" / "fallback.jpg"
        )
        from app.camera.manager import CameraManager
        cam = CameraManager(
            source=camera_cfg.get("source", 0),
            width=camera_cfg.get("width", 640),
            height=camera_cfg.get("height", 480),
            fallback_image=fallback,
            reopen_interval=float(camera_cfg.get("reopen_interval", 5.0)),
        )
        app.extensions["camera_manager"] = cam
        app.register_blueprint(camera_bp)

        @app.teardown_appcontext
        def _stop_camera(exception=None):
            try:
                cam.stop()
            except Exception:
                pass

    return app
