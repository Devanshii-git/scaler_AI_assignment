"""
Unit tests for Context Engine and Document Entity Registry.
"""

import pytest
from src.detectors.base import EntitySpan
from src.detectors.context.proximity_scorer import ContextProximityScorer
from src.detectors.context.address_detector import ContextualAddressDetector
from src.detectors.context.entity_registry import DocumentEntityRegistry


def test_proximity_scorer_dob_vs_filing_date():
    scorer = ContextProximityScorer()

    # Case 1: True DOB
    text1 = "Director Information: Date of Birth: 15 May 1998. Educational Qualifications: B.Tech."
    span1 = EntitySpan(
        entity_id="s1",
        type="DATE_OF_BIRTH",
        text="15 May 1998",
        start=text1.index("15 May 1998"),
        end=text1.index("15 May 1998") + len("15 May 1998"),
        confidence=0.70
    )
    res1 = scorer.score_and_adjust([span1], text1)
    assert len(res1) == 1
    assert res1[0].confidence > 0.85

    # Case 2: Filing Date (Hard negative)
    text2 = "This Draft Red Herring Prospectus is Dated December 10, 2025 by the Lead Managers."
    span2 = EntitySpan(
        entity_id="s2",
        type="DATE_OF_BIRTH",
        text="December 10, 2025",
        start=text2.index("December 10, 2025"),
        end=text2.index("December 10, 2025") + len("December 10, 2025"),
        confidence=0.70
    )
    res2 = scorer.score_and_adjust([span2], text2)
    # The negative keyword "Dated" penalizes the date below threshold, dropping it
    assert len(res2) == 0


def test_contextual_address_detector():
    detector = ContextualAddressDetector()
    text = (
        "Registered Office: Plot No. 12, Chakan Industrial Area, MIDC Phase II, "
        "Taluka Khed, Pune 410501, Maharashtra, India. "
        "Tel: +91 20 2553 1234; Email: info@ksh.com"
    )
    spans = detector.detect(text)
    assert len(spans) == 1
    addr_span = spans[0]
    assert addr_span.type == "ADDRESS"
    assert "Plot No. 12" in addr_span.text
    assert "Pune 410501" in addr_span.text
    assert "Tel:" not in addr_span.text
    assert text[addr_span.start:addr_span.end] == addr_span.text


def test_document_entity_registry():
    registry = DocumentEntityRegistry(min_seed_confidence=0.85)

    seed_span = EntitySpan(
        entity_id="p1",
        type="PERSON",
        text="Rajesh Kushal Hegde",
        start=0,
        end=19,
        confidence=0.95
    )
    registry.register_candidate(seed_span)

    downstream_text = "The board resolved that Mr. Hegde will oversee operations alongside Rajesh Hegde."
    propagated = registry.propagate_to_text(downstream_text, existing_spans=[])

    prop_texts = {p.text for p in propagated}
    assert "Mr. Hegde" in prop_texts or "Rajesh Hegde" in prop_texts
    for p in propagated:
        assert downstream_text[p.start:p.end] == p.text
