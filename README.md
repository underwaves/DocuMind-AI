# 🧠 DocuMind AI: Enterprise RAG & Document Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.8%20Flash-4285F4.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)](tests/)

**DocuMind AI** เป็นแพลตฟอร์มจัดการคลังความรู้และตอบคำถามจากเอกสารระดับองค์กร (Enterprise Retrieval-Augmented Generation - RAG) พัฒนาด้วยสถาปัตยกรรม **Clean Architecture** บน **FastAPI** และ **PostgreSQL + pgvector** เชื่อมต่อโมเดลภาษา **Google Gemini 3.8 Flash** ผ่านการสื่อสารแบบเรียลไทม์ (Server-Sent Events: SSE)

แก้ปัญหาสำคัญขององค์กร: **พนักงานค้นหาเอกสาร/สัญญา/คู่มือยาก และ AI ทั่วไปมักเกิดอาการ Hallucination (มโนข้อมูล)** ระบบนี้สืบค้นเฉพาะข้อมูลจริงในเอกสาร พร้อมแนบการอ้างอิง (Citations) ระบุชื่อไฟล์และเลขหน้าอย่างโปร่งใส

---

## 🏛️ System Architecture

```
                       [ Web Dashboard / Client ]
                                   │
                                   ▼ (HTTP REST / SSE Stream)
        ┌─────────────────────────────────────────────────────────────┐
        │ FastAPI Application Gateway                                 │
        │ ├─ JWT Authentication & User Isolation                      │
        │ ├─ Rate Limiting & OpenAPI Documentation (/docs)           │
        │ └─ Static Dashboard Mount (Tailwind CSS + Marked.js)        │
        └──────────────┬──────────────────────────────┬───────────────┘
                       │                              │
        (Async File Upload)             (Real-time Semantic Query)
                       ▼                              ▼
        ┌──────────────────────────────┐ ┌───────────────────────────┐
        │ Ingestion Worker             │ │ RAG Retrieval & Inference │
        │ ├─ Text Extractor (PDF/MD)   │ │ ├─ Query Embedder         │
        │ ├─ Recursive Text Chunker    │ │ ├─ Cosine Vector Matcher  │
        │ └─ Vector Embedding (Gemini) │ │ ├─ Prompt Augmenter       │
        └──────────────┬───────────────┘ │ └─ Streaming Engine (SSE) │
                       │                 └───────────┬───────────────┘
                       ▼                             │
        ┌────────────────────────────────────────────▼───────────────┐
        │ PostgreSQL + pgvector (or SQLite Local Fallback)          │
        │ ├─ users (Credentials, Roles, Permissions)                 │
        │ ├─ documents (Metadata, Status, File Size)                 │
        │ └─ document_chunks (Index, Page, Content, Vector 768-dim)  │
        └────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Engineering Highlights (จุดเด่นทางเทคนิค)

1. **Production Vector Search (PostgreSQL + pgvector):**
   * ใช้ฐานข้อมูลเชิงสัมพันธ์ร่วมกับส่วนขยาย `pgvector` ค้นหาด้วย Cosine Distance (`<=>`) รองรับการทำ Indexing ประสิทธิภาพสูง
   * มี **Dual-Engine Auto-Fallback**: หากยังไม่ได้เปิด Docker จะสลับไปใช้ Local Vector Store ด้วย `numpy` อัตโนมัติ ทำให้รันโค้ดและทดสอบได้ทันทีโดยระบบไม่ล่ม
2. **Non-Blocking Ingestion Pipeline:**
   * การอัปโหลดเอกสารจะถูกประมวลผลผ่าน Background Tasks เพื่อไม่ให้ Thread หลักของ API ถูกบล็อก (Non-blocking I/O)
3. **Real-time Server-Sent Events (SSE) Streaming:**
   * สตรีมคำตอบแบบ Typewriter ทีละโทเค็นผ่าน HTTP SSE ช่วยลด Time to First Token (TTFT) และยกระดับประสบการณ์ผู้ใช้งาน
4. **Anti-Hallucination & Verifiable Citations:**
   * บังคับให้ Prompt Synthesis อิงจาก Context เท่านั้น และส่ง Metadata การอ้างอิง (เลขหน้า, ชื่อไฟล์, ความแม่นยำ %) กลับมาแสดงในการ์ดอ้างอิง
5. **Multi-Tenant User Isolation:**
   * เอกสารและเวกเตอร์จะถูกผูกกับ `user_id` ทำให้ผู้ใช้ไม่สามารถสืบค้นเอกสารของบุคคลอื่นได้

---

## 📁 โครงสร้างโปรเจกต์ (Clean Architecture)

```
documind-ai/
├── app/
│   ├── api/
│   │   ├── deps.py             # Dependency Injections (DB Session, JWT User Context)
│   │   └── v1/
│   │       ├── auth.py         # Endpoints: /register, /login, /me
│   │       ├── documents.py    # Endpoints: /upload, list, detail, delete
│   │       └── chat.py         # Endpoints: /chat (Sync) & /chat/stream (SSE)
│   ├── core/
│   │   ├── database.py         # SQLAlchemy engine with pgvector auto-detection
│   │   └── security.py         # Bcrypt password hashing & JWT encoding/decoding
│   ├── models/
│   │   ├── user.py             # User entity
│   │   └── document.py         # Document & DocumentChunk with adaptive vector column
│   ├── schemas/                # Pydantic v2 DTOs (Request/Response validation)
│   ├── services/
│   │   ├── ingestion.py        # PDF/MD parser, chunker & Gemini embeddings
│   │   ├── vector_store.py     # Cosine similarity vector search queries
│   │   └── rag_engine.py       # Prompt engineering & SSE streaming generator
│   ├── config.py               # Centralized configuration with Pydantic Settings
│   └── main.py                 # FastAPI application, CORS, Static UI mounting
├── static/                     # Modern Enterprise Web Dashboard
│   ├── index.html              # Tailwind CSS UI
│   ├── app.js                  # SSE Stream reader & UI state manager
│   └── style.css               # Typography & animations
├── tests/                      # Automated Test Suite (Pytest)
│   ├── conftest.py             # In-memory test DB fixtures
│   ├── test_auth.py            # Authentication & JWT test cases
│   ├── test_ingestion.py       # Text extraction & chunking algorithms
│   └── test_api.py             # End-to-end upload & RAG query flow
├── sample_docs/                # ตัวอย่างเอกสารทดสอบ (company_policies.md)
├── docker-compose.yml          # Containerized PostgreSQL + pgvector
├── Dockerfile                  # Multi-stage container build
├── requirements.txt            # Python dependencies
└── .env.example                # Environment variables template
```

---

## 🚀 เริ่มต้นใช้งาน (Quick Start)

### 1. ติดตั้ง Dependencies
```bash
# Clone repository
cd documind-ai

