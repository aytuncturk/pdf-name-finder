import fitz
from app.ocr_service import ocr_page, is_tesseract_available
from app.utils import normalize_text

def extract_text_from_pdf(path: str, names: list):
    pages = {}
    doc = fitz.open(path)

    tesseract_available = is_tesseract_available()

    normalized_names = [normalize_text(n) for n in names]

    for i, page in enumerate(doc):
        page_number = i + 1
        text = page.get_text()

        normalized_text = normalize_text(text)

        # Eğer metin boşsa direkt OCR
        if not normalized_text.strip() and tesseract_available:
            text = ocr_page(page)
            pages[page_number] = text
            continue

        # Eğer metin var ama hiçbir isim eşleşmiyorsa
        if tesseract_available:
            found = any(name in normalized_text for name in normalized_names)

            if not found:
                ocr_text = ocr_page(page)
                text += "\n" + ocr_text

        pages[page_number] = text

    return pages