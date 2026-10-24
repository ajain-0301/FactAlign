"""Text extraction for uploads: .txt .md .pdf .docx"""
import io

from app.core.errors import AppError


def extract_document(filename: str, data: bytes) -> dict:
    pages = None
    name = filename.lower()
    if name.endswith((".txt", ".md", ".text")):
        for enc in ("utf-8-sig", "utf-16", "cp1252"):
            try:
                text = data.decode(enc)
                break
            except UnicodeError:
                continue
        else:
            raise AppError("Could not decode the text file. Save it as UTF-8 and try again.", 422)
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise AppError("This PDF is password-protected.", 422)
            texts = [(p.extract_text() or "").replace("\x00", "").strip() for p in reader.pages]
            pages = []
            parts = []
            offset = 0
            for number, page_text in enumerate(texts, 1):
                if not page_text:
                    continue
                if parts:
                    offset += 1
                pages.append({"page": number, "start": offset, "end": offset + len(page_text)})
                parts.append(page_text)
                offset += len(page_text)
            text = "\n".join(parts)
        except AppError:
            raise
        except Exception:  # noqa: BLE001
            raise AppError("Could not read this PDF file.", 422)
        if not text.strip():
            raise AppError("No selectable text found in the PDF (scanned PDFs need OCR, which is not included).", 422)
    elif name.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception:  # noqa: BLE001
            raise AppError("Could not read this Word document.", 422)
    else:
        raise AppError("Unsupported file type. Upload .txt, .md, .pdf or .docx.", 415)
    text = text.replace("\x00", "").strip()
    if not text:
        raise AppError("The file contains no text.", 422)
    return {"text": text, "pages": pages}


def extract_text(filename: str, data: bytes) -> str:
    """Compatibility helper for existing callers."""
    return extract_document(filename, data)["text"]
