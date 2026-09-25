"""
Image Redactor.
Applies bounding box pixel redactions (solid color fill or blur) to image artifacts,
returning clean sanitized image bytes for DOCX container replacement.
"""

from typing import List, Tuple, Optional
import io
from PIL import Image, ImageDraw, ImageFilter


class ImageRedactor:
    """Applies pixel redaction to image bytes."""

    def __init__(self, fill_color: Tuple[int, int, int] = (0, 0, 0)):
        self.fill_color = fill_color

    def redact_boxes(
        self,
        image_bytes: bytes,
        bounding_boxes: List[Tuple[int, int, int, int]],
        method: str = "fill"
    ) -> bytes:
        """
        Redacts specified bounding boxes (x, y, w, h) on image.
        Returns redacted image bytes.
        """
        if not image_bytes or not bounding_boxes:
            return image_bytes

        try:
            img = Image.open(io.BytesIO(image_bytes))
            orig_format = img.format or "PNG"
            # Ensure editable mode
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            draw = ImageDraw.Draw(img)

            for x, y, w, h in bounding_boxes:
                # Clamp coordinates to image dimensions
                x0 = max(0, x)
                y0 = max(0, y)
                x1 = min(img.width, x + w)
                y1 = min(img.height, y + h)

                if x1 <= x0 or y1 <= y0:
                    continue

                if method == "blur":
                    box_crop = img.crop((x0, y0, x1, y1))
                    blurred_crop = box_crop.filter(ImageFilter.GaussianBlur(radius=15))
                    img.paste(blurred_crop, (x0, y0))
                else:
                    # Solid fill (black-box)
                    fill = self.fill_color if img.mode == "RGB" else (*self.fill_color, 255)
                    draw.rectangle([x0, y0, x1, y1], fill=fill)

            out_buffer = io.BytesIO()
            img.save(out_buffer, format=orig_format)
            return out_buffer.getvalue()

        except Exception:
            return image_bytes
