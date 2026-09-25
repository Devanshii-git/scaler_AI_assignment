"""
Offset mapping data structures linking document text blocks, runs, and character offsets.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Tuple
from src.normalization.text_cleaner import NormalizationResult


@dataclass
class RunInfo:
    """Tracks a single python-docx Run with its local character bounds inside a block."""
    run_index: int
    raw_start: int
    raw_end: int
    text: str
    is_italic: Optional[bool] = False
    is_bold: Optional[bool] = False
    run_ref: Optional[Any] = None  # Reference to docx.text.run.Run


@dataclass
class DocumentBlock:
    """Represents a coherent text unit in a DOCX document (paragraph, table cell, footer, etc.)."""
    block_id: str
    block_type: str  # 'paragraph', 'table_cell', 'header', 'footer'
    raw_text: str
    runs: List[RunInfo] = field(default_factory=list)
    paragraph_ref: Optional[Any] = None
    clean_result: Optional[NormalizationResult] = None
    metadata: dict = field(default_factory=dict)

    @property
    def normalized_text(self) -> str:
        if self.clean_result:
            return self.clean_result.cleaned_text
        return self.raw_text

    def map_normalized_span_to_raw(self, norm_start: int, norm_end: int) -> Tuple[int, int]:
        """Maps a span in normalized_text to raw_text character offsets."""
        if self.clean_result:
            return self.clean_result.map_norm_span_to_orig(norm_start, norm_end)
        return norm_start, norm_end

    def find_spanned_runs(self, raw_start: int, raw_end: int) -> List[Tuple[RunInfo, int, int]]:
        """
        Returns list of (RunInfo, slice_start_within_run, slice_end_within_run)
        covering the raw_start..raw_end interval.
        """
        spanned = []
        for r in self.runs:
            # Check overlap between [raw_start, raw_end) and [r.raw_start, r.raw_end)
            overlap_start = max(raw_start, r.raw_start)
            overlap_end = min(raw_end, r.raw_end)
            if overlap_start < overlap_end:
                slice_start = overlap_start - r.raw_start
                slice_end = overlap_end - r.raw_start
                spanned.append((r, slice_start, slice_end))
        return spanned
