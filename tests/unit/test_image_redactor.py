"""
Unit tests for ImageRedactor.
"""

import io
from PIL import Image
import pytest
from src.image.redactor import ImageRedactor


def test_image_redactor_fill():
    # Create a simple white test image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    redactor = ImageRedactor(fill_color=(0, 0, 0))
    # Redact box (10, 10, 20, 20)
    redacted_bytes = redactor.redact_boxes(raw_bytes, [(10, 10, 20, 20)], method="fill")

    # Verify redacted image pixel color in the box
    res_img = Image.open(io.BytesIO(redacted_bytes))
    pixel_inside = res_img.getpixel((15, 15))
    pixel_outside = res_img.getpixel((5, 5))

    assert pixel_inside == (0, 0, 0)
    assert pixel_outside == (255, 255, 255)
