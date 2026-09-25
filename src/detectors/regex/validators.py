"""
Algorithmic validators for structured PII (Luhn, ipaddress, phonenumbers, RFC emails, PAN/SSN).
"""

import ipaddress
import re
from typing import Optional
import phonenumbers
from datetime import datetime


def validate_luhn(number_str: str) -> bool:
    """Validates credit card numbers using the standard Luhn (Mod-10) algorithm."""
    # Strip spaces and hyphens
    digits = re.sub(r'[\s\-]', '', number_str)
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False
    
    # Exclude repetitive identical digits (e.g., 0000000000000000)
    if len(set(digits)) == 1:
        return False

    total = 0
    reverse_digits = digits[::-1]
    for i, char in enumerate(reverse_digits):
        n = int(char)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_ip_address(ip_str: str) -> bool:
    """Validates IPv4 and IPv6 addresses using the ipaddress module."""
    cleaned = ip_str.strip()
    try:
        ip_obj = ipaddress.ip_address(cleaned)
        # Avoid treating 0.0.0.0 or 255.255.255.255 as PII if desired, but they are valid IP syntax
        return True
    except ValueError:
        return False


def validate_phone_number(phone_str: str, default_region: str = "IN") -> bool:
    """
    Validates telephone and mobile numbers using Google's libphonenumber port.
    Prevents monetary values, year ranges, or registration numbers from being flagged.
    """
    cleaned = phone_str.strip()
    # If it looks like pure currency or percentage, reject immediately
    if re.search(r'[₹$€£%]', cleaned):
        return False
    
    # Strip excessive punctuation
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
        if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
            return True
        # Also handle standard Indian mobile 10-digit formats starting with 6, 7, 8, 9
        if len(digits_only) == 10 and digits_only[0] in '6789':
            return True
        # Handle +91 followed by 10 digits
        if len(digits_only) == 12 and digits_only.startswith('91') and digits_only[2] in '6789':
            return True
    except phonenumbers.NumberParseException:
        # Fallback for common local telephone patterns with STD code
        if re.match(r'^(?:\+?91[\-\s]?)?[6-9]\d{9}$', cleaned):
            return True
        if re.match(r'^\(?0\d{2,4}\)?[\-\s]?\d{6,8}$', cleaned):
            return True
    return False


def validate_email_address(email_str: str) -> bool:
    """Validates email addresses against RFC standard syntax and sensible TLDs."""
    cleaned = email_str.strip().lower()
    email_regex = re.compile(
        r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    )
    if not email_regex.match(cleaned):
        return False
    
    # Discard false positives like invalid double dots or missing TLD
    if '..' in cleaned or cleaned.endswith('.'):
        return False
    
    domain_part = cleaned.split('@')[-1]
    if '.' not in domain_part:
        return False
    tld = domain_part.split('.')[-1]
    if len(tld) < 2:
        return False
    return True


def validate_us_ssn(ssn_str: str) -> bool:
    """Validates US Social Security Number format and disallowed area/group numbers."""
    cleaned = re.sub(r'\s+', '', ssn_str)
    # Match standard AAA-GG-SSSS pattern
    pattern = re.compile(r'^(?!000|666|9\d{2})(\d{3})-(?!00)(\d{2})-(?!0000)(\d{4})$')
    return bool(pattern.match(cleaned))


def validate_indian_pan(pan_str: str) -> bool:
    """
    Validates Indian Permanent Account Number (PAN):
    5 uppercase letters + 4 digits + 1 uppercase letter.
    4th character indicates status (e.g. P for Person, C for Company, H for HUF, F for Firm).
    """
    cleaned = pan_str.strip().upper()
    if len(cleaned) != 10:
        return False
    pattern = re.compile(r'^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$')
    return bool(pattern.match(cleaned))


def validate_dob_syntax(date_str: str) -> Optional[datetime]:
    """
    Attempts to parse a date string into a datetime object.
    Returns datetime if valid and falls within realistic human lifespan (1910 - current year).
    """
    cleaned = date_str.strip()
    formats = [
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
        "%d %B, %Y", "%d %b, %Y", "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if 1910 <= dt.year <= datetime.now().year:
                return dt
        except ValueError:
            continue
    return None
