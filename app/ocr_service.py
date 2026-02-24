import pytesseract
from PIL import Image
import fitz
import io

def is_tesseract_available():
    try:
        pytesseract.get_tesseract_version()
        return True
    except:
        return False

def ocr_page(page):
    pix = page.get_pixmap(dpi=200)
    img_data = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_data))
    return pytesseract.image_to_string(image, lang="tur")