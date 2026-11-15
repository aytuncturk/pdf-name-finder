import io
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from threading import Event
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app import main, pdf_service


def workbook_bytes(*names):
    book = Workbook()
    for name in names:
        book.active.append([name])
    with io.BytesIO() as buffer:
        book.save(buffer)
        book.close()
        return buffer.getvalue()


def pdf_bytes(*pages):
    with fitz.open() as document:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        return document.tobytes()


class UploadCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.excel = workbook_bytes("Örnek Öğe", "Deneme Marka")
        cls.pdf = pdf_bytes("ORNEK OGE", "(731) - Deneme Morka (test)")

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.sibling = self.root / "pdf-name-finder-preexisting"
        self.sibling.mkdir()
        (self.sibling / "keep.pdf").write_bytes(b"synthetic sentinel")
        # Redirect only the application's request directories into the test sandbox.
        temp_api = stack.enter_context(patch.object(main, "tempfile", wraps=tempfile))
        temp_api.mkdtemp.side_effect = partial(tempfile.mkdtemp, dir=self.root)
        stack.enter_context(patch.object(main.limiter, "enabled", False))
        self.ocr_available = stack.enter_context(
            patch.object(pdf_service, "is_tesseract_available", return_value=False)
        )

    def tearDown(self):
        self.assertEqual(list(self.root.iterdir()), [self.sibling])
        self.assertEqual((self.sibling / "keep.pdf").read_bytes(), b"synthetic sentinel")

    def post(self, excel=None, pdf=None, excel_filename="synthetic.xlsx"):
        files = {
            "excel": (excel_filename, self.excel if excel is None else excel),
            "pdf": ("synthetic.pdf", self.pdf if pdf is None else pdf),
        }
        with TestClient(main.app) as client:
            return client.post("/search", files=files)

    def test_home_serves_upload_form_and_progress_handler(self):
        with TestClient(main.app) as client:
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<form id="uploadForm"', response.text)
        self.assertIn('id="progressBar"', response.text)
        self.assertIn("xhr.upload.onprogress", response.text)

    def test_download_preserves_exact_and_fuzzy_results(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["Content-Disposition"], "attachment; filename=sonuc.txt")
        self.assertEqual(response.headers["Content-Type"].split(";")[0], "text/plain")
        self.assertEqual(response.content, (
            "TAM ESLESMELER\n------------------\nÖrnek Öğe - 1\n"
            "\n\nBENZER ESLESMELER\n------------------\n"
            "Deneme Marka ~ sayfa 2 (benzerlik: %91)\n"
        ).encode("utf-8"))

    def test_empty_workbook(self):
        response = self.post(excel=workbook_bytes())
        self.assertEqual(response.status_code, 400, response.text)

    def test_corrupt_excel(self):
        response = self.post(excel=b"synthetic broken xlsx")
        self.assertEqual(response.status_code, 400, response.text)

    def test_corrupt_pdf(self):
        response = self.post(pdf=b"synthetic broken pdf")
        self.assertEqual(response.status_code, 400, response.text)

    def test_invalid_extension(self):
        response = self.post(excel_filename="synthetic.txt")
        self.assertEqual(response.status_code, 400, response.text)

    def test_pdf_size_limit(self):
        self.assertEqual(main.MAX_FILE_SIZE, 1024**3)
        # Exercise the exact boundary without allocating a gigabyte.
        size = max(len(self.excel), len(self.pdf))
        at_limit = self.pdf.ljust(size, b" ")
        with patch.object(main, "MAX_FILE_SIZE", size):
            self.assertEqual(self.post(pdf=at_limit).status_code, 200)
            self.assertEqual(self.post(pdf=at_limit + b" ").status_code, 400)

    def test_ocr_failure(self):
        scanned_pdf = pdf_bytes("")
        self.ocr_available.return_value = True
        with patch.object(pdf_service, "ocr_page", side_effect=RuntimeError("synthetic OCR failure")) as ocr:
            response = self.post(pdf=scanned_pdf)
        self.assertEqual(response.status_code, 500, response.text)
        ocr.assert_called_once()

    def test_search_failure(self):
        with patch.object(main, "search_names_in_pages", side_effect=RuntimeError("synthetic failure")):
            response = self.post()
        self.assertEqual(response.status_code, 500, response.text)

    def test_partial_second_file_is_removed_with_the_first(self):
        targets = []
        contents_at_failure = []

        def interrupt_second_copy(source, target):
            targets.append(Path(target.name))
            if len(targets) == 1:
                return shutil.copyfileobj(source, target)
            target.write(source.read(4))
            target.flush()
            contents_at_failure.extend(path.read_bytes() for path in targets)
            raise OSError("synthetic write failure")

        with patch.object(main, "shutil", wraps=shutil) as file_ops:
            file_ops.copyfileobj.side_effect = interrupt_second_copy
            response = self.post()
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(contents_at_failure, [self.excel, self.pdf[:4]])
        self.assertEqual(targets[0].parent, targets[1].parent)
        self.assertFalse(targets[0].parent.exists())

    def test_overlapping_requests_have_independent_files_and_results(self):
        first_excel, first_pdf = workbook_bytes("Deneme Bir"), pdf_bytes("Deneme Bir")
        second_excel, second_pdf = workbook_bytes("Deneme Iki"), pdf_bytes("Deneme Iki")
        first_ready, release_first = Event(), Event()
        directories = {}
        read_excel = main.read_names_from_excel

        def hold_first_request(path):
            names = read_excel(path)
            directories[names[0]] = Path(path).parent
            if names[0] == "Deneme Bir":
                first_ready.set()
                if not release_first.wait(timeout=30):
                    raise TimeoutError("second request did not finish")
            return names

        with patch.object(main, "read_names_from_excel", side_effect=hold_first_request), \
             ThreadPoolExecutor(max_workers=1) as worker:
            pending = worker.submit(self.post, first_excel, first_pdf)
            try:
                self.assertTrue(first_ready.wait(timeout=15))
                second = self.post(second_excel, second_pdf)
                self.assertEqual(second.status_code, 200, second.text)
                self.assertIn("Deneme Iki - 1\n", second.text)
                self.assertNotIn("Deneme Bir", second.text)
                first_dir, second_dir = directories["Deneme Bir"], directories["Deneme Iki"]
                self.assertNotEqual(first_dir, second_dir)
                self.assertEqual(first_dir.parent, self.root)
                self.assertEqual(second_dir.parent, self.root)
                self.assertFalse(second_dir.exists())
                self.assertEqual(next(first_dir.glob("*.pdf")).read_bytes(), first_pdf)
                self.assertEqual(next(first_dir.glob("*.xlsx")).read_bytes(), first_excel)
            finally:
                release_first.set()
            first = pending.result(timeout=15)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertIn("Deneme Bir - 1\n", first.text)
        self.assertNotIn("Deneme Iki", first.text)

    def test_cleanup_failure_is_logged_without_disclosing_inputs_or_masking_status(self):
        marker = "SYNTHETIC_PRIVATE_MARKER"
        with patch.object(main, "shutil", wraps=shutil) as file_ops:
            file_ops.rmtree.side_effect = PermissionError(marker)
            with self.assertLogs(main.__name__, level="WARNING") as logs:
                ok = self.post(excel=workbook_bytes(marker), excel_filename=f"{marker}.xlsx")
                bad = self.post(excel=workbook_bytes())
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(bad.status_code, 400, bad.text)
        self.assertGreaterEqual(len(logs.records), 2)
        self.assertNotIn(marker, "\n".join(logs.output))
        # Only these two synthetic request directories could not be removed.
        failed_dirs = {Path(call.args[0]) for call in file_ops.rmtree.call_args_list}
        self.assertEqual(len(failed_dirs), 2)
        for path in failed_dirs:
            self.assertEqual(path.parent, self.root)
            self.assertNotEqual(path, self.sibling)
            shutil.rmtree(path)
