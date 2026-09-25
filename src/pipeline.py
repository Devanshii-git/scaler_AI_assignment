"""
End-to-end PII Redaction Pipeline.
Orchestrates ingestion, candidate detection, context scoring, dynamic entity registry,
conflict resolution, cryptographic pseudonymization, and formatting-preserving DOCX reconstruction.
Features high-performance vectorized batch inference.
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import re
import docx

from src.ingestion.docx_parser import DocxParser
from src.ingestion.offset_mapper import DocumentBlock
from src.normalization.text_cleaner import TextCleaner
from src.detectors.base import EntitySpan
from src.detectors.regex.recognizers import RegexDetector
from src.detectors.neural.gliner_detector import GlinerDetector
from src.detectors.context.proximity_scorer import ContextProximityScorer
from src.detectors.context.address_detector import ContextualAddressDetector
from src.detectors.context.entity_registry import DocumentEntityRegistry
from src.resolution.aggregator import CandidateAggregator
from src.resolution.conflict_resolver import ConflictResolver
from src.pseudonymization.crypto import CryptoKeyManager
from src.pseudonymization.synthesizer import PseudonymSynthesizer
from src.document.docx_reconstructor import DocxReconstructor
from src.image.ocr_engine import ImageOcrEngine
from src.image.redactor import ImageRedactor


class PiiRedactionPipeline:
    """Production PII Redaction Engine with high-throughput batching."""

    def __init__(
        self,
        enable_neural: bool = True,
        enable_context: bool = True,
        enable_registry: bool = True,
        enable_images: bool = True,
        model_path: str = "models/gliner_multi_pii"
    ):
        self.cleaner = TextCleaner()
        self.parser = DocxParser(self.cleaner)
        self.regex_detector = RegexDetector()

        self.enable_neural = enable_neural
        self.enable_context = enable_context
        self.enable_registry = enable_registry
        self.enable_images = enable_images

        self.neural_detector = None
        if self.enable_neural:
            self.neural_detector = GlinerDetector(model_path=model_path)

        self.context_scorer = ContextProximityScorer() if self.enable_context else None
        self.address_detector = ContextualAddressDetector() if self.enable_context else None
        self.entity_registry = DocumentEntityRegistry() if self.enable_registry else None

        self.conflict_resolver = ConflictResolver()
        self.key_manager = CryptoKeyManager()
        self.synthesizer = PseudonymSynthesizer(self.key_manager)
        self.reconstructor = DocxReconstructor(self.synthesizer)

        self.ocr_engine = ImageOcrEngine() if self.enable_images else None
        self.image_redactor = ImageRedactor() if self.enable_images else None

    def process_document(
        self,
        input_docx_path: str,
        output_docx_path: str
    ) -> Dict[str, Any]:
        """
        Runs the complete redaction pipeline on an input DOCX document.
        Returns a detailed summary dictionary of detected entities and redacting results.
        """
        # 1. Reset per-document state
        self.synthesizer.reset()
        if self.entity_registry:
            self.entity_registry.reset()

        # 2. Ingest document
        print("Ingesting document and extracting blocks...", flush=True)
        blocks, images, loaded_doc = self.parser.parse_document(input_docx_path)
        print(f"Extracted {len(blocks)} total blocks and {len(images)} embedded images.", flush=True)

        # 3. High-throughput Batch Neural Inference
        neural_results_map: Dict[int, List[EntitySpan]] = {}
        if self.neural_detector:
            neural_indices = []
            neural_texts = []
            for i, block in enumerate(blocks):
                text = block.normalized_text
                if not text:
                    continue
                clean_str = text.strip()
                if bool(re.search(r'[a-zA-Z]', clean_str)) and len(clean_str) >= 4:
                    neural_indices.append(i)
                    neural_texts.append(clean_str)

            if neural_texts:
                print(f"Running GPU neural batch inference on {len(neural_texts)} text blocks (batch_size=64)...", flush=True)
                batch_spans = self.neural_detector.detect_batch(neural_texts, batch_size=64)
                for idx, spans in zip(neural_indices, batch_spans):
                    neural_results_map[idx] = spans
                print("GPU neural inference completed!", flush=True)

        # 4. First Pass: Detect candidates across all blocks
        print("Running Pass 1: Multi-engine candidate detection...", flush=True)
        block_spans: Dict[str, List[EntitySpan]] = {}
        all_detected_spans: List[EntitySpan] = []

        for i, block in enumerate(blocks):
            text = block.normalized_text
            if not text or not text.strip():
                continue

            candidates: List[EntitySpan] = []

            # A. Regex Detector
            regex_candidates = self.regex_detector.detect(text)
            candidates.extend(regex_candidates)

            # B. Neural GLiNER Detector (from pre-computed batch map)
            if i in neural_results_map:
                candidates.extend(neural_results_map[i])

            # C. Contextual Address Detector
            clean_str = text.strip()
            if bool(re.search(r'[a-zA-Z]', clean_str)) and len(clean_str) >= 4:
                if self.address_detector:
                    addr_candidates = self.address_detector.detect(text)
                    candidates.extend(addr_candidates)

            # D. Context Proximity Scorer
            if self.context_scorer:
                candidates = self.context_scorer.score_and_adjust(candidates, text)

            # E. Register high-confidence entities in Document Registry
            if self.entity_registry:
                for c in candidates:
                    self.entity_registry.register_candidate(c)

            block_spans[block.block_id] = candidates

        # 5. Second Pass: Registry propagation across the entire document
        print("Running Pass 2: Fast entity registry propagation...", flush=True)
        if self.entity_registry:
            for block in blocks:
                text = block.normalized_text
                if not text or len(text.strip()) < 4 or not re.search(r'[a-zA-Z]', text):
                    continue
                existing = block_spans.get(block.block_id, [])
                propagated = self.entity_registry.propagate_to_text(text, existing)
                if propagated:
                    if self.context_scorer:
                        propagated = self.context_scorer.score_and_adjust(propagated, text)
                    existing.extend(propagated)
                    block_spans[block.block_id] = existing

        # 6. Third Pass: Conflict Resolution per block
        print("Running Pass 3: Conflict resolution...", flush=True)
        total_pii_count = 0
        pii_by_type: Dict[str, int] = {}

        for block_id, raw_spans in list(block_spans.items()):
            resolved = self.conflict_resolver.resolve(raw_spans)
            block_spans[block_id] = resolved
            for s in resolved:
                total_pii_count += 1
                pii_by_type[s.type] = pii_by_type.get(s.type, 0) + 1
                all_detected_spans.append(s)

        # 7. Process and redact embedded images
        redacted_images: Dict[str, bytes] = {}
        if self.enable_images and self.ocr_engine and self.image_redactor and images:
            print("Checking embedded images for redaction...", flush=True)
            for img_name, img_bytes in images.items():
                boxes = self.ocr_engine.extract_text_boxes(img_bytes)
                pii_boxes = []
                for b in boxes:
                    box_text = b["text"]
                    if self.regex_detector.detect(box_text):
                        pii_boxes.append(b["bbox"])
                if pii_boxes:
                    redacted_img = self.image_redactor.redact_boxes(img_bytes, pii_boxes)
                    redacted_images[img_name] = redacted_img

        # 8. DOCX Reconstruction with run splitting & formatting preservation
        print(f"Reconstructing DOCX with {total_pii_count} redacted spans...", flush=True)
        os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
        self.reconstructor.redact_document(
            original_docx_path=input_docx_path,
            output_docx_path=output_docx_path,
            blocks=blocks,
            block_spans=block_spans,
            doc=loaded_doc,
            redacted_images=redacted_images
        )

        return {
            "input_file": input_docx_path,
            "output_file": output_docx_path,
            "total_blocks_processed": len(blocks),
            "total_pii_detected": total_pii_count,
            "pii_by_type": pii_by_type,
            "entities": [
                {
                    "type": s.type,
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "confidence": s.confidence,
                    "detectors": s.detector_sources
                }
                for s in all_detected_spans
            ]
        }
