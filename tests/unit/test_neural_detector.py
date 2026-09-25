"""
Unit test for GlinerDetector.
"""

import pytest
from src.detectors.neural.gliner_detector import GlinerDetector


@pytest.fixture(scope="module")
def gliner_detector():
    return GlinerDetector(model_path="models/gliner_multi_pii")


def test_gliner_person_and_org(gliner_detector):
    text = "The Key Managerial Personnel is Sarthak Malvadkar representing KSH International Limited."
    spans = gliner_detector.detect(text)

    types = {s.type for s in spans}
    assert "PERSON" in types
    assert "ORGANIZATION" in types

    person_spans = [s for s in spans if s.type == "PERSON"]
    assert any("Sarthak" in s.text for s in person_spans)

    org_spans = [s for s in spans if s.type == "ORGANIZATION"]
    assert any("KSH" in s.text for s in org_spans)
