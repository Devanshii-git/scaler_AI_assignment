"""
Document-Aware Dynamic Entity Registry.
Constructs an in-memory document-level entity symbol table from high-confidence
detections in structured prospectus sections and propagates them consistently across the document.
Strictly guards against registering non-PII, single-word nouns, or generic corporate roles.
"""

import re
import uuid
from typing import Dict, List, Set, Optional, Any, Tuple
from src.detectors.base import EntitySpan


class DocumentEntityRegistry:
    """Ephemeral document-level entity memory and alias propagator."""

    # Regulatory bodies, procedural terms, and document types that should never be registered
    EXCLUDED_ENTITIES: Set[str] = {
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

    def __init__(self, min_seed_confidence: float = 0.85, min_name_length: int = 4):
        self.min_seed_confidence = min_seed_confidence
        self.min_name_length = min_name_length
        self.registered_entities: Dict[str, Dict[str, Any]] = {}
        self._compiled_patterns: List[Dict[str, Any]] = []
        self._alias_map: Dict[str, Tuple[str, str]] = {}
        self._master_regex: Optional[re.Pattern] = None
        self._dirty: bool = False

    def reset(self):
        """Clears registry to ensure complete isolation between document runs."""
        self.registered_entities.clear()
        self._compiled_patterns.clear()
        self._alias_map.clear()
        self._master_regex = None
        self._dirty = False

    def _is_excluded(self, text: str) -> bool:
        """Checks if entity text matches excluded regulatory bodies or generic terms."""
        text_lower = text.strip().lower()
        if text_lower in self.EXCLUDED_ENTITIES:
            return True
        if text.strip().isupper() and len(text.strip()) <= 4:
            return True
        return False

    def register_candidate(self, span: EntitySpan):
        """Registers a high-confidence entity if eligible."""
        if span.confidence < self.min_seed_confidence:
            return
        if span.type not in ["PERSON", "ORGANIZATION"]:
            return

        clean_text = span.text.strip()
        canonical = re.sub(r'^(?:Mr\.|Ms\.|Mrs\.|Dr\.|Shri|Smt\.)\s*', '', clean_text, flags=re.IGNORECASE).strip()

        if len(canonical) < self.min_name_length:
            return

        if self._is_excluded(canonical):
            return

        tokens = canonical.split()
        # For PERSON: must have at least 2 tokens (First + Last Name)
        if span.type == "PERSON" and len(tokens) < 2:
            return

        # For ORGANIZATION: must have at least 2 tokens or end with a legal form
        if span.type == "ORGANIZATION":
            has_legal_suffix = any(
                canonical.lower().endswith(s)
                for s in ["limited", "ltd", "ltd.", "private limited", "pvt ltd", "pvt. ltd.", "llp", "trust"]
            )
            if len(tokens) < 2 and not has_legal_suffix:
                return

        if canonical not in self.registered_entities:
            aliases = self._generate_aliases(canonical, span.type)
            self.registered_entities[canonical] = {
                "canonical": canonical,
                "type": span.type,
                "aliases": aliases,
                "seed_id": span.entity_id
            }
            self._compile_pattern(canonical, span.type, aliases)

    def _generate_aliases(self, canonical: str, ent_type: str) -> Set[str]:
        """Generates common variations and titles."""
        aliases = {canonical}
        if ent_type == "PERSON":
            tokens = canonical.split()
            if len(tokens) >= 2:
                # First + Last: "Rajesh Hegde"
                aliases.add(f"{tokens[0]} {tokens[-1]}")
                for prefix in ["Mr.", "Ms.", "Mrs.", "Dr.", "Shri"]:
                    aliases.add(f"{prefix} {tokens[-1]}")
                    aliases.add(f"{prefix} {canonical}")
                    aliases.add(f"{prefix} {tokens[0]} {tokens[-1]}")
                if len(tokens) == 3:
                    aliases.add(f"{tokens[0]} {tokens[1][0]}. {tokens[2]}")
        elif ent_type == "ORGANIZATION":
            if "Limited" in canonical:
                aliases.add(canonical.replace("Limited", "Ltd"))
                aliases.add(canonical.replace("Limited", "Ltd."))
            if "Private Limited" in canonical:
                aliases.add(canonical.replace("Private Limited", "Pvt. Ltd."))
                aliases.add(canonical.replace("Private Limited", "Pvt Ltd"))
                aliases.add(canonical.replace("Private Limited", "Pvt. Ltd"))
            if "Private" in canonical:
                aliases.add(canonical.replace("Private", "Pvt."))
                aliases.add(canonical.replace("Private", "Pvt"))
        return aliases

    def _compile_pattern(self, canonical: str, ent_type: str, aliases: Set[str]):
        """Compiles boundary-safe regular expressions for all aliases."""
        filtered_aliases = {a for a in aliases if len(a) >= 5}
        if not filtered_aliases:
            return

        for a in filtered_aliases:
            self._alias_map[a.lower()] = (canonical, ent_type)
        self._dirty = True

        sorted_aliases = sorted(filtered_aliases, key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        pattern_str = r'\b(?:' + '|'.join(escaped) + r')\b'
        compiled = re.compile(pattern_str, re.IGNORECASE)
        self._compiled_patterns.append({
            "canonical": canonical,
            "type": ent_type,
            "regex": compiled
        })

    def propagate_to_text(self, text: str, existing_spans: List[EntitySpan]) -> List[EntitySpan]:
        """
        Scans text for registered entity aliases using unified single-pass regex.
        Returns new spans for any occurrences not already covered.
        """
        if not self._alias_map or not text:
            return []

        if self._dirty or self._master_regex is None:
            sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)
            escaped = [re.escape(a) for a in sorted_aliases]
            pattern_str = r'\b(?:' + '|'.join(escaped) + r')\b'
            self._master_regex = re.compile(pattern_str, re.IGNORECASE)
            self._dirty = False

        propagated_spans: List[EntitySpan] = []

        for match in self._master_regex.finditer(text):
            m_start, m_end = match.start(), match.end()
            matched_text = match.group()
            matched_lower = matched_text.lower()
            if matched_lower not in self._alias_map:
                continue

            canonical, ent_type = self._alias_map[matched_lower]

            # Check if this interval overlaps with any existing span
            is_covered = any(
                max(m_start, s.start) < min(m_end, s.end)
                for s in existing_spans + propagated_spans
            )

            if not is_covered:
                propagated_spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type=ent_type,
                    text=matched_text,
                    start=m_start,
                    end=m_end,
                    confidence=0.90,
                    detector_sources=["document_entity_registry"],
                    metadata={"canonical": canonical, "propagated": True}
                ))

        return propagated_spans
