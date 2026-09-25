"""
Cryptographic seed derivation and AES-256-GCM memory vault.
Implements HKDF-SHA256 (RFC 5869) and HMAC-SHA256 identity tokens.
"""

import os
import hmac
import hashlib
from typing import Tuple, Dict, Optional
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoKeyManager:
    """Manages master keys, HKDF expansion, and HMAC token generation."""

    def __init__(self, master_key: Optional[bytes] = None, salt: Optional[bytes] = None):
        # Generate or use master key
        self.master_key = master_key or os.urandom(32)
        self.salt = salt or os.urandom(16)
        self.lookup_key, self.vault_key = self._derive_keys()
        self._aesgcm = AESGCM(self.vault_key)
        # Encrypted storage: token -> encrypted_original_bytes
        self._encrypted_vault: Dict[str, bytes] = {}

    def _derive_keys(self) -> Tuple[bytes, bytes]:
        """Derives separate lookup HMAC key and AES-GCM vault key using HKDF-SHA256."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=self.salt,
            info=b"pii-pseudonym-derivation-v1"
        )
        derived = hkdf.derive(self.master_key)
        lookup_key = derived[:32]
        vault_key = derived[32:64]
        return lookup_key, vault_key

    def generate_entity_token(self, entity_type: str, normalized_text: str) -> str:
        """
        Derives an HMAC-SHA256 token from the entity type and text.
        Guarantees that low-entropy PII cannot be reversed via dictionary attacks without the master key.
        """
        canonical_payload = f"{entity_type.upper().strip()}:{normalized_text.lower().strip()}".encode("utf-8")
        h = hmac.new(self.lookup_key, canonical_payload, hashlib.sha256)
        return h.hexdigest()

    def store_in_vault(self, token: str, raw_pii: str):
        """Encrypts original PII with AES-256-GCM before storing under the token."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, raw_pii.encode("utf-8"), token.encode("utf-8"))
        self._encrypted_vault[token] = nonce + ciphertext

    def retrieve_from_vault(self, token: str) -> Optional[str]:
        """Decrypts and returns original PII from the vault."""
        payload = self._encrypted_vault.get(token)
        if not payload or len(payload) < 28:
            return None
        nonce = payload[:12]
        ciphertext = payload[12:]
        try:
            decrypted = self._aesgcm.decrypt(nonce, ciphertext, token.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception:
            return None
