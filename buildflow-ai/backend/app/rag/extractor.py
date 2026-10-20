"""
Text extraction from documents.

Supports:
- PDF (via pypdf)
- Word documents (DOCX via python-docx, if installed)
- Plain text (TXT, MD, CSV, JSON)
- OCR fallback (via pytesseract, if installed)

Extraction is deterministic — no LLM used for text extraction.
"""
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


@dataclass
class ExtractedPage:
    """A single page of extracted text from a document."""
    page_number: int
    text: str
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ExtractedDocument:
    """Full extracted text from a document, split by page."""
    file_name: str
    file_type: str
    total_pages: int = 0
    pages: list[ExtractedPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def char_count(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())


class TextExtractor:
    """Extract text from various document formats."""

    SUPPORTED_TYPES = {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "md": "text/markdown",
        "csv": "text/csv",
        "json": "application/json",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def extract(self, file_bytes: bytes, file_name: str, file_type: str = "") -> ExtractedDocument:
        """Extract text from a file's bytes."""
        ext = Path(file_name).suffix.lower().lstrip(".")
        if not file_type:
            file_type = self.SUPPORTED_TYPES.get(ext, "application/octet-stream")

        if ext == "pdf":
            return self._extract_pdf(file_bytes, file_name)
        elif ext == "docx":
            return self._extract_docx(file_bytes, file_name)
        elif ext in ("xlsx",):
            return self._extract_xlsx(file_bytes, file_name)
        elif ext in ("txt", "md", "csv", "json"):
            return self._extract_text(file_bytes, file_name, ext)
        else:
            return ExtractedDocument(
                file_name=file_name,
                file_type=file_type,
                error=f"Unsupported file type: {ext}",
            )

    def _extract_pdf(self, file_bytes: bytes, file_name: str) -> ExtractedDocument:
        """Extract text from PDF using pypdf."""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append(ExtractedPage(page_number=i, text=text))
            metadata = {}
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                }
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/pdf",
                total_pages=len(pages),
                pages=pages,
                metadata=metadata,
            )
        except Exception as e:
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/pdf",
                error=f"PDF extraction failed: {str(e)}",
            )

    def _extract_docx(self, file_bytes: bytes, file_name: str) -> ExtractedDocument:
        """Extract text from DOCX using python-docx (optional)."""
        try:
            import docx  # type: ignore
        except ImportError:
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                error="python-docx not installed",
            )
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                total_pages=1,
                pages=[ExtractedPage(page_number=1, text=text)],
                metadata={},
            )
        except Exception as e:
            return ExtractedDocument(
                file_name=file_name,
                file_type="docx",
                error=f"DOCX extraction failed: {str(e)}",
            )

    def _extract_xlsx(self, file_bytes: bytes, file_name: str) -> ExtractedDocument:
        """Extract text from XLSX using openpyxl (optional)."""
        try:
            import openpyxl  # type: ignore
        except ImportError:
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                error="openpyxl not installed",
            )
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            lines = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                for row in ws.iter_rows(values_only=True):
                    row_text = " | ".join(
                        str(c) for c in row if c is not None
                    )
                    if row_text:
                        lines.append(f"[{sheet}] {row_text}")
            text = "\n".join(lines)
            return ExtractedDocument(
                file_name=file_name,
                file_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                total_pages=1,
                pages=[ExtractedPage(page_number=1, text=text)],
                metadata={"sheets": wb.sheetnames},
            )
        except Exception as e:
            return ExtractedDocument(
                file_name=file_name,
                file_type="xlsx",
                error=f"XLSX extraction failed: {str(e)}",
            )

    def _extract_text(self, file_bytes: bytes, file_name: str, ext: str) -> ExtractedDocument:
        """Extract text from plain text files."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            return ExtractedDocument(
                file_name=file_name,
                file_type=self.SUPPORTED_TYPES.get(ext, "text/plain"),
                total_pages=1,
                pages=[ExtractedPage(page_number=1, text=text)],
                metadata={},
            )
        except Exception as e:
            return ExtractedDocument(
                file_name=file_name,
                file_type="text/plain",
                error=f"Text extraction failed: {str(e)}",
            )


def ocr_fallback(file_bytes: bytes, file_name: str) -> ExtractedDocument:
    """Attempt OCR on a PDF/image using pytesseract (optional)."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return ExtractedDocument(
            file_name=file_name,
            file_type="application/pdf",
            error="pytesseract/PIL not installed for OCR",
        )
    # OCR is best-effort; this is a placeholder for integration
    return ExtractedDocument(
        file_name=file_name,
        file_type="application/pdf",
        error="OCR not available in this environment",
    )


# Singleton extractor instance
text_extractor = TextExtractor()