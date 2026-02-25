import fitz
import re
from app.utils import normalize_text
from app.ocr_service import ocr_page, is_tesseract_available


def extract_text_from_pdf(path: str, names: list):
    pages = {}
    doc = fitz.open(path)

    tesseract_available = is_tesseract_available()

    for i, page in enumerate(doc):
        page_number = i + 1

        text = page.get_text()
        normalized_text = normalize_text(text)

        # Sayfa boşsa OCR
        if not normalized_text.strip() and tesseract_available:
            text = ocr_page(page)

        # TÜM SAYFALARI EKLE (fuzzy için gerekli)
        pages[page_number] = text

    return pages


def extract_names_from_page(text: str):
    """
    (731) alanındaki isimleri yakalar.
    """
    matches = re.findall(r"\(731\).*?-\s*(.*?)\s*\(", text)
    return [normalize_text(m) for m in matches]
