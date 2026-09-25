"""
Unit tests for RegexDetector and validators.
"""

import pytest
from src.detectors.regex.recognizers import RegexDetector
from src.detectors.regex.validators import validate_luhn, validate_phone_number


def test_regex_detector_email_and_ip():
    detector = RegexDetector()
    text = "Send alerts to compliance@kshgroup.com or admin@192.168.1.100. Server IP is 10.0.0.1."
    spans = detector.detect(text)

    types = {s.type for s in spans}
    assert "EMAIL" in types
    assert "IP_ADDRESS" in types

    email_spans = [s for s in spans if s.type == "EMAIL"]
    assert len(email_spans) == 1
    assert email_spans[0].text == "compliance@kshgroup.com"
    assert text[email_spans[0].start:email_spans[0].end] == "compliance@kshgroup.com"

    ip_spans = [s for s in spans if s.type == "IP_ADDRESS"]
    assert any(s.text == "10.0.0.1" for s in ip_spans)


def test_regex_detector_credit_card_luhn():
    detector = RegexDetector()
    # 4012 8888 8888 1881 is a valid test Visa card passing Luhn
    valid_card = "4012 8888 8888 1881"
    invalid_card = "4012 8888 8888 1882"
    assert validate_luhn(valid_card) is True
    assert validate_luhn(invalid_card) is False

    text = f"Primary Card: {valid_card}, Bad Card: {invalid_card}"
    spans = detector.detect(text)
    card_spans = [s for s in spans if s.type == "CREDIT_CARD"]
    assert len(card_spans) == 1
    assert card_spans[0].text == valid_card


def test_regex_detector_phone_vs_financial_values():
    detector = RegexDetector()
    text = "Contact Tel: +91 9876543210 or 020-25531234. Total Offer: ₹4,500,000 equity shares at ₹10 each."
    spans = detector.detect(text)

    phone_spans = [s for s in spans if s.type == "PHONE"]
    phone_texts = [s.text for s in phone_spans]
    assert "+91 9876543210" in phone_texts or "9876543210" in "".join(phone_texts)

    # Ensure financial numbers like 4,500,000 are NOT detected as phones
    for s in spans:
        assert "4,500,000" not in s.text
        assert "₹" not in s.text


def test_regex_detector_pan_and_ssn():
    detector = RegexDetector()
    # 4th character 'P' indicates Person for Indian PAN
    text = "Promoter PAN: ABCPE1234F. US Tax ID: 123-45-6789."
    spans = detector.detect(text)

    pan_spans = [s for s in spans if s.metadata.get("sub_type") == "INDIAN_PAN"]
    assert len(pan_spans) == 1
    assert pan_spans[0].text == "ABCPE1234F"

    ssn_spans = [s for s in spans if s.metadata.get("sub_type") == "US_SSN"]
    assert len(ssn_spans) == 1
    assert ssn_spans[0].text == "123-45-6789"
