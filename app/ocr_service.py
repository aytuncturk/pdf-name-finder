from contextlib import closing
import io

import pytesseract
from PIL import Image

def is_tesseract_available():
    try:
        pytesseract.get_tesseract_version()
        return True
    except:
        return False

def ocr_page(page):
    with io.BytesIO(page.get_pixmap(dpi=200).tobytes("png")) as data:
        with closing(Image.open(data)) as image:
            return pytesseract.image_to_string(image, lang="tur")
