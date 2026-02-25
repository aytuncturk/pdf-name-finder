# PDF Name Finder

High-performance PDF name scanning system with OCR and fuzzy matching support.

Designed for large structured PDFs (3,000+ pages) such as:
- Official Gazette documents
- Trademark bulletins
- Patent publications
- Legal announcements

---

## 🔍 What It Does

PDF Name Finder:

- Reads names from an Excel file (.xlsx)
- Scans large PDF documents
- Performs:
  - Exact matching
  - Fuzzy similarity matching
- Supports OCR for image-based pages
- Outputs structured TXT results

---

## ⚙️ Features

- ⚡ Handles 3000+ page PDFs
- 🧠 RapidFuzz similarity detection
- 🔎 (731) field extraction support
- 🖼 OCR fallback with Tesseract
- 📦 Dockerized production setup
- 🔐 Rate limited API
- 💾 RAM-based result generation (no disk output)

---

## 🧩 Tech Stack

- FastAPI
- PyMuPDF (fitz)
- Tesseract OCR
- RapidFuzz
- Docker
- Uvicorn

---

## 📂 Project Structure

```
app/
├── main.py
├── pdf_service.py
├── search_service.py
├── ocr_service.py
├── utils.py
templates/
static/
Dockerfile
docker-compose.yml
requirements.txt
```


---

## 🐳 Run with Docker

Build:

```
docker build -t pdf-name-finder .
```

Run:

```
docker run -d \
  --name pdf-finder \
  -p 8000:8000 \
  pdf-name-finder
```


Access:


http://localhost:8000


---
```
TAM ESLESMELER
------------------
NAME - page_numbers

BENZER ESLESMELER
------------------
NAME ~ sayfa X (benzerlik: %score)
```


---

## 🚀 Performance Notes

Optimized for:

- Structured legal PDFs
- Trademark bulletins
- High-volume name detection
- CPU-safe processing
- Smart OCR fallback

---

## 🔒 Security

- File size limit (1GB)
- Extension validation
- Rate limiting
- Temporary file isolation

---

## 📌 Status

Production-ready stable version.

---

## 📈 Roadmap (Future)

- Multi-user SaaS version
- Background job processing
- Payment integration
- Admin dashboard
- API access

---

## 👤 Author

Developed by Aytunç Türk
