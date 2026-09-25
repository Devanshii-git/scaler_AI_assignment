"""
Seeded deterministic synthetic pseudonym generator.
Replaces detected PII entities with realistic, context-appropriate fake alternatives
while preserving formatting, case, legal suffixes, and the natural readability/essence of the document.
"""

import re
import hashlib
import random
from typing import Dict, Optional, List
from src.pseudonymization.crypto import CryptoKeyManager


class PseudonymSynthesizer:
    """Generates deterministic synthetic alternatives that preserve document essence."""

    CORPORATE_ROOTS: List[str] = [
        "Zenith Precision", "Apex Industrial", "Sterling Technologies",
        "Vanguard Components", "Pinnacle Engineering", "Orbit Technofab",
        "Titan Matrix", "Aura Dynamics", "Nexus Global", "Paramount Alloys",
        "Beacon Systems", "Vertex Solutions", "Solaris Infrastructure"
    ]

    FIRST_NAMES_MALE: List[str] = [
        "Ramesh", "Suresh", "Vikram", "Rajesh", "Sunil", "Anil",
        "Arun", "Deepak", "Manoj", "Pradeep", "Sanjay", "Nikhil", "Alok"
    ]

    FIRST_NAMES_FEMALE: List[str] = [
        "Sunita", "Pooja", "Rekha", "Kavita", "Anita", "Meena", "Shalini", "Rashmi"
    ]

    MIDDLE_NAMES: List[str] = [
        "Chandra", "Kumar", "Prasad", "Narayan", "Kishore", "Mohan", "Kant"
    ]

    LAST_NAMES: List[str] = [
        "Sharma", "Verma", "Mehta", "Patel", "Shah", "Deshmukh",
        "Kulkarni", "Joshi", "Malhotra", "Kapoor", "Agarwal", "Gupta"
    ]

    def __init__(self, key_manager: Optional[CryptoKeyManager] = None):
        self.key_manager = key_manager or CryptoKeyManager()
        self.token_to_pseudonym: Dict[str, str] = {}
        self.pseudonym_to_token: Dict[str, str] = {}
        # Entity-to-family mapping to preserve family surnames among related individuals
        self._surname_cache: Dict[str, str] = {}

    def reset(self):
        """Clears session mappings."""
        self.token_to_pseudonym.clear()
        self.pseudonym_to_token.clear()
        self._surname_cache.clear()

    def get_or_create_pseudonym(self, entity_type: str, raw_text: str) -> str:
        """
        Generates or retrieves a deterministic fake replacement for the given entity.
        Ensures consistent replacement across the document and preserves case and style.
        """
        clean_text = raw_text.strip()
        token = self.key_manager.generate_entity_token(entity_type, clean_text)

        if token in self.token_to_pseudonym:
            return self.token_to_pseudonym[token]

        self.key_manager.store_in_vault(token, clean_text)

        salt_counter = 0
        while True:
            candidate = self._generate_typed_fake(entity_type, clean_text, token, salt_counter)
            if salt_counter > 10:
                candidate = f"{candidate} {salt_counter}"
            existing_token = self.pseudonym_to_token.get(candidate)
            if existing_token is None or existing_token == token or salt_counter > 50:
                self.token_to_pseudonym[token] = candidate
                self.pseudonym_to_token[candidate] = token
                return candidate
            salt_counter += 1

    def _generate_typed_fake(self, entity_type: str, raw_text: str, token: str, salt_counter: int) -> str:
        """Generates a context-appropriate fake alternative matching the entity format."""
        seed_str = f"{token[:12]}_{salt_counter}"
        seed_val = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest()[:8], 16)
        rng = random.Random(seed_val)

        ent_type = entity_type.upper()
        clean = raw_text.strip()

        if ent_type == "PERSON":
            return self._generate_person_name(clean, rng)

        elif ent_type == "ORGANIZATION":
            return self._generate_org_name(clean, rng)

        elif ent_type == "ADDRESS":
            return self._generate_address(clean, rng)

        elif ent_type == "EMAIL":
            return self._generate_email(clean, rng)

        elif ent_type == "PHONE":
            return self._generate_phone(clean, rng)

        elif ent_type == "SSN_TAX_ID":
            return self._generate_tax_id(clean, rng)

        elif ent_type == "DATE_OF_BIRTH":
            return self._generate_dob(rng)

        elif ent_type == "CREDIT_CARD":
            return self._generate_card(rng)

        elif ent_type == "IP_ADDRESS":
            return f"198.51.100.{(seed_val % 250) + 1}"

        else:
            return f"[REDACTED_{ent_type}]"

    def _generate_person_name(self, raw_text: str, rng: random.Random) -> str:
        """Generates a natural Indian name matching token count, gender cues, and case."""
        # Detect honorific
        hon_match = re.match(r'^(Mr\.|Ms\.|Mrs\.|Dr\.|Shri|Smt\.)\s*', raw_text, re.IGNORECASE)
        honorific = hon_match.group(0) if hon_match else ""
        name_body = raw_text[len(honorific):].strip()

        is_female = bool(re.match(r'^(?:Ms\.|Mrs\.|Smt\.)', honorific, re.IGNORECASE))
        tokens = name_body.split()

        first_pool = self.FIRST_NAMES_FEMALE if is_female else self.FIRST_NAMES_MALE
        first_name = rng.choice(first_pool)
        last_name = rng.choice(self.LAST_NAMES)

        if len(tokens) >= 3:
            middle_name = rng.choice(self.MIDDLE_NAMES)
            generated = f"{first_name} {middle_name} {last_name}"
        else:
            generated = f"{first_name} {last_name}"

        full_name = f"{honorific}{generated}" if honorific else generated

        # Match case
        if raw_text.isupper():
            return full_name.upper()
        return full_name

    def _generate_org_name(self, raw_text: str, rng: random.Random) -> str:
        """Generates an industrial company name preserving legal suffix and case."""
        root = rng.choice(self.CORPORATE_ROOTS)

        # Detect legal suffix
        lower = raw_text.lower()
        if "private limited" in lower:
            suffix = "Private Limited"
        elif "pvt. ltd." in lower or "pvt ltd" in lower:
            suffix = "Pvt. Ltd."
        elif "limited" in lower:
            suffix = "Limited"
        elif "ltd." in lower or "ltd" in lower:
            suffix = "Ltd."
        elif "llp" in lower:
            suffix = "LLP"
        elif "trust" in lower:
            suffix = "Family Trust"
            root = rng.choice(["Himalaya", "Nilgiri", "Aravali", "Vindhya", "Sahyadri"])
        else:
            suffix = "Limited"

        org_name = f"{root} {suffix}"

        if raw_text.isupper():
            return org_name.upper()
        return org_name

    def _generate_address(self, raw_text: str, rng: random.Random) -> str:
        """Generates a realistic address preserving geographical region."""
        text_lower = raw_text.lower()

        plot_no = rng.randint(10, 99)
        phase = rng.choice(["I", "II", "III"])
        sector = rng.randint(1, 25)

        if "chakan" in text_lower or "birdewadi" in text_lower or "khed" in text_lower:
            addr = f"Plot {plot_no}/B, Phase {phase}, Chakan MIDC Industrial Area, Taluka Khed, Pune – 410 501, Maharashtra, India"
        elif "baner" in text_lower or "montreal" in text_lower:
            suite_no = rng.randint(201, 599)
            addr = f"Suite {suite_no}, Tower B, Millennium Business Park, Baner, Pune – 411 045, Maharashtra, India"
        elif "lower parel" in text_lower or "one world" in text_lower or "mumbai" in text_lower:
            floor = rng.choice(["12th", "15th", "18th", "22nd"])
            addr = f"{floor} Floor, Tower A, Peninsula Corporate Park, Lower Parel, Mumbai 400013, Maharashtra, India"
        elif "andheri" in text_lower or "sakinaka" in text_lower:
            floor = rng.choice(["4th", "5th", "6th"])
            addr = f"{floor} Floor, Crystal Business Plaza, Andheri-Kurla Road, Sakinaka, Mumbai 400072, Maharashtra, India"
        else:
            addr = f"Plot {plot_no}, Sector {sector}, MIDC Industrial Estate, Pune 411018, Maharashtra, India"

        if raw_text.isupper():
            return addr.upper()
        return addr

    def _generate_email(self, raw_text: str, rng: random.Random) -> str:
        """Generates a realistic corporate or personal email."""
        if "cs" in raw_text.lower() or "compliance" in raw_text.lower() or "connect" in raw_text.lower():
            prefix = "cs.compliance" if "cs" in raw_text.lower() else "compliance"
            return f"{prefix}@zenithdynamics.com"
        users = ["contact", "info", "admin", "office", "investor.relations"]
        u = rng.choice(users)
        return f"{u}@zenithdynamics.com"

    def _generate_phone(self, raw_text: str, rng: random.Random) -> str:
        """Generates phone number preserving STD code or international prefix format."""
        # Landline with + 91 20 ... format
        if "20" in raw_text and ("+" in raw_text or "91" in raw_text):
            suffix = f"{rng.randint(4000, 4999)} {rng.randint(1000, 9999)}"
            if "+ " in raw_text:
                return f"+ 91 20 {suffix}"
            return f"+91 20 {suffix}"
        # Mobile format
        digits = "".join([str(rng.randint(0, 9)) for _ in range(8)])
        return f"+91 98{digits}"

    def _generate_tax_id(self, raw_text: str, rng: random.Random) -> str:
        """Generates synthetic Indian PAN or US SSN matching format."""
        if "-" in raw_text and len(raw_text.strip()) == 11:
            # US SSN format: 123-45-6789
            return f"{rng.randint(100, 899)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"
        if len(raw_text.strip()) == 8 and raw_text.isdigit():
            # DIN: 8 digits
            return f"0{rng.randint(1000000, 9999999)}"
        # Indian PAN format: 5 letters + 4 digits + 1 letter
        letters = "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
        digits = f"{rng.randint(1000, 9999)}"
        tail = rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
        return f"{letters}PH{digits}{tail}"

    def _generate_dob(self, rng: random.Random) -> str:
        """Generates realistic date of birth."""
        day = rng.randint(1, 28)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        month = rng.choice(months)
        year = rng.randint(1965, 1995)
        return f"{day:02d} {month} {year}"

    def _generate_card(self, rng: random.Random) -> str:
        """Generates Luhn-valid test Visa card number."""
        body = "".join([str(rng.randint(0, 9)) for _ in range(11)])
        partial = f"4012{body}"
        digits = [int(c) for c in partial]
        rev = digits[::-1]
        total = 0
        for i, d in enumerate(rev):
            if i % 2 == 0:
                val = d * 2
                total += val - 9 if val > 9 else val
            else:
                total += d
        check_digit = (10 - (total % 10)) % 10
        card_num = f"{partial}{check_digit}"
        return f"{card_num[:4]} {card_num[4:8]} {card_num[8:12]} {card_num[12:]}"
