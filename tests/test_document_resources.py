import unittest
from unittest.mock import patch

import fitz
from PIL import Image

from app.pdf_service import extract_text_from_pdf


class DocumentResourceTests(unittest.TestCase):
    def test_pdf_and_ocr_resources_close_after_processing(self):
        with fitz.open() as blank:
            blank.new_page(width=72, height=72)
            pdf_bytes = blank.tobytes()

        for ocr_fails in (False, True):
            with self.subTest(ocr_fails=ocr_fails):
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                with (
                    patch("app.pdf_service.fitz.open", return_value=doc),
                    patch("app.pdf_service.is_tesseract_available", return_value=True),
                    patch("app.ocr_service.Image.open", wraps=Image.open) as decode,
                    patch("app.ocr_service.pytesseract.image_to_string") as ocr,
                ):
                    if ocr_fails:
                        ocr.side_effect = RuntimeError("synthetic OCR failure")
                        with self.assertRaisesRegex(RuntimeError, "synthetic OCR failure"):
                            extract_text_from_pdf("synthetic.pdf", [])
                    else:
                        ocr.return_value = "sentetik"
                        self.assertEqual(extract_text_from_pdf("synthetic.pdf", []), {1: "sentetik"})

                self.assertTrue(doc.is_closed)
                decode.assert_called_once()
                self.assertTrue(decode.call_args.args[0].closed)
                ocr.assert_called_once()
                image = ocr.call_args.args[0]
                self.assertEqual(ocr.call_args.kwargs, {"lang": "tur"})
                with self.assertRaises(ValueError):
                    image.getpixel((0, 0))
