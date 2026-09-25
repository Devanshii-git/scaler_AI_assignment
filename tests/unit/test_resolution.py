"""
Unit tests for Candidate Aggregator and Conflict Resolver.
"""

import pytest
from src.detectors.base import EntitySpan
from src.resolution.conflict_resolver import ConflictResolver


def test_conflict_resolver_org_containing_person():
    resolver = ConflictResolver()

    # "Rajesh Hegde Transport Private Limited" (start 0, end 38)
    org_span = EntitySpan(
        entity_id="e_org",
        type="ORGANIZATION",
        text="Rajesh Hegde Transport Private Limited",
        start=0,
        end=38,
        confidence=0.90
    )
    # "Rajesh Hegde" (start 0, end 12)
    person_span = EntitySpan(
        entity_id="e_person",
        type="PERSON",
        text="Rajesh Hegde",
        start=0,
        end=12,
        confidence=0.88
    )

    resolved = resolver.resolve([person_span, org_span])
    assert len(resolved) == 1
    assert resolved[0].type == "ORGANIZATION"
    assert resolved[0].text == "Rajesh Hegde Transport Private Limited"


def test_conflict_resolver_dedup_and_source_merge():
    resolver = ConflictResolver()

    span1 = EntitySpan(
        entity_id="e1",
        type="EMAIL",
        text="info@ksh.com",
        start=10,
        end=22,
        confidence=0.95,
        detector_sources=["regex_detector"]
    )
    span2 = EntitySpan(
        entity_id="e2",
        type="EMAIL",
        text="info@ksh.com",
        start=10,
        end=22,
        confidence=0.90,
        detector_sources=["neural_detector"]
    )

    resolved = resolver.resolve([span1, span2])
    assert len(resolved) == 1
    assert "regex_detector" in resolved[0].detector_sources
    assert "neural_detector" in resolved[0].detector_sources


def test_conflict_resolver_priority():
    resolver = ConflictResolver()

    # Structured phone span (start 5, end 19)
    phone_span = EntitySpan(
        entity_id="e_phone",
        type="PHONE",
        text="+91 9876543210",
        start=5,
        end=19,
        confidence=0.95
    )
    # Generic entity span overlapping partially (start 0, end 10)
    misc_span = EntitySpan(
        entity_id="e_misc",
        type="ORGANIZATION",
        text="Call +91 9",
        start=0,
        end=10,
        confidence=0.50
    )

    resolved = resolver.resolve([misc_span, phone_span])
    assert len(resolved) == 1
    assert resolved[0].type == "PHONE"
    assert resolved[0].text == "+91 9876543210"
