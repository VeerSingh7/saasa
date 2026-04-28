"""Tests for the data collection module."""
from __future__ import annotations

import json
import time

import pytest


@pytest.fixture
def tmp_storage(tmp_path):
    from app.data_collection.storage import FilesystemStorage
    return FilesystemStorage(tmp_path)


@pytest.fixture
def sample():
    from app.data_collection.collector import CollectionSample
    return CollectionSample(
        inspection_id=99,
        barcode="TEST-001",
        frame_jpeg=b"\xff\xd8\xff\xe0" + b"\x00" * 100,  # fake JPEG header
        wire_results=[
            {"wire_no": i, "ai_result": 1, "confidence": 0.9, "bbox": [0, i * 20, 40, 18]}
            for i in range(1, 8)
        ],
        detector_version="1.0.0",
        classifier_version="1.0.0",
    )


def test_filesystem_storage_write_read(tmp_storage):
    tmp_storage.write_bytes("a/b/test.jpg", b"hello")
    assert tmp_storage.exists("a/b/test.jpg")


def test_filesystem_storage_write_json(tmp_storage):
    tmp_storage.write_json("meta.json", {"foo": 1})
    data = tmp_storage.read_json("meta.json")
    assert data["foo"] == 1


def test_filesystem_storage_list(tmp_storage):
    tmp_storage.write_bytes("dir/a.jpg", b"x")
    tmp_storage.write_bytes("dir/b.jpg", b"y")
    files = list(tmp_storage.list("dir"))
    assert len(files) == 2


def test_collector_writes_to_disk(tmp_storage, sample):
    from app.data_collection.collector import DataCollector
    collector = DataCollector(tmp_storage, max_queue=10, retention_days=0)
    collector.enqueue(sample)
    collector._queue.join()  # wait for writer thread to drain
    collector.stop()

    # frame.jpg and metadata.json must exist under today/<inspection_id>/
    files = list(tmp_storage.list())
    assert any("frame.jpg" in f for f in files)
    assert any("metadata.json" in f for f in files)


def test_collector_metadata_content(tmp_storage, sample):
    from app.data_collection.collector import DataCollector
    from datetime import date
    collector = DataCollector(tmp_storage, max_queue=10, retention_days=0)
    collector.enqueue(sample)
    collector._queue.join()
    collector.stop()

    today = date.today().isoformat()
    meta = tmp_storage.read_json(f"{today}/99/metadata.json")
    assert meta["barcode"] == "TEST-001"
    assert meta["inspection_id"] == 99
    assert meta["detector_version"] == "1.0.0"
    assert len(meta["wires"]) == 7


def test_collector_patch_final_result(tmp_storage, sample):
    from app.data_collection.collector import DataCollector
    from datetime import date
    collector = DataCollector(tmp_storage, max_queue=10, retention_days=0)
    collector.enqueue(sample)
    collector._queue.join()

    collector.patch_final_result(99, final_result=1, manual_overrides={"3": 1})
    collector.stop()

    today = date.today().isoformat()
    meta = tmp_storage.read_json(f"{today}/99/metadata.json")
    assert meta["final_result"] == 1
    assert meta["manual_overrides"]["3"] == 1


def test_collector_low_confidence_mode_filters(tmp_storage):
    from app.data_collection.collector import DataCollector, CollectionSample
    collector = DataCollector(tmp_storage, mode="low_confidence",
                              low_conf_threshold=0.8, max_queue=10, retention_days=0)

    # High confidence sample — should be filtered out
    high_conf = CollectionSample(
        inspection_id=1, barcode="X",
        frame_jpeg=b"x",
        wire_results=[{"wire_no": i, "ai_result": 1, "confidence": 0.95, "bbox": []} for i in range(1, 8)],
    )
    collector.enqueue(high_conf)
    collector._queue.join()

    # Low confidence sample — should be collected
    low_conf = CollectionSample(
        inspection_id=2, barcode="Y",
        frame_jpeg=b"x",
        wire_results=[{"wire_no": 1, "ai_result": 0, "confidence": 0.5, "bbox": []}],
    )
    collector.enqueue(low_conf)
    collector._queue.join()
    collector.stop()

    files = list(tmp_storage.list())
    # Only the low-confidence sample should be on disk
    assert any("2" in f for f in files)
    assert not any("inspection_id" in json.dumps(tmp_storage.read_json(f))
                   and tmp_storage.read_json(f).get("inspection_id") == 1
                   for f in files if f.endswith("metadata.json"))
