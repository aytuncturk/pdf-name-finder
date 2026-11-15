import io
import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.pdf_service import InvalidPDFFile, extract_text_from_pdf
from app.search_service import InvalidExcelFile, read_names_from_excel, search_names_in_pages

app = FastAPI()

# Rate limit
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Static & template
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB


@contextmanager
def temporary_upload_directory():
    directory = Path(tempfile.mkdtemp(prefix="pdf-name-finder-"))
    try:
        yield directory
    finally:
        try:
            shutil.rmtree(directory)
        except OSError as exc:
            logger.error(
                "Geçici yükleme klasörü temizlenemedi (klasör=%s, errno=%s).",
                directory.name, exc.errno,
            )


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/search")
@limiter.limit("5/minute")
async def search(request: Request, excel: UploadFile = File(...), pdf: UploadFile = File(...)):

    # Uzantı kontrolü
    if not excel.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Excel dosyası .xlsx formatında olmalıdır.")

    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF dosyası .pdf formatında olmalıdır.")

    # Dosya boyutu kontrolü
    excel.file.seek(0, 2)
    excel_size = excel.file.tell()
    excel.file.seek(0)

    pdf.file.seek(0, 2)
    pdf_size = pdf.file.tell()
    pdf.file.seek(0)

    if excel_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Excel dosyası 1GB'dan büyük olamaz."
        )

    if pdf_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="PDF dosyası 1GB'dan büyük olamaz."
        )

    try:
        with temporary_upload_directory() as directory:
            excel_path = directory / "input.xlsx"
            pdf_path = directory / "input.pdf"
            with excel.file, pdf.file:
                with excel_path.open("wb") as buffer:
                    shutil.copyfileobj(excel.file, buffer)
                with pdf_path.open("wb") as buffer:
                    shutil.copyfileobj(pdf.file, buffer)

            names = read_names_from_excel(str(excel_path))
            if not names:
                raise HTTPException(status_code=400, detail="Excel dosyasında isim bulunamadı.")

            pages = extract_text_from_pdf(str(pdf_path), names)

        exact, similar = search_names_in_pages(names, pages)

        # TXT içeriği RAM'de oluştur
        output_content = "TAM ESLESMELER\n"
        output_content += "------------------\n"

        for name, page_list in exact.items():
            if page_list:
                pages_str = ", ".join(map(str, page_list))
                output_content += f"{name} - {pages_str}\n"

        output_content += "\n\nBENZER ESLESMELER\n"
        output_content += "------------------\n"

        for name, matches in similar.items():
            for page, score in matches:
                output_content += f"{name} ~ sayfa {page} (benzerlik: %{int(score)})\n"

        file_like = io.BytesIO(output_content.encode("utf-8"))

        return StreamingResponse(
            file_like,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=sonuc.txt"}
        )

    except HTTPException:
        raise
    except InvalidExcelFile as exc:
        raise HTTPException(status_code=400, detail="Excel dosyası okunamadı.") from exc
    except InvalidPDFFile as exc:
        raise HTTPException(status_code=400, detail="PDF dosyası okunamadı.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Arama sırasında bir hata oluştu.") from exc


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Çok fazla istek gönderdiniz. Lütfen biraz bekleyin."}
    )
