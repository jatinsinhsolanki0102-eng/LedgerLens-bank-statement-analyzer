"""Tesseract-based OCR for scanned or image-only PDF pages."""

from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageOps

from config.settings import OCR_DPI, TESSERACT_CMD
from src.pdf_processing.errors import OCRExtractionError, OCRUnavailableError
from src.pdf_processing.pdf_detector import open_pdf
from src.utils.logging_config import get_logger

logger = get_logger("ocr_processor")

_COMMON_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


class OCRProcessor:
    """Render PDF pages and run local Tesseract OCR with light preprocessing."""

    def __init__(self, tesseract_cmd: str | None = None, dpi: int = OCR_DPI) -> None:
        self._tesseract_cmd = tesseract_cmd or TESSERACT_CMD or self._find_tesseract()
        self._dpi = dpi

    @staticmethod
    def _find_tesseract() -> str | None:
        command = shutil.which("tesseract")
        if command:
            return command
        for candidate in _COMMON_TESSERACT_PATHS:
            if candidate.exists():
                return str(candidate)
        return None

    @property
    def available(self) -> bool:
        return bool(self._tesseract_cmd and Path(self._tesseract_cmd).exists())

    def _load_pytesseract(self):
        try:
            import pytesseract
        except ImportError as exc:
            raise OCRUnavailableError(
                "pytesseract is not installed. Install requirements and Tesseract OCR."
            ) from exc

        if not self.available:
            raise OCRUnavailableError(
                "Tesseract OCR was not found. Install it and set TESSERACT_CMD if needed."
            )
        pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
        return pytesseract

    def ocr_page(self, path: str | Path, page_number: int, password: str | None = None) -> str:
        """OCR a single zero-based PDF page and return cleaned text."""

        pytesseract = self._load_pytesseract()
        document = open_pdf(path, password=password)
        try:
            if page_number < 0 or page_number >= document.page_count:
                raise OCRExtractionError("The requested PDF page does not exist.")
            page = document.load_page(page_number)
            zoom = self._dpi / 72
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
        except OCRExtractionError:
            raise
        except Exception as exc:
            logger.warning("Page rendering failed: %s", type(exc).__name__)
            raise OCRExtractionError("The scanned page could not be rendered.") from exc
        finally:
            document.close()

        try:
            processed = self._preprocess_image(image)
            text = pytesseract.image_to_string(
                processed,
                lang="eng",
                config="--oem 3 --psm 6 -c preserve_interword_spaces=1",
            )
        except Exception as exc:
            logger.warning("OCR execution failed: %s", type(exc).__name__)
            raise OCRExtractionError("OCR failed while reading the scanned page.") from exc
        return self._clean_ocr_text(text)

    def ocr_pages(
        self,
        path: str | Path,
        page_numbers: list[int],
        password: str | None = None,
    ) -> dict[int, str]:
        """OCR multiple zero-based pages and return page-indexed text."""

        return {
            page_number: self.ocr_page(path, page_number, password=password)
            for page_number in page_numbers
        }

    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        """Improve contrast and remove noise before OCR when OpenCV is available."""

        grayscale = ImageOps.grayscale(ImageOps.exif_transpose(image))
        try:
            import cv2
        except ImportError:
            return ImageOps.autocontrast(grayscale)

        array = np.array(grayscale)
        denoised = cv2.fastNlMeansDenoising(array, None, h=10)
        thresholded = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=15,
        )
        return Image.fromarray(thresholded)

    @staticmethod
    def _clean_ocr_text(text: str) -> str:
        lines = [" ".join(line.split()) for line in (text or "").splitlines()]
        return "\n".join(line for line in lines if line).strip()
