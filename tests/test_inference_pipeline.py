"""Tests for the inference pipeline using a stub runtime (no real models needed)."""
from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Stub runtime — canned detection output
# ---------------------------------------------------------------------------

class _StubDetectorRuntime:
    """Returns a fixed set of 7 wire bounding-box outputs.

    Output format matches YOLOv8 ONNX: (1, 4+nc, num_anchors).
    num_anchors must exceed num_features (5) so the transpose heuristic works.
    """

    input_name = "images"
    input_shape = (1, 3, 640, 640)

    def run(self, image):
        # 7 high-confidence anchors + padding with zero confidence (filtered out)
        anchors = []
        for i in range(7):
            anchors.append([100.0, 50.0 + i * 50, 40.0, 30.0, 0.9])
        # padding — keeps num_anchors > num_features so heuristic fires correctly
        for _ in range(10):
            anchors.append([0.0, 0.0, 0.0, 0.0, 0.0])
        arr = np.array(anchors, dtype=np.float32).T     # (5, 17)
        return [arr.reshape(1, 5, -1)]


class _StubClassifierRuntime:
    """Always returns [ok=0.85, fail=0.15] — all wires pass."""

    input_name = "input"
    input_shape = (1, 3, 224, 224)

    def run(self, image):
        return [np.array([[0.85, 0.15]], dtype=np.float32)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline():
    from app.ai.detector.yolo import WireDetector
    from app.ai.classifier.classifier import WireClassifier
    from app.ai.inference_pipeline import InferencePipeline

    detector = WireDetector.__new__(WireDetector)
    detector._runtime = _StubDetectorRuntime()
    detector._input_w = detector._input_h = 640
    detector._conf_thresh = 0.4
    detector._iou_thresh = 0.45
    detector._num_wires = 7
    detector._sort_by = "top_to_bottom"

    classifier = WireClassifier.__new__(WireClassifier)
    classifier._runtime = _StubClassifierRuntime()
    classifier._input_w = classifier._input_h = 224
    classifier._classes = ["ok", "fail"]
    classifier._conf_thresh = 0.5

    return InferencePipeline(detector, classifier, num_wires=7)


@pytest.fixture
def dummy_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pipeline_returns_seven_results(pipeline, dummy_frame):
    results = pipeline.run(dummy_frame)
    assert len(results) == 7


def test_wire_numbers_are_one_indexed(pipeline, dummy_frame):
    results = pipeline.run(dummy_frame)
    assert [r.wire_no for r in results] == list(range(1, 8))


def test_all_wires_pass_with_stub(pipeline, dummy_frame):
    results = pipeline.run(dummy_frame)
    assert all(r.ai_result == 1 for r in results)


def test_confidence_values_in_range(pipeline, dummy_frame):
    results = pipeline.run(dummy_frame)
    for r in results:
        assert 0.0 <= r.confidence <= 1.0


def test_crop_bytes_produced(pipeline, dummy_frame):
    results = pipeline.run(dummy_frame)
    # At least detected wires should have crop bytes
    assert any(len(r.crop_bytes) > 0 for r in results)


def test_missing_wire_is_conservative_fail(dummy_frame):
    """If detector finds fewer than num_wires, missing wires become FAIL."""
    from app.ai.detector.yolo import WireDetector
    from app.ai.classifier.classifier import WireClassifier
    from app.ai.inference_pipeline import InferencePipeline

    class _FewDetectionsRuntime:
        input_name = "images"
        input_shape = (1, 3, 640, 640)

        def run(self, image):
            # 3 high-confidence anchors + padding so num_anchors > num_features
            anchors = [[100.0, 50.0 + i * 50, 40.0, 30.0, 0.9] for i in range(3)]
            for _ in range(10):
                anchors.append([0.0, 0.0, 0.0, 0.0, 0.0])
            arr = np.array(anchors, dtype=np.float32).T
            return [arr.reshape(1, 5, -1)]

    detector = WireDetector.__new__(WireDetector)
    detector._runtime = _FewDetectionsRuntime()
    detector._input_w = detector._input_h = 640
    detector._conf_thresh = 0.4
    detector._iou_thresh = 0.45
    detector._num_wires = 7
    detector._sort_by = "top_to_bottom"

    classifier = WireClassifier.__new__(WireClassifier)
    classifier._runtime = _StubClassifierRuntime()
    classifier._input_w = classifier._input_h = 224
    classifier._classes = ["ok", "fail"]
    classifier._conf_thresh = 0.5

    pipeline = InferencePipeline(detector, classifier, num_wires=7)
    results = pipeline.run(dummy_frame)

    assert len(results) == 7
    # Wires 4–7 (indices 3–6) should be FAIL since no detection
    for r in results[3:]:
        assert r.ai_result == 0
        assert r.confidence == 0.0
