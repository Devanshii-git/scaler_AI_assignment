"""
Contextual Multi-line Address Detector.
Identifies physical and registered office addresses by detecting address anchors,
geographical indicators, postal PIN codes, and expanding to terminal delimiters.
"""

import re
import uuid
from typing import List, Optional, Dict, Any
from src.detectors.base import BaseDetector, EntitySpan


class ContextualAddressDetector(BaseDetector):
    """Detects multi-line address blocks using anchor cues, PIN patterns, and delimiters."""

    ANCHOR_PATTERN = re.compile(
        r'\b(?:registered\s+office|corporate\s+office|head\s+office|principal\s+place\s+of\s+business|'
        r'works|factory|branch\s+office|residence|resident\s+of|residing\s+at|communication\s+address|'
        r'located\s+at|situated\s+at|address)\s*[:\-]',
        re.IGNORECASE
    )

    TERMINAL_PATTERN = re.compile(
        r'(?:\b(?:tel|telephone|phone|mobile|fax|cin|email|website|contact\s+person|director|din|pan)\s*[:\-]|\n\n)',
        re.IGNORECASE
    )

    INDIAN_PIN_PATTERN = re.compile(r'\b[1-9][0-9]{2}\s?[0-9]{3}\b')

    # Pattern to detect organization name at the start of a candidate window
    ORG_PREFIX_PATTERN = re.compile(
        r'^.*?\b(?:Limited|Ltd\.?|Pvt\.?\s*Ltd\.?|Private\s+Limited|Corporation|'
        r'Holdings|Bank|LLP|Partnership|Association|Society)\b[\s,]*',
        re.IGNORECASE
    )

    # Pattern to find address-starting cues in text
    ADDRESS_START_PATTERN = re.compile(
        r'(?:(?:\d+[A-Za-z]?(?:/\d+)*\s*,)|'
        r'\b(?:Plot|Survey|Gat|Unit|Flat|Block|Tower|Floor|Wing|Building|House|'
        r'Shed|Shop|Office|Room|Suite|Level|Sector|Ward|Village|\d+(?:st|nd|rd|th)\s+Floor)\b)',
        re.IGNORECASE
    )

    # State and country tokens that may follow a PIN code
    POST_PIN_TAIL_PATTERN = re.compile(
        r'^(?:[,\s]+(?:Maharashtra|Karnataka|Gujarat|Rajasthan|Tamil\s+Nadu|Delhi|'
        r'Uttar\s+Pradesh|Haryana|Telangana|India|Bharat))*\b',
        re.IGNORECASE
    )

    GEOGRAPHIC_TOKENS = {
        "plot", "survey", "gat", "road", "street", "lane", "marg", "nagar", "sector",
        "industrial", "area", "midc", "phase", "taluka", "district", "village",
        "floor", "building", "complex", "tower", "estate",
        # Indian cities
        "pune", "mumbai", "delhi", "bengaluru", "hyderabad", "chennai", "kolkata",
        "ahmedabad", "nagpur", "thane", "nashik", "jaipur", "lucknow", "noida",
        "gurugram", "gurgaon", "chandigarh",
        # Indian states
        "maharashtra", "karnataka", "gujarat", "rajasthan", "telangana",
        "tamil", "nadu", "kerala", "haryana", "uttar", "pradesh",
        # Localities
        "parel", "worli", "bkc", "andheri", "bandra", "goregaon", "malad",
        "borivali", "powai", "vikhroli", "kurla", "chakan", "khed",
        "hinjewadi", "kharadi", "hadapsar", "wakad", "baner",
        # General address keywords
        "near", "ward", "city", "state", "country", "india",
        "zip", "pin", "post", "office", "flat", "block", "wing",
        "shed", "shop", "unit", "level", "suite"
    }

    @property
    def detector_id(self) -> str:
        return "contextual_address_detector"

    def detect(self, text: str, block_context: Optional[Dict[str, Any]] = None) -> List[EntitySpan]:
        """Detects full address blocks in text."""
        spans: List[EntitySpan] = []

        # 1. Search by explicit Address Anchor
        for anchor_match in self.ANCHOR_PATTERN.finditer(text):
            anchor_end = anchor_match.end()
            address_start = anchor_end
            while address_start < len(text) and text[address_start] in " \t:":
                address_start += 1

            remaining_text = text[address_start:]
            term_match = self.TERMINAL_PATTERN.search(remaining_text)

            if term_match:
                address_end = address_start + term_match.start()
            else:
                newline_pos = remaining_text.find("\n")
                if newline_pos != -1:
                    address_end = address_start + newline_pos
                else:
                    address_end = min(len(text), address_start + 300)

            candidate_addr = text[address_start:address_end]
            # Strip trailing punctuation and whitespace
            while candidate_addr and candidate_addr[-1] in " ,;.:\t\n":
                candidate_addr = candidate_addr[:-1]

            tokens = set(re.findall(r'[a-zA-Z]+', candidate_addr.lower()))
            has_geo = bool(tokens & self.GEOGRAPHIC_TOKENS)
            has_pin = bool(self.INDIAN_PIN_PATTERN.search(candidate_addr))

            if (has_geo or has_pin) and len(candidate_addr) > 12:
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="ADDRESS",
                    text=candidate_addr,
                    start=address_start,
                    end=address_start + len(candidate_addr),
                    confidence=0.95,
                    detector_sources=[self.detector_id],
                    metadata={"source": "anchor_expanded"}
                ))

        # 2. Search around standalone PIN codes if not already covered
        for pin_match in self.INDIAN_PIN_PATTERN.finditer(text):
            p_start, p_end = pin_match.start(), pin_match.end()
            if any(s.start <= p_start and s.end >= p_end for s in spans):
                continue

            back_limit = max(0, p_start - 150)
            window = text[back_limit:p_end]

            tokens = set(re.findall(r'[a-zA-Z]+', window.lower()))
            if len(tokens & self.GEOGRAPHIC_TOKENS) >= 2:
                # Find start
                clause_start = self._find_address_start(text, back_limit, p_start)

                # Determine end: examine what follows the PIN code
                after_pin = text[p_end:min(len(text), p_end + 60)]
                tail_match = self.POST_PIN_TAIL_PATTERN.match(after_pin)
                if tail_match and tail_match.group().strip():
                    clause_end = p_end + tail_match.end()
                else:
                    clause_end = p_end

                addr_text = text[clause_start:clause_end]
                # Trim trailing punctuation and whitespace
                while addr_text and addr_text[-1] in " ,;.:\t\n":
                    addr_text = addr_text[:-1]

                # Trim leading punctuation and whitespace
                while addr_text and addr_text[0] in " ,;:\t\n":
                    addr_text = addr_text[1:]
                    clause_start += 1

                if len(addr_text) > 15:
                    spans.append(EntitySpan(
                        entity_id=str(uuid.uuid4()),
                        type="ADDRESS",
                        text=addr_text,
                        start=clause_start,
                        end=clause_start + len(addr_text),
                        confidence=0.88,
                        detector_sources=[self.detector_id],
                        metadata={"source": "pin_anchored"}
                    ))

        return spans

    def _find_address_start(self, text: str, back_limit: int, pin_start: int) -> int:
        """
        Finds the actual start of an address by scanning backward from the PIN code.
        """
        search_window = text[back_limit:pin_start]

        # Check for prepositions or explicit delimiters first
        prep_matches = list(re.finditer(
            r'\b(?:from|at|in|located\s+at|residing\s+at|resident\s+of|office:?|address:?|situated\s+at)\s+',
            search_window, re.IGNORECASE
        ))
        if prep_matches:
            best_prep = prep_matches[-1]
            return back_limit + best_prep.end()

        # Strategy 2: Look for address start patterns (Flat, Plot, Floor, etc.)
        addr_start_matches = list(self.ADDRESS_START_PATTERN.finditer(search_window))
        if addr_start_matches:
            best_match = addr_start_matches[0]
            return back_limit + best_match.start()

        # Strategy 3: Look for delimiter boundaries
        clause_start = back_limit
        for delim in [":", "\n", ";", "."]:
            pos = text.rfind(delim, back_limit, pin_start)
            if pos != -1:
                start_after = pos + 1
                while start_after < len(text) and text[start_after] in " \t":
                    start_after += 1
                clause_start = max(clause_start, start_after)

        # Strategy 4: Strip organization name prefix
        candidate_text = text[clause_start:pin_start]
        org_match = self.ORG_PREFIX_PATTERN.match(candidate_text)
        if org_match:
            after_org = candidate_text[org_match.end():]
            connector_match = re.match(
                r'\s*(?:operates\s+from|is\s+(?:located|situated)\s+at|having\s+its\s+office\s+at)\s*',
                after_org, re.IGNORECASE
            )
            if connector_match:
                clause_start = clause_start + org_match.end() + connector_match.end()
            else:
                clause_start = clause_start + org_match.end()

        return clause_start
