"""
Proximity-based contextual scorer.
Adjusts candidate entity confidence scores based on nearby positive and negative keywords.
Differentiates between Date of Birth vs statutory filing dates, and Person vs Company names.
Filters regulatory bodies, document headings, and generic business terminology.
"""

import re
from typing import List, Set
from src.detectors.base import EntitySpan


class ContextProximityScorer:
    """Calculates contextual relevance and adjusts candidate span confidences."""

    DOB_POS_PATTERN = re.compile(
        r'\b(?:date\s+of\s+birth|dob|born\s+on|birth\s+date|age|years\s+old|aged|d\.o\.b)\b',
        re.IGNORECASE
    )
    DOB_NEG_PATTERN = re.compile(
        r'\b(?:dated|offer\s+date|filing\s+date|agreement\s+dated|financial\s+year|agm|egm|'
        r'annual\s+general\s+meeting|record\s+date|issue\s+date|allotment\s+date|'
        r'incorporated\s+on|incorporation|effective\s+date|closing\s+date|'
        r'listing\s+date|settlement\s+date|deemed\s+date|board\s+meeting)\b',
        re.IGNORECASE
    )

    PERSON_POS_PATTERN = re.compile(
        r'\b(?:mr\.|ms\.|mrs\.|dr\.|shri|smt\.|promoter|director|managing\s+director|'
        r'compliance\s+officer|company\s+secretary|key\s+managerial|kmp|'
        r'chief\s+executive\s+officer|ceo|cfo|cto|coo|'
        r'contact\s+person|authorized\s+signatory|nominee|partner|'
        r'independent\s+director|whole[\s-]?time\s+director|chairperson|chairman)\b',
        re.IGNORECASE
    )
    PERSON_NEG_PATTERN = re.compile(
        r'\b(?:limited|ltd|pvt|private\s+limited|holdings|corporation|bank|'
        r'ministry|association|statute|act|tribunal|committee|authority|board|'
        r'department|commission|council|exchange|depository|government|'
        r'securities|exchange\s+board|stock\s+exchange)\b',
        re.IGNORECASE
    )

    # Comprehensive set of non-PII terms that should never be redacted
    EXCLUDED_NON_PII: Set[str] = {
        # Document types
        "red herring prospectus", "prospectus", "draft red herring prospectus", "drhp", "rhp",
        # Generic corporate & procedural roles
        "company", "our company", "the company", "your company",
        "board", "board of directors", "audit committee", "committee",
        "nomination and remuneration committee", "stakeholders relationship committee",
        "unauthorized user", "user", "customer", "employee", "employees",
        "shareholder", "shareholders", "promoter", "promoters",
        "director", "directors", "managing director", "independent director",
        "reader", "bidders", "bidder", "investors", "investor", "anchor investors",
        "management", "senior management", "kmp", "officer", "compliance officer",
        "company secretary", "secretary", "secretaries", "auditors", "auditor",
        "members", "member", "report", "care report", "crisil report",
        # Regulatory bodies
        "sebi", "securities and exchange board of india",
        "rbi", "reserve bank of india", "reserve bank",
        "bse", "bse limited", "bombay stock exchange",
        "nse", "nse limited", "national stock exchange", "national stock exchange of india limited",
        "mca", "ministry of corporate affairs", "roc", "registrar of companies",
        "nclt", "national company law tribunal", "clb", "company law board",
        "nsdl", "national securities depository limited",
        "cdsl", "central depository services (india) limited", "central depository services limited",
        "irdai", "gst", "income tax department",
        "government of india", "government of maharashtra", "central government", "state government",
        "supreme court", "high court", "bombay high court", "delhi high court",
        "icai", "icsi", "bis", "european union", "united nations",
        # Financial & market terms
        "book running lead managers", "brlms", "lead managers", "syndicate members",
        "upi", "asba", "scsb", "ind as", "indian gaap", "us gaap", "ifrs",
        "shares", "equity shares", "fresh issue", "offer for sale",
        "table of contents", "notice", "general information", "risk factors",
        "our business", "objects of the offer", "basis for the offer price",
        "third party industry sources", "industry research report",
        "india", "standard time", "indian standard time",
    }

    def __init__(self, window_size: int = 80):
        self.window_size = window_size
        self._excluded_set = {r.lower() for r in self.EXCLUDED_NON_PII}

    def _is_excluded(self, text: str) -> bool:
        """Checks if the entity text matches a known non-PII term."""
        text_clean = text.strip().lower()
        if text_clean in self._excluded_set:
            return True
        for excl in self._excluded_set:
            if text_clean == excl:
                return True
        return False

    def score_and_adjust(self, spans: List[EntitySpan], full_text: str) -> List[EntitySpan]:
        """
        Examines surrounding text window for each span and updates confidence.
        Filters out non-PII terms, false positive dates, and low-confidence entities.
        """
        adjusted_spans: List[EntitySpan] = []

        for span in spans:
            # 0. Filter non-PII terms
            if self._is_excluded(span.text):
                continue

            window_start = max(0, span.start - self.window_size)
            window_end = min(len(full_text), span.end + self.window_size)
            window_text = full_text[window_start:window_end]

            conf = span.confidence

            # 1. Date of Birth logic
            if span.type == "DATE_OF_BIRTH":
                has_pos = bool(self.DOB_POS_PATTERN.search(window_text))
                has_neg = bool(self.DOB_NEG_PATTERN.search(window_text))

                if has_pos and not has_neg:
                    conf = min(1.0, conf + 0.35)
                elif has_neg:
                    conf = max(0.0, conf - 0.60)
                else:
                    conf = max(0.0, conf - 0.45)

            # 2. Person Name logic
            elif span.type == "PERSON":
                span_lower = span.text.lower()
                if any(kw in span_lower for kw in ["limited", "ltd", "pvt", "holdings", "llp", "corporation"]):
                    span.type = "ORGANIZATION"
                    if self._is_excluded(span.text):
                        continue
                elif len(span.text.strip()) < 3:
                    continue
                else:
                    has_pos = bool(self.PERSON_POS_PATTERN.search(window_text))
                    has_neg = bool(self.PERSON_NEG_PATTERN.search(window_text))
                    if has_pos:
                        conf = min(1.0, conf + 0.20)
                    if has_neg and not has_pos:
                        conf = max(0.0, conf - 0.25)

            # 3. Organization logic
            elif span.type == "ORGANIZATION":
                org_lower = span.text.lower()
                if any(kw in org_lower for kw in ["limited", "ltd", "pvt", "holdings", "bank"]):
                    conf = min(1.0, conf + 0.20)
                elif len(span.text.strip()) < 4:
                    continue

            span.confidence = round(conf, 3)

            if span.type == "DATE_OF_BIRTH" and span.confidence < 0.50:
                continue
            if span.type == "ORGANIZATION" and span.confidence < 0.45:
                continue

            adjusted_spans.append(span)

        return adjusted_spans
