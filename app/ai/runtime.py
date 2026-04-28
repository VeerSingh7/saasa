"""Thin inference runtime abstraction.

Supports ONNX Runtime (default, edge-safe) and PyTorch (dev/training boxes only).
The edge device should always use backend="onnx" — no torch dependency required.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)


class InferenceRuntime(Protocol):
    """Shared interface every backend must satisfy."""

    def run(self, image: np.ndarray) -> list[np.ndarray]:
        """Run the model on a pre-processed image array.

        Args:
            image: float32 NCHW or NHWC array depending on the model.

        Returns:
            List of output tensors as numpy arrays.
        """
        ...

    @property
    def input_name(self) -> str: ...
    @property
    def input_shape(self) -> tuple[int, ...]: ...


# ---------------------------------------------------------------------------
# ONNX Runtime backend
# ---------------------------------------------------------------------------

class OnnxRuntime:
    """ONNX Runtime inference backend.  Works on CPU / ARM without PyTorch."""

    def __init__(self, model_path: str | Path) -> None:
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ImportError("onnxruntime is required: pip install onnxruntime") from e

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

        opts = ort.SessionOptions()
        opts.log_severity_level = 3  # suppress verbose ONNX RT logs
        self._session = ort.InferenceSession(str(path), sess_options=opts)
        self._input_meta = self._session.get_inputs()[0]
        log.info("Loaded ONNX model %s  input=%s %s",
                 path.name, self._input_meta.name, self._input_meta.shape)

    def run(self, image: np.ndarray) -> list[np.ndarray]:
        outputs = self._session.run(None, {self._input_meta.name: image})
        return outputs

    @property
    def input_name(self) -> str:
        return self._input_meta.name

    @property
    def input_shape(self) -> tuple[int, ...]:
        return tuple(self._input_meta.shape)


# ---------------------------------------------------------------------------
# PyTorch backend (dev / training boxes only — not for edge)
# ---------------------------------------------------------------------------

class PytorchRuntime:
    """PyTorch inference backend for development use.

    Falls back gracefully if torch is not installed.
    """

    def __init__(self, model_path: str | Path) -> None:
        try:
            import torch
        except ImportError as e:
            raise ImportError("torch is required for the pytorch backend: "
                              "use onnx backend on edge devices.") from e

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"PyTorch model not found: {path}")

        self._model = torch.load(str(path), map_location="cpu")
        self._model.eval()
        self._torch = torch
        log.info("Loaded PyTorch model %s", path.name)

    def run(self, image: np.ndarray) -> list[np.ndarray]:
        import torch
        t = torch.from_numpy(image)
        with torch.no_grad():
            out = self._model(t)
        if isinstance(out, (list, tuple)):
            return [o.numpy() for o in out]
        return [out.numpy()]

    @property
    def input_name(self) -> str:
        return "input"

    @property
    def input_shape(self) -> tuple[int, ...]:
        return ()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_runtime(model_path: str | Path, backend: str = "onnx") -> OnnxRuntime | PytorchRuntime:
    """Instantiate the correct backend from a model path + backend name."""
    b = backend.lower()
    if b == "onnx":
        return OnnxRuntime(model_path)
    if b == "pytorch":
        return PytorchRuntime(model_path)
    raise ValueError(f"Unknown inference backend: {backend!r}. Choose 'onnx' or 'pytorch'.")
