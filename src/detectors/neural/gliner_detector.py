"""
Neural PII Detector using GLiNER models.
Extracts open-vocabulary entities (PERSON, ORGANIZATION, ADDRESS, DATE_OF_BIRTH)
with exact character boundaries, honorific normalization, and non-PII suppression.
Includes single-text and high-performance batched inference.
"""

import os
import re
import uuid
from typing import List, Optional, Dict, Any, Set
import torch
from gliner import GLiNER
from src.detectors.base import BaseDetector, EntitySpan


class GlinerDetector(BaseDetector):
    """Deep neural span-extractor using GLiNER PII architecture with batching support."""

    LABEL_MAPPING = {
        "person": "PERSON",
        "name": "PERSON",
        "individual": "PERSON",
        "organization": "ORGANIZATION",
        "company": "ORGANIZATION",
        "corporate": "ORGANIZATION",
        "address": "ADDRESS",
        "physical address": "ADDRESS",
        "date of birth": "DATE_OF_BIRTH",
        "dob": "DATE_OF_BIRTH",
    }

    HONORIFIC_PATTERN = re.compile(
        r'^(?:Mr\.|Ms\.|Mrs\.|Dr\.|Shri|Smt\.)\s*',
        re.IGNORECASE
    )

    NON_PII_TERMS: Set[str] = {
        "company", "our company", "the company", "your company",
        "board", "board of directors", "audit committee", "committee",
        "unauthorized user", "user", "customer", "employee", "employees",
        "shareholder", "shareholders", "promoter", "promoters",
        "director", "directors", "managing director", "independent director",
        "reader", "bidders", "bidder", "investors", "investor", "anchor investors",
        "management", "senior management", "kmp", "officer", "compliance officer",
        "company secretary", "secretary", "secretaries", "auditors", "auditor",
        "members", "member", "report", "care report", "crisil report",
        "prospectus", "red herring prospectus", "draft red herring prospectus",
        "act", "companies act", "sebi", "rbi", "bse", "nse", "mca", "roc",
        "regulations", "sebi icdr regulations", "icdr",
        "shares", "equity shares", "fresh issue", "offer for sale",
        "government", "central government", "state government", "ministry",
        "bank", "statute", "union", "european union", "securities", "exchange",
        "india", "indian", "standard time", "indian standard time",
        "book running lead managers", "brlms", "lead managers", "syndicate members",
        "upi", "asba", "ind as", "indian gaap", "us gaap", "ifrs",
        "table of contents", "notice", "general information", "risk factors",
        "our business", "objects of the offer", "basis for the offer price",
        "third party industry sources", "industry research report"
    }

    MAX_WINDOW_CHARS = 350

    def __init__(
        self,
        model_path: str = "models/gliner_multi_pii",
        labels: Optional[List[str]] = None,
        threshold: float = 0.55,
        device: Optional[str] = None
    ):
        self._model_path = model_path
        self._labels = labels or [
            "person",
            "organization",
            "company",
            "address",
            "date of birth",
        ]
        self._threshold = threshold
        self._device = device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._load_model()

    def _load_model(self):
        """Loads model checkpoint from local directory or Hugging Face cache."""
        try:
            self._model = GLiNER.from_pretrained(self._model_path)
            self._model.to(self._device)
            self._model.eval()
        except Exception:
            alt_path = "urchade/gliner_multi_pii-v1"
            self._model = GLiNER.from_pretrained(alt_path)
            self._model.to(self._device)
            self._model.eval()

    @property
    def detector_id(self) -> str:
        return "gliner_detector"

    def _clean_and_filter_entity(self, ent: Dict[str, Any], base_offset: int = 0) -> Optional[EntitySpan]:
        """Cleans and filters a raw GLiNER entity prediction."""
        raw_label = ent.get("label", "").lower()
        mapped_type = self.LABEL_MAPPING.get(raw_label)
        if mapped_type is None:
            return None

        ent_text = ent.get("text", "")
        start = ent.get("start", 0) + base_offset
        end = ent.get("end", 0) + base_offset
        score = float(ent.get("score", 0.0))

        while ent_text and ent_text[-1] in " ,;.:\t\n":
            ent_text = ent_text[:-1]
            end -= 1

        while ent_text and ent_text[0] in " \t\n":
            ent_text = ent_text[1:]
            start += 1

        if mapped_type == "PERSON":
            hon_match = self.HONORIFIC_PATTERN.match(ent_text)
            if hon_match:
                prefix_len = hon_match.end()
                ent_text = ent_text[prefix_len:]
                start += prefix_len

        if ent_text.strip().lower() in self.NON_PII_TERMS:
            return None

        if mapped_type in ["PERSON", "ORGANIZATION"] and len(ent_text.strip()) < 3:
            return None

        if mapped_type == "ORGANIZATION":
            words = ent_text.strip().split()
            if len(words) == 1 and not any(kw in ent_text.lower() for kw in ["limited", "ltd", "pvt"]):
                return None

        return EntitySpan(
            entity_id=str(uuid.uuid4()),
            type=mapped_type,
            text=ent_text,
            start=start,
            end=end,
            confidence=score,
            detector_sources=[self.detector_id],
            metadata={"raw_label": raw_label}
        )

    def detect(self, text: str, block_context: Optional[Dict[str, Any]] = None) -> List[EntitySpan]:
        """Runs neural span extraction on a single text."""
        if not text or len(text.strip()) < 4:
            return []

        try:
            raw_entities = self._model.predict_entities(
                text,
                self._labels,
                threshold=self._threshold
            )
        except Exception:
            return []

        spans: List[EntitySpan] = []
        for ent in raw_entities:
            span = self._clean_and_filter_entity(ent)
            if span:
                spans.append(span)
        return spans

    def detect_batch(self, texts: List[str], batch_size: int = 32) -> List[List[EntitySpan]]:
        """
        Runs neural span extraction across a batch of texts for high throughput.
        Uses vectorized batched inference in PyTorch.
        """
        if not texts:
            return []

        try:
            batch_raw = self._model.batch_predict_entities(
                texts,
                self._labels,
                threshold=self._threshold,
                batch_size=batch_size
            )
        except Exception:
            return [self.detect(t) for t in texts]

        results: List[List[EntitySpan]] = []
        for raw_list in batch_raw:
            spans = []
            for ent in raw_list:
                span = self._clean_and_filter_entity(ent)
                if span:
                    spans.append(span)
            results.append(spans)
        return results
