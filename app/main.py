from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import os
import uuid
import io

from app.pdf_service import extract_text_from_pdf
from app.search_service import read_names_from_excel, search_names_in_pages

app = FastAPI()

# Rate limit
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Static & template
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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
        raise HTTPException(status_code=400, detail="Excel dosyası 50MB'dan büyük olamaz.")

    if pdf_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="PDF dosyası 50MB'dan büyük olamaz.")

    # Geçici dosya yolları
    excel_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.xlsx")
    pdf_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.pdf")

    try:
        # Dosyaları kaydet
        with open(excel_path, "wb") as buffer:
            shutil.copyfileobj(excel.file, buffer)

        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(pdf.file, buffer)

        # Excel isimlerini oku
        names = read_names_from_excel(excel_path)

        if not names:
            raise HTTPException(status_code=400, detail="Excel dosyasında isim bulunamadı.")

        # PDF extraction + OCR
        pages = extract_text_from_pdf(pdf_path, names)

        # Arama
        results = search_names_in_pages(names, pages)

        # TXT içeriği RAM'de oluştur
        output_content = ""
        for name, page_list in results.items():
            if page_list:
                pages_str = ", ".join(map(str, page_list))
                output_content += f"{name} - {pages_str}\n"

        if not output_content:
            output_content = "Hiçbir eşleşme bulunamadı."

        file_like = io.BytesIO(output_content.encode("utf-8"))

        return StreamingResponse(
            file_like,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=sonuc.txt"}
        )

    finally:
        # Temp dosyaları temizle
        for path in [excel_path, pdf_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Çok fazla istek gönderdiniz. Lütfen biraz bekleyin."}
    )
