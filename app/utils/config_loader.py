"""YAML configuration loader with defaults and environment-variable overrides."""
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("pyyaml is required: pip install pyyaml")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load(name: str, defaults: dict | None = None) -> dict:
    """Load a config YAML file from app/config/<name>.yaml.

    Values in the file override `defaults`; environment variables of the form
    SAASA_<UPPER_KEY> override the file (top-level keys only).
    """
    cfg: dict[str, Any] = dict(defaults or {})
    cfg.update(_load_yaml(_CONFIG_DIR / f"{name}.yaml"))

    prefix = "SAASA_"
    for key in list(cfg.keys()):
        env_key = prefix + key.upper()
        if env_key in os.environ:
            cfg[key] = os.environ[env_key]

    return cfg
