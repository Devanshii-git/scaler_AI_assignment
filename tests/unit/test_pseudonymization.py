"""
Unit tests for Cryptographic key manager and Pseudonym Synthesizer.
"""

import pytest
from src.pseudonymization.crypto import CryptoKeyManager
from src.pseudonymization.synthesizer import PseudonymSynthesizer
from src.detectors.regex.validators import validate_luhn, validate_email_address, validate_ip_address


def test_crypto_vault_roundtrip():
    km = CryptoKeyManager()
    token = km.generate_entity_token("PERSON", "Rajesh Kushal Hegde")
    assert isinstance(token, str) and len(token) == 64

    km.store_in_vault(token, "Rajesh Kushal Hegde")
    decrypted = km.retrieve_from_vault(token)
    assert decrypted == "Rajesh Kushal Hegde"


def test_pseudonym_synthesizer_determinism():
    synth = PseudonymSynthesizer()

    name = "Rajesh Kushal Hegde"
    pseudo1 = synth.get_or_create_pseudonym("PERSON", name)
    pseudo2 = synth.get_or_create_pseudonym("PERSON", name)

    # Must be completely identical across calls
    assert pseudo1 == pseudo2
    assert isinstance(pseudo1, str)
    assert pseudo1 != name


def test_pseudonym_synthesizer_distinctness():
    synth = PseudonymSynthesizer()

    pseudo1 = synth.get_or_create_pseudonym("PERSON", "Rajesh Hegde")
    pseudo2 = synth.get_or_create_pseudonym("PERSON", "Sarthak Malvadkar")

    assert pseudo1 != pseudo2


def test_pseudonym_format_validity():
    synth = PseudonymSynthesizer()

    email_pseudo = synth.get_or_create_pseudonym("EMAIL", "test@real.com")
    assert validate_email_address(email_pseudo) is True

    card_pseudo = synth.get_or_create_pseudonym("CREDIT_CARD", "4012888888881881")
    assert validate_luhn(card_pseudo) is True

    ip_pseudo = synth.get_or_create_pseudonym("IP_ADDRESS", "192.168.1.50")
    assert validate_ip_address(ip_pseudo) is True
