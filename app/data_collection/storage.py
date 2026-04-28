"""Storage abstraction for collected inspection data.

FilesystemStorage is the concrete implementation used on edge devices.
Future cloud backends (S3Storage, GCSStorage) can be dropped in by
implementing the Storage protocol.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Protocol every storage backend must satisfy."""

    def write_bytes(self, relative_path: str, data: bytes) -> None: ...
    def write_json(self, relative_path: str, obj: dict) -> None: ...
    def read_json(self, relative_path: str) -> dict: ...
    def list(self, prefix: str = "") -> Iterator[str]: ...
    def exists(self, relative_path: str) -> bool: ...


class FilesystemStorage:
    """Stores collected samples on the local filesystem.

    All paths are relative to `root`.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative_path: str, data: bytes) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def write_json(self, relative_path: str, obj: dict) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(obj, indent=2))

    def read_json(self, relative_path: str) -> dict:
        target = self.root / relative_path
        if not target.exists():
            return {}
        return json.loads(target.read_text())

    def list(self, prefix: str = "") -> Iterator[str]:
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return
        for p in base.rglob("*"):
            if p.is_file():
                yield str(p.relative_to(self.root))

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()


# ---------------------------------------------------------------------------
# Cloud stub — plug-in point for future cloud backends
# ---------------------------------------------------------------------------

class CloudStorage:
    """Stub for a future cloud storage backend (S3, GCS, Azure Blob).

    Replace the body with a real implementation; the interface matches Storage.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        raise NotImplementedError(
            "CloudStorage is not implemented yet. "
            "Use FilesystemStorage and sync the data directory manually or "
            "with a separate upload script."
        )

    def write_bytes(self, relative_path: str, data: bytes) -> None: ...
    def write_json(self, relative_path: str, obj: dict) -> None: ...
    def read_json(self, relative_path: str) -> dict: ...
    def list(self, prefix: str = "") -> Iterator[str]: ...
    def exists(self, relative_path: str) -> bool: ...
