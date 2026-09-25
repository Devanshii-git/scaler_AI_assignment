"""
Regex PII Detector with algorithmic validation.
Detects EMAIL, PHONE, CREDIT_CARD, IP_ADDRESS, SSN_TAX_ID, DIN, CIN, and GSTIN.
Returns unmutated candidate EntitySpan objects.
"""

import re
import uuid
from typing import List, Optional, Dict, Any
from src.detectors.base import BaseDetector, EntitySpan
from src.detectors.regex.validators import (
    validate_luhn,
    validate_ip_address,
    validate_phone_number,
    validate_email_address,
    validate_us_ssn,
    validate_indian_pan,
)


class RegexDetector(BaseDetector):
    """Regex-based detector strictly paired with algorithmic validators."""

    def __init__(self):
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        )
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.ipv6_pattern = re.compile(
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        )
        self.credit_card_pattern = re.compile(
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b|\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b'
        )
        # Indian and International Phone Patterns
        # Note: Do NOT use \b before + because space and + are both non-word characters!
        self.phone_pattern = re.compile(
            r'(?:(?<=[\s:;,(\-])|^)(?:\+\s*91|0091|91)?[-\s]?[6-9]\d{9}\b|'                      # Indian mobile
            r'(?:(?<=[\s:;,(\-])|^)\+\s*91\s+\d{2}\s+\d{4}\s+\d{4}\b|'                           # + 91 20 4505 3237
            r'\b0\d{2,4}[-\s]?\d{6,8}\b|'                                                        # Landline with STD
            r'(?:(?<=[\s:;,(\-])|^)\+[1-9]\d{0,2}[-\s]?(?:\(\d{1,4}\)|\d{1,4})[-\s]?\d{3,4}[-\s]?\d{3,4}\b'  # Intl
        )
        self.us_ssn_pattern = re.compile(
            r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b'
        )
        self.indian_pan_pattern = re.compile(
            r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
        )
        self.din_pattern = re.compile(
            r'(?:DIN|Director\s+Identification\s+Number)\s*[:\-]?\s*(\d{8})\b',
            re.IGNORECASE
        )
        self.cin_pattern = re.compile(
            r'\b[UL]\d{5}[A-Z]{2}\d{4}(?:PLC|PTC|FLC|GAP|NPL|OPC|GOI|FGN)\d{6}\b'
        )
        self.gstin_pattern = re.compile(
            r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z0-9][A-Z0-9]\b'
        )

    @property
    def detector_id(self) -> str:
        return "regex_detector"

    def detect(self, text: str, block_context: Optional[Dict[str, Any]] = None) -> List[EntitySpan]:
        """Scans text, applies regex patterns, executes algorithmic validation, and outputs spans."""
        spans: List[EntitySpan] = []

        # 1. Email Addresses
        for match in self.email_pattern.finditer(text):
            val = match.group()
            start = match.start()
            end = match.end()
            # Trim
            while val and val[-1] in " ,;.:":
                val = val[:-1]
                end -= 1
            if validate_email_address(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="EMAIL",
                    text=val,
                    start=start,
                    end=end,
                    confidence=0.99,
                    detector_sources=[self.detector_id]
                ))

        # 2. IP Addresses (IPv4 & IPv6)
        for match in self.ip_pattern.finditer(text):
            val = match.group()
            if validate_ip_address(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="IP_ADDRESS",
                    text=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.98,
                    detector_sources=[self.detector_id]
                ))

        for match in self.ipv6_pattern.finditer(text):
            val = match.group()
            if validate_ip_address(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="IP_ADDRESS",
                    text=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.98,
                    detector_sources=[self.detector_id]
                ))

        # 3. Credit Cards (with Luhn check)
        for match in self.credit_card_pattern.finditer(text):
            val = match.group()
            if validate_luhn(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="CREDIT_CARD",
                    text=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    detector_sources=[self.detector_id]
                ))

        # 4. Phone Numbers (with phonenumbers validation)
        for match in self.phone_pattern.finditer(text):
            val = match.group().strip()
            start = match.start()
            end = match.end()
            # Adjust start if leading space
            matched_raw = text[start:end]
            leading_spaces = len(matched_raw) - len(matched_raw.lstrip())
            start += leading_spaces
            trailing_spaces = len(matched_raw) - len(matched_raw.rstrip())
            end -= trailing_spaces

            # Trim trailing punctuation
            while val and val[-1] in " ,;.:":
                val = val[:-1]
                end -= 1

            if re.match(r'^(?:19|20)\d{2}$', val):
                continue

            prefix_ctx = text[max(0, start - 10):start]
            if any(sym in prefix_ctx for sym in ['\u20b9', 'Rs', '$', '\u20ac', '%', 'INR', 'USD']):
                continue
            suffix_ctx = text[end:min(len(text), end + 15)].lower()
            if any(kw in suffix_ctx for kw in ['crore', 'lakh', 'million', 'billion', 'lac', ' cr', ' mn']):
                continue
            if any(kw in prefix_ctx.lower() for kw in ['#', 'no.', 'number', 'order', 'ticket', 'sr.', 'cin', 'din']):
                continue

            if validate_phone_number(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="PHONE",
                    text=val,
                    start=start,
                    end=end,
                    confidence=0.96,
                    detector_sources=[self.detector_id]
                ))

        # 5. US SSN
        for match in self.us_ssn_pattern.finditer(text):
            val = match.group()
            if validate_us_ssn(val):
                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="SSN_TAX_ID",
                    text=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    detector_sources=[self.detector_id],
                    metadata={"sub_type": "US_SSN"}
                ))

        # 6. Indian PAN
        for match in self.indian_pan_pattern.finditer(text):
            val = match.group()
            if validate_indian_pan(val):
                if self.cin_pattern.search(text[max(0, match.start()-3):min(len(text), match.end()+10)]):
                    continue
                if self.gstin_pattern.search(text[max(0, match.start()-3):min(len(text), match.end()+5)]):
                    continue

                spans.append(EntitySpan(
                    entity_id=str(uuid.uuid4()),
                    type="SSN_TAX_ID",
                    text=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    detector_sources=[self.detector_id],
                    metadata={"sub_type": "INDIAN_PAN"}
                ))

        # 7. DIN (Director Identification Number)
        for match in self.din_pattern.finditer(text):
            val = match.group(1)
            spans.append(EntitySpan(
                entity_id=str(uuid.uuid4()),
                type="SSN_TAX_ID",
                text=val,
                start=match.start(1),
                end=match.end(1),
                confidence=0.93,
                detector_sources=[self.detector_id],
                metadata={"sub_type": "DIN"}
            ))

        return spans
