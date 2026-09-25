"""
Comprehensive DOCX Ingestion Parser.
Extracts paragraphs, table cells, headers, footers, bottom notes, and embedded images,
constructing fully indexed DocumentBlock instances with run offsets and styling references.
"""

from typing import List, Dict, Any, Tuple
import docx
from docx.text.paragraph import Paragraph
import zipfile
import io

from src.normalization.text_cleaner import TextCleaner
from src.ingestion.offset_mapper import DocumentBlock, RunInfo


class DocxParser:
    """Parses DOCX documents into indexed structural blocks and image artifacts."""

    def __init__(self, cleaner: TextCleaner = None):
        self.cleaner = cleaner or TextCleaner()

    def _build_block(
        self,
        paragraph: Paragraph,
        block_id: str,
        block_type: str,
        metadata: dict = None
    ) -> DocumentBlock:
        """Constructs a DocumentBlock from a python-docx Paragraph with run offset indexing."""
        runs_info: List[RunInfo] = []
        raw_parts: List[str] = []
        current_offset = 0

        for idx, run in enumerate(paragraph.runs):
            run_text = run.text or ""
            start_off = current_offset
            end_off = current_offset + len(run_text)
            current_offset = end_off

            raw_parts.append(run_text)
            runs_info.append(
                RunInfo(
                    run_index=idx,
                    raw_start=start_off,
                    raw_end=end_off,
                    text=run_text,
                    is_italic=bool(run.italic),
                    is_bold=bool(run.bold),
                    run_ref=run
                )
            )

        raw_text = "".join(raw_parts)
        clean_res = self.cleaner.clean(raw_text)

        meta = metadata or {}
        # Mark if paragraph contains italic runs (e.g., bottom notes, legal disclaimers)
        has_italic = any(r.is_italic for r in runs_info)
        meta["has_italic"] = has_italic
        meta["style_name"] = paragraph.style.name if paragraph.style else "Normal"

        return DocumentBlock(
            block_id=block_id,
            block_type=block_type,
            raw_text=raw_text,
            runs=runs_info,
            paragraph_ref=paragraph,
            clean_result=clean_res,
            metadata=meta
        )

    def parse_document(self, docx_path: str) -> Tuple[List[DocumentBlock], Dict[str, bytes], docx.Document]:
        """
        Parses the entire document:
        - Body paragraphs
        - Tables and cell paragraphs
        - Headers and footers (all sections)
        - Embedded images from package media/
        
        Returns:
            (blocks, image_artifacts, docx_doc)
        """
        doc = docx.Document(docx_path)
        blocks: List[DocumentBlock] = []

        # 1. Parse body paragraphs
        for p_idx, p in enumerate(doc.paragraphs):
            # Check if this paragraph is at the bottom or styled as note/italic
            is_footnote_style = "footnote" in (p.style.name.lower() if p.style else "")
            b = self._build_block(
                paragraph=p,
                block_id=f"p_{p_idx}",
                block_type="paragraph",
                metadata={"para_index": p_idx, "is_footnote_style": is_footnote_style}
            )
            blocks.append(b)

        # 2. Parse tables and cells
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for cp_idx, cp in enumerate(cell.paragraphs):
                        b = self._build_block(
                            paragraph=cp,
                            block_id=f"tbl_{t_idx}_r_{r_idx}_c_{c_idx}_p_{cp_idx}",
                            block_type="table_cell",
                            metadata={
                                "table_index": t_idx,
                                "row_index": r_idx,
                                "col_index": c_idx,
                                "cell_para_index": cp_idx
                            }
                        )
                        blocks.append(b)

        # 3. Parse headers and footers across all sections
        for s_idx, section in enumerate(doc.sections):
            # Header paragraphs
            for hp_idx, hp in enumerate(section.header.paragraphs):
                b = self._build_block(
                    paragraph=hp,
                    block_id=f"sec_{s_idx}_header_p_{hp_idx}",
                    block_type="header",
                    metadata={"section_index": s_idx, "header_para_index": hp_idx}
                )
                blocks.append(b)

            # Footer paragraphs (contains bottom notes, italic disclaimers, page references)
            for fp_idx, fp in enumerate(section.footer.paragraphs):
                b = self._build_block(
                    paragraph=fp,
                    block_id=f"sec_{s_idx}_footer_p_{fp_idx}",
                    block_type="footer",
                    metadata={"section_index": s_idx, "footer_para_index": fp_idx}
                )
                blocks.append(b)

            # Also check for tables inside headers/footers
            for ht_idx, ht in enumerate(section.header.tables):
                for r_idx, row in enumerate(ht.rows):
                    for c_idx, cell in enumerate(row.cells):
                        for cp_idx, cp in enumerate(cell.paragraphs):
                            b = self._build_block(
                                paragraph=cp,
                                block_id=f"sec_{s_idx}_htbl_{ht_idx}_r_{r_idx}_c_{c_idx}_p_{cp_idx}",
                                block_type="header_table_cell",
                                metadata={"section_index": s_idx, "table_index": ht_idx}
                            )
                            blocks.append(b)

            for ft_idx, ft in enumerate(section.footer.tables):
                for r_idx, row in enumerate(ft.rows):
                    for c_idx, cell in enumerate(row.cells):
                        for cp_idx, cp in enumerate(cell.paragraphs):
                            b = self._build_block(
                                paragraph=cp,
                                block_id=f"sec_{s_idx}_ftbl_{ft_idx}_r_{r_idx}_c_{c_idx}_p_{cp_idx}",
                                block_type="footer_table_cell",
                                metadata={"section_index": s_idx, "table_index": ft_idx}
                            )
                            blocks.append(b)

        # 4. Extract embedded images from DOCX zip
        image_artifacts: Dict[str, bytes] = {}
        with zipfile.ZipFile(docx_path, 'r') as z:
            for fname in z.namelist():
                if fname.startswith("word/media/"):
                    image_artifacts[fname] = z.read(fname)

        return blocks, image_artifacts, doc
