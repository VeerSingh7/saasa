"""Camera manager for safe capture in background thread.

Place this file in `app/camera/manager.py` and import `CameraManager`
from your Flask app to create a singleton instance that serves frames
to routes.

Usage:
    from app.camera.manager import CameraManager
    cam = CameraManager(source=0, width=640, height=480)
    jpeg = cam.get_jpeg()
    cam.stop()

The manager keeps a background thread that reads frames and stores the
latest JPEG bytes. It will attempt to re-open the camera on failure and
optionally load a fallback image.
"""
from __future__ import annotations

import threading
import time
import logging
from typing import Optional
from pathlib import Path

import cv2

log = logging.getLogger(__name__)


class CameraManager:
    def __init__(
        self,
        source: int | str = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fallback_image: Optional[str] = None,
        reopen_interval: float = 5.0,
    ) -> None:
        self.source = source
        self.width = int(width) if width is not None else None
        self.height = int(height) if height is not None else None
        self.fallback_image = Path(fallback_image) if fallback_image else None
        self.reopen_interval = float(reopen_interval)

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._capture: Optional[cv2.VideoCapture] = None
        self._frame = None  # latest BGR frame
        self._jpeg: Optional[bytes] = None
        self._thread = threading.Thread(target=self._run, daemon=True)

        self._thread.start()

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        try:
            cap = cv2.VideoCapture(self.source, cv2.CAP_ANY)
            if self.width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.width))
            if self.height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.height))
            if not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
                raise RuntimeError(f"VideoCapture could not open source {self.source}")
            log.info("Opened camera source %s", self.source)
            return cap
        except Exception:
            log.exception("Failed to open camera %s", self.source)
            return None

    def _read_frame(self, cap: cv2.VideoCapture):
        if not cap:
            return None
        ret, frame = cap.read()
        if not ret or frame is None:
            return None
        return frame

    def _encode_jpeg(self, frame) -> Optional[bytes]:
        try:
            ret, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ret:
                return None
            return buf.tobytes()
        except Exception:
            log.exception("Failed to encode JPEG")
            return None

    def _load_fallback_jpeg(self) -> Optional[bytes]:
        if not self.fallback_image or not self.fallback_image.exists():
            return None
        try:
            img = cv2.imread(str(self.fallback_image))
            if img is None:
                return None
            return self._encode_jpeg(img)
        except Exception:
            log.exception("Failed to load fallback image")
            return None

    def _run(self) -> None:
        last_open_attempt = 0.0
        while not self._stop.is_set():
            if self._capture is None or not getattr(self._capture, 'isOpened', lambda: False)():
                now = time.time()
                if now - last_open_attempt >= self.reopen_interval:
                    last_open_attempt = now
                    cap = self._open_capture()
                    if cap:
                        with self._lock:
                            self._capture = cap
                    else:
                        fallback = self._load_fallback_jpeg()
                        if fallback:
                            with self._lock:
                                self._jpeg = fallback
                        time.sleep(self.reopen_interval)
                        continue
                else:
                    time.sleep(0.1)
                    continue

            try:
                frame = self._read_frame(self._capture)
                if frame is None:
                    with self._lock:
                        try:
                            if self._capture:
                                self._capture.release()
                        except Exception:
                            pass
                        self._capture = None
                    time.sleep(0.5)
                    continue

                jpeg = self._encode_jpeg(frame)
                with self._lock:
                    self._frame = frame
                    self._jpeg = jpeg
            except Exception:
                log.exception("Error in camera loop")
                with self._lock:
                    try:
                        if self._capture:
                            self._capture.release()
                    except Exception:
                        pass
                    self._capture = None
                time.sleep(1.0)

    def get_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return None if self._jpeg is None else bytes(self._jpeg)

    def get_frame(self):
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            try:
                if self._capture:
                    self._capture.release()
            except Exception:
                pass
            self._capture = None
        self._thread.join(timeout=1.0)
