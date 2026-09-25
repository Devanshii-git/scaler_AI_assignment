"""
DOCX Reconstruction Engine.
Applies span-level pseudonyms into python-docx paragraphs, table cells, headers, and footers
using exact run-splitting algorithms that preserve formatting styles and OpenXML structural integrity.
"""

from typing import List, Dict, Tuple, Optional
import docx
import zipfile
import io
import shutil
from src.ingestion.offset_mapper import DocumentBlock
from src.detectors.base import EntitySpan
from src.pseudonymization.synthesizer import PseudonymSynthesizer


class DocxReconstructor:
    """Reconstructs redacted DOCX files with formatting and image preservation."""

    def __init__(self, synthesizer: PseudonymSynthesizer):
        self.synthesizer = synthesizer

    def redact_document(
        self,
        original_docx_path: str,
        output_docx_path: str,
        blocks: List[DocumentBlock],
        block_spans: Dict[str, List[EntitySpan]],
        doc: Optional[docx.Document] = None,
        redacted_images: Dict[str, bytes] = None
    ) -> str:
        """
        Executes end-to-end redaction on document:
        1. Modifies in-memory paragraph runs across paragraphs, tables, headers, footers.
        2. Saves updated document to temporary buffer.
        3. Injects redacted images into the OpenXML media/ zip structure.
        4. Writes output_docx_path.
        """
        if doc is None:
            doc = docx.Document(original_docx_path)
            # Link blocks to the newly loaded doc paragraphs if needed
            # (or caller passes loaded doc directly)

        # Build lookup for all blocks in doc
        # We process each block that has detected spans
        for block in blocks:
            spans = block_spans.get(block.block_id, [])
            if not spans:
                continue

            # Map normalized spans to raw character offsets
            raw_replacements: List[Tuple[int, int, str]] = []
            for s in spans:
                raw_start, raw_end = block.map_normalized_span_to_raw(s.start, s.end)
                pseudo = self.synthesizer.get_or_create_pseudonym(s.type, s.text)
                raw_replacements.append((raw_start, raw_end, pseudo))

            # Retrieve the underlying python-docx paragraph
            para = block.paragraph_ref
            if para is not None:
                self._apply_replacements_to_paragraph(para, raw_replacements)

        # Save document to intermediate bytes buffer
        intermediate_buffer = io.BytesIO()
        doc.save(intermediate_buffer)
        intermediate_buffer.seek(0)

        # If there are redacted images, update them in the DOCX zip package
        if redacted_images:
            output_buffer = io.BytesIO()
            with zipfile.ZipFile(intermediate_buffer, 'r') as in_zip:
                with zipfile.ZipFile(output_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as out_zip:
                    for item in in_zip.infolist():
                        if item.filename in redacted_images:
                            out_zip.writestr(item.filename, redacted_images[item.filename])
                        else:
                            out_zip.writestr(item.filename, in_zip.read(item.filename))
            output_buffer.seek(0)
            final_bytes = output_buffer.getvalue()
        else:
            final_bytes = intermediate_buffer.getvalue()

        # Write final DOCX to target path
        with open(output_docx_path, "wb") as f:
            f.write(final_bytes)

        return output_docx_path

    def _apply_replacements_to_paragraph(
        self,
        paragraph: docx.text.paragraph.Paragraph,
        replacements: List[Tuple[int, int, str]]
    ):
        """
        Applies a list of (raw_start, raw_end, replacement_text) intervals
        to paragraph runs preserving all formatting properties.
        """
        if not paragraph.runs or not replacements:
            return

        runs = paragraph.runs
        # Build initial offsets of runs
        run_offsets: List[Tuple[int, int]] = []
        curr = 0
        for r in runs:
            text = r.text or ""
            run_offsets.append((curr, curr + len(text)))
            curr += len(text)

        # Process replacements in reverse order (right to left) to avoid offset invalidation
        sorted_reps = sorted(replacements, key=lambda x: x[0], reverse=True)

        for rep_start, rep_end, rep_text in sorted_reps:
            first_idx = None
            last_idx = None

            for i, (r_start, r_end) in enumerate(run_offsets):
                if max(r_start, rep_start) < min(r_end, rep_end):
                    if first_idx is None:
                        first_idx = i
                    last_idx = i

            if first_idx is None:
                continue

            r_first = runs[first_idx]
            r_last = runs[last_idx]
            f_start, f_end = run_offsets[first_idx]
            l_start, l_end = run_offsets[last_idx]

            first_text = r_first.text or ""
            last_text = r_last.text or ""

            slice_start = max(0, rep_start - f_start)
            slice_end = max(0, rep_end - l_start)

            prefix = first_text[:slice_start]
            suffix = last_text[slice_end:]

            if first_idx == last_idx:
                r_first.text = prefix + rep_text + suffix
            else:
                r_first.text = prefix + rep_text
                for m in range(first_idx + 1, last_idx):
                    runs[m].text = ""
                r_last.text = suffix

            # Recompute run offsets after modification
            run_offsets = []
            curr = 0
            for r in runs:
                t = r.text or ""
                run_offsets.append((curr, curr + len(t)))
                curr += len(t)
