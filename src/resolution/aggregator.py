"""
Candidate aggregator.
Collects and indexes candidate spans from multiple heterogeneous detection sources.
"""

from typing import List, Dict, Any, Optional
from src.detectors.base import EntitySpan, BaseDetector


class CandidateAggregator:
    """Aggregates candidate spans from multiple detectors."""

    def __init__(self, detectors: Optional[List[BaseDetector]] = None):
        self.detectors = detectors or []

    def add_detector(self, detector: BaseDetector):
        self.detectors.append(detector)

    def collect_candidates(self, text: str, block_context: Optional[Dict[str, Any]] = None) -> List[EntitySpan]:
        """Runs all registered detectors on the text and pools candidate spans."""
        all_spans: List[EntitySpan] = []
        for det in self.detectors:
            try:
                spans = det.detect(text, block_context)
                all_spans.extend(spans)
            except Exception as e:
                # Detector error logging can be hooked here; continue gracefully
                continue
        return all_spans
