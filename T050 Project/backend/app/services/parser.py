"""Document parsing - PDF, DOCX, TXT. Page-level extraction for source attribution."""
import io
import re
from typing import List, Tuple, Optional


def detect_mime(filename: str, content: bytes) -> str:
    fn = filename.lower()
    if fn.endswith(".pdf") or content.startswith(b"%PDF"):
        return "application/pdf"
    if fn.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fn.endswith(".doc"):
        return "application/msword"
    if fn.endswith(".txt") or fn.endswith(".md"):
        return "text/plain"
    return "application/octet-stream"


def extract_pdf_pages(data: bytes) -> Tuple[str, int, List[Tuple[int, str]]]:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        pages: List[Tuple[int, str]] = []
        full_text_parts = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            text = text.strip()
            pages.append((i, text))
            full_text_parts.append(text)
        doc.close()
        return "\n\n".join(full_text_parts), len(pages), pages
    except Exception as e:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = []
            parts = []
            for i, page in enumerate(reader.pages, start=1):
                t = page.extract_text() or ""
                pages.append((i, t))
                parts.append(t)
            return "\n\n".join(parts), len(pages), pages
        except Exception:
            return "", 0, []


def extract_docx(data: bytes) -> Tuple[str, int, List[Tuple[int, str]]]:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        paras = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        text = "\n\n".join(paras)
        # treat as single page; paginate heuristically by ~3000 chars
        pages = []
        chunk = 3000
        for i in range(0, len(text), chunk):
            pages.append((len(pages) + 1, text[i:i + chunk]))
        return text, len(pages), pages
    except Exception:
        return "", 0, []


def extract_text(data: bytes) -> Tuple[str, int, List[Tuple[int, str]]]:
    text = data.decode("utf-8", errors="ignore")
    pages = []
    chunk = 3000
    for i in range(0, len(text), chunk):
        pages.append((len(pages) + 1, text[i:i + chunk]))
    return text, len(pages), pages


def parse_document(filename: str, data: bytes) -> Tuple[str, int, List[Tuple[int, str]], str]:
    mime = detect_mime(filename, data)
    from app.services.azure_doc_intel import azure_doc_intelligence_service
    if azure_doc_intelligence_service.is_available():
        text, pages, page_text, _ = azure_doc_intelligence_service.analyze_document_bytes(data, mime_type=mime)
    elif mime == "application/pdf":
        text, pages, page_text = extract_pdf_pages(data)
    elif "officedocument" in mime or mime == "application/msword":
        text, pages, page_text = extract_docx(data)
    else:
        text, pages, page_text = extract_text(data)
    text = _clean_text(text)
    page_text = [(i, _clean_text(t)) for i, t in page_text]
    return text, pages, page_text, mime


def _clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"\u00a0", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
