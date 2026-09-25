"""
Unit tests for text cleaning, monotonic coordinate mapping, and DOCX block offset preservation.
"""

import pytest
from src.normalization.text_cleaner import TextCleaner
from src.ingestion.offset_mapper import DocumentBlock, RunInfo


def test_text_cleaner_ligatures_and_zero_width():
    cleaner = TextCleaner()
    # "fi" ligature (\ufb01), non-breaking space (\u00a0), zero-width space (\u200b)
    raw = "Of\ufb01ce\u200b\u00a0at\u00a0Pune–MIDC"
    res = cleaner.clean(raw)

    assert "\u200b" not in res.cleaned_text
    assert "Office" in res.cleaned_text
    assert "-" in res.cleaned_text

    # Test bidirectional coordinate mapping
    # "Pune" in cleaned text
    pune_start = res.cleaned_text.index("Pune")
    pune_end = pune_start + len("Pune")

    orig_start, orig_end = res.map_norm_span_to_orig(pune_start, pune_end)
    assert raw[orig_start:orig_end] == "Pune"


def test_document_block_run_spanning():
    # Simulate a paragraph split into 3 runs: "Mr. ", "Rajesh ", "Hegde"
    r0 = RunInfo(run_index=0, raw_start=0, raw_end=4, text="Mr. ")
    r1 = RunInfo(run_index=1, raw_start=4, raw_end=11, text="Rajesh ")
    r2 = RunInfo(run_index=2, raw_start=11, raw_end=16, text="Hegde")

    raw_text = "Mr. Rajesh Hegde"
    cleaner = TextCleaner()
    clean_res = cleaner.clean(raw_text)

    block = DocumentBlock(
        block_id="p_test",
        block_type="paragraph",
        raw_text=raw_text,
        runs=[r0, r1, r2],
        clean_result=clean_res
    )

    # Target entity: "Rajesh Hegde" (start 4, end 16)
    spanned = block.find_spanned_runs(4, 16)
    assert len(spanned) == 2
    # First spanned run is r1 ("Rajesh "), slice 0..7
    assert spanned[0][0].run_index == 1
    assert spanned[0][1] == 0
    assert spanned[0][2] == 7
    # Second spanned run is r2 ("Hegde"), slice 0..5
    assert spanned[1][0].run_index == 2
    assert spanned[1][1] == 0
    assert spanned[1][2] == 5


def test_monotonic_empty_and_edge_cases():
    cleaner = TextCleaner()
    empty_res = cleaner.clean("")
    assert empty_res.cleaned_text == ""
    assert empty_res.map_norm_span_to_orig(0, 0) == (0, 0)

    # Only zero width
    zw_res = cleaner.clean("\u200b\u200c\u200d")
    assert zw_res.cleaned_text == ""
