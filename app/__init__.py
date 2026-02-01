"""Flask application factory.

Provides create_app() so other modules can import the package without
triggering app wiring at import time.
"""
from flask import Flask
from pathlib import Path
from jinja2 import ChoiceLoader, FileSystemLoader


def create_app(test_config=None):
	"""Create and configure the Flask application.

	- Registers blueprints from `app.routes`
	- Config can be extended via `test_config` dict
	"""
	# Configure template/static folders to point to top-level dirs
	# Support templates placed either at project-level `templates/` or
	# package-local `app/templates/`. Prefer project-level first so a
	# top-level templates/ directory overrides package templates.
	project_root = Path(__file__).resolve().parents[1]
	this_dir = Path(__file__).resolve().parent

	# Serve static files from project-level `static/` so root static assets
	# are available to the app and templates.
	app = Flask(
		__name__,
		static_folder=str(project_root / "static"),
	)

	# Secret key for session usage in API endpoints; override via config
	app.secret_key = app.config.get("SECRET_KEY", "dev-secret-key")

	# Configure Jinja loader to use project-level templates only to avoid
	# ambiguity between `templates/` and `app/templates/`.
	app.jinja_loader = FileSystemLoader(str(project_root / "templates"))

	if test_config:
		app.config.update(test_config)

	# Ensure database initialized so routes can create/read rows without
	# requiring manual init during development.
	try:
		from app.db import database as _db
		_db.init_db()
	except Exception:
		# best-effort: don't crash app creation if DB initialization fails
		pass

	# Register blueprints
	from app.routes.barcode import barcode_bp
	from app.routes.inspection import inspection_bp
	from app.routes.ui import ui_bp
	from app.routes.camera import camera_bp  # camera blueprint is optional and will be registered below if enabled
	from app.routes.api import api_bp

	app.register_blueprint(barcode_bp)
	app.register_blueprint(inspection_bp)
	app.register_blueprint(ui_bp)
	app.register_blueprint(api_bp)
	# Note: we serve static files from top-level `static/`. Keep package-local
	# `app/static/` as a source-of-truth, but avoid serving it separately to
	# reduce path confusion.

	# Camera manager: optional. Enable via app.config['ENABLE_CAMERA']=True and
	# provide settings under app.config['CAMERA'] (dict). Default is disabled.
	if app.config.get("ENABLE_CAMERA", False):
		# safe defaults for camera settings
		camera_cfg = app.config.get("CAMERA", {})
		project_root = Path(__file__).resolve().parents[1]
		fallback = camera_cfg.get("fallback_image") or str(project_root / "static" / "img" / "fallback.jpg")
		from app.camera.manager import CameraManager
		cam = CameraManager(
			source=camera_cfg.get("source", 0),
			width=camera_cfg.get("width", 640),
			height=camera_cfg.get("height", 480),
			fallback_image=fallback,
			reopen_interval=camera_cfg.get("reopen_interval", 5.0),
		)
		app.extensions = getattr(app, "extensions", {})
		app.extensions["camera_manager"] = cam
		app.register_blueprint(camera_bp)

		# Ensure the camera is stopped on app shutdown
		@app.teardown_appcontext
		def _stop_camera(exception=None):
			try:
				cam.stop()
			except Exception:
				pass

	# end if ENABLE_CAMERA

	return app
