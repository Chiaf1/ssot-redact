"""Test helpers: SYNTHETIC images and scans, and the Tesseract program (the tests that need it are skipped
when it is not installed)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

WIN_DEFAULT = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")


def tesseract() -> str:
    exe = shutil.which("tesseract") or (str(WIN_DEFAULT) if WIN_DEFAULT.exists() else None)
    if not exe:
        pytest.skip("Tesseract not installed")
    return exe


def text_image(path: Path, lines: list[str]) -> Path:
    im = Image.new("RGB", (1200, 80 + 60 * len(lines)), "white")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default(size=36)
    for i, line in enumerate(lines):
        d.text((30, 30 + 60 * i), line, fill="black", font=font)
    im.save(path)
    return path


def scanned_pdf(path: Path, lines: list[str], tmp: Path) -> Path:
    """A PDF made only of an image of text, like a scan."""
    Image.open(text_image(tmp / "page.png", lines)).convert("RGB").save(path, "PDF", resolution=100)
    return path
