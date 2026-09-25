"""
Text cleaning and normalization module with strict offset tracking.
Ensures zero-drift mapping between normalized text and raw document text.
"""

from dataclasses import dataclass
from typing import List, Tuple
import unicodedata
import re


@dataclass(frozen=True)
class NormalizationResult:
    """Holds normalized text along with bidirectional index mapping."""
    raw_text: str
    cleaned_text: str
    norm_to_orig: List[int]
    orig_to_norm: List[int]

    def map_norm_span_to_orig(self, norm_start: int, norm_end: int) -> Tuple[int, int]:
        """Maps a span in cleaned_text back to exact character span in raw_text."""
        if not self.cleaned_text:
            return 0, 0
        
        # Clamp bounds
        clamped_start = max(0, min(norm_start, len(self.cleaned_text)))
        clamped_end = max(clamped_start, min(norm_end, len(self.cleaned_text)))

        if clamped_start == clamped_end:
            if clamped_start < len(self.norm_to_orig):
                orig_pos = self.norm_to_orig[clamped_start]
                return orig_pos, orig_pos
            return len(self.raw_text), len(self.raw_text)

        orig_start = self.norm_to_orig[clamped_start]
        # For end offset, map the last character index + 1
        last_char_idx = clamped_end - 1
        orig_last_char_idx = self.norm_to_orig[last_char_idx]
        orig_end = orig_last_char_idx + 1

        # Safety check: ensure orig_start <= orig_end
        if orig_start > orig_end:
            orig_start, orig_end = orig_end, orig_start

        return orig_start, orig_end


class TextCleaner:
    """Normalizes text while tracking exact character offsets for OpenXML run mapping."""

    ZERO_WIDTH_CHARS = {
        '\u200b',  # zero-width space
        '\u200c',  # zero-width non-joiner
        '\u200d',  # zero-width joiner
        '\ufeff',  # byte order mark / zero-width no-break space
        '\u00ad',  # soft hyphen
    }

    UNICODE_REPLACEMENTS = {
        '\u00a0': ' ',  # non-breaking space
        '\u202f': ' ',  # narrow non-breaking space
        '\u2009': ' ',  # thin space
        '\u2003': ' ',  # em space
        '\u2002': ' ',  # en space
        '–': '-',       # en-dash
        '—': '-',       # em-dash
        '’': "'",       # right single quote
        '‘': "'",       # left single quote
        '“': '"',       # left double quote
        '”': '"',       # right double quote
    }

    def clean(self, raw_text: str) -> NormalizationResult:
        """
        Normalizes Unicode and whitespace while building character-by-character coordinate maps.
        """
        if not raw_text:
            return NormalizationResult(
                raw_text="",
                cleaned_text="",
                norm_to_orig=[],
                orig_to_norm=[]
            )

        cleaned_chars: List[str] = []
        norm_to_orig: List[int] = []
        orig_to_norm: List[int] = [-1] * len(raw_text)

        for orig_idx, char in enumerate(raw_text):
            # Skip zero-width characters
            if char in self.ZERO_WIDTH_CHARS:
                continue

            # Standardize common typographic punctuation
            sub = self.UNICODE_REPLACEMENTS.get(char, char)

            # Normalize using NFKC for ligatures (e.g., 'fi', 'fl')
            normalized_chunk = unicodedata.normalize('NFKC', sub)

            for norm_char in normalized_chunk:
                norm_idx = len(cleaned_chars)
                cleaned_chars.append(norm_char)
                norm_to_orig.append(orig_idx)
                if orig_to_norm[orig_idx] == -1:
                    orig_to_norm[orig_idx] = norm_idx

        # Fill any skipped positions in orig_to_norm for monotonic safety
        last_valid_norm = 0
        for i in range(len(orig_to_norm)):
            if orig_to_norm[i] != -1:
                last_valid_norm = orig_to_norm[i]
            else:
                orig_to_norm[i] = last_valid_norm

        cleaned_text = "".join(cleaned_chars)

        return NormalizationResult(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            norm_to_orig=norm_to_orig,
            orig_to_norm=orig_to_norm
        )