# สร้างและเปิดใช้งาน Virtual Environment
python -m venv .venv
.\.venv\Scripts\activate   # สำหรับ Windows
# source .venv/bin/activate # สำหรับ macOS/Linux

# ติดตั้งแพ็กเกจ
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables
คัดลอกไฟล์ `.env.example` เป็น `.env` และใส่ Google Gemini API Key:
```env
GEMINI_API_KEY="your-gemini-api-key-here"
```
*(หากยังไม่มี API Key ระบบจะรันในโหมดจำลอง (Mock Demo Mode) ให้สามารถทดสอบการทำงานได้ตามปกติ)*

### 3. (ทางเลือก) เปิด PostgreSQL + pgvector ด้วย Docker
```bash
docker compose up -d
```

### 4. รันระบบ
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **เปิด Web Dashboard:** เข้าชมได้ที่ [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive API Documentation:** เข้าชมได้ที่ [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 การรัน Automated Test Suite

รันการทดสอบ Unit & Integration Tests ด้วย `pytest`:
```bash
pytest -v tests/
```
ผลการทดสอบ:
```
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_upload_and_query_flow PASSED
tests/test_auth.py::test_register_and_login PASSED
tests/test_auth.py::test_login_invalid_password PASSED
tests/test_ingestion.py::test_clean_text PASSED
tests/test_ingestion.py::test_chunk_text_splitting PASSED
tests/test_ingestion.py::test_extract_markdown PASSED
======================== 7 passed in 2.74s ========================
```

---

## 📝 ตัวอย่างข้อความสำหรับใส่ใน Resume / LinkedIn Portfolio

> **DocuMind AI — Enterprise RAG & Document Intelligence Platform**
> * *Architected an enterprise-grade Retrieval-Augmented Generation (RAG) platform using **FastAPI**, **PostgreSQL (pgvector)**, and **Google Gemini 3.8 Flash**.*
> * *Implemented asynchronous background document ingestion supporting PDF and Markdown, featuring recursive character chunking with overlap and vector embeddings.*
> * *Engineered a real-time Server-Sent Events (SSE) streaming chat API delivering low-latency responses with verifiable document citations and source page attribution.*
> * *Built secure multi-tenant user isolation with JWT authentication and role-based access control (RBAC).*
> * *Dockerized services with Docker Compose and achieved comprehensive test coverage using **Pytest**.*
