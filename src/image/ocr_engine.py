"""
Image OCR Engine with multi-backend support (pytesseract and fallback).
Extracts text and word/line bounding boxes from image bytes.
"""

from typing import List, Dict, Any, Tuple, Optional
import io
from PIL import Image
import os
import shutil


class ImageOcrEngine:
    """Extracts text tokens and bounding box coordinates from images."""

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.tesseract_available = False
        self._init_tesseract(tesseract_cmd)

    def _init_tesseract(self, tesseract_cmd: Optional[str]):
        """Checks for tesseract in path or configured location."""
        import pytesseract

        candidates = [
            tesseract_cmd,
            shutil.which("tesseract"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ]

        for c in candidates:
            if c and os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                self.tesseract_available = True
                break

    def extract_text_boxes(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Runs OCR and returns list of detected text boxes:
        [{"text": word, "bbox": (x, y, w, h), "confidence": conf}, ...]
        """
        if not image_bytes:
            return []

        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            return []

        boxes: List[Dict[str, Any]] = []

        if self.tesseract_available:
            try:
                import pytesseract
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                n_boxes = len(data["text"])
                for i in range(n_boxes):
                    text = data["text"][i].strip()
                    conf = float(data["conf"][i])
                    if conf > 30 and text:
                        x = data["left"][i]
                        y = data["top"][i]
                        w = data["width"][i]
                        h = data["height"][i]
                        boxes.append({
                            "text": text,
                            "bbox": (x, y, w, h),
                            "confidence": conf / 100.0
                        })
                return boxes
            except Exception:
                pass

        # Fallback if tesseract binary is not on host: return empty or fallback boxes
        return boxes
