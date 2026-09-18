import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.core.database import init_db, is_pgvector_active
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables and extensions
    init_db()
    yield
    # Shutdown: clean up if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Enterprise RAG & Document Intelligence Platform API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Health Check
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "pgvector_active": is_pgvector_active,
        "gemini_configured": bool(settings.GEMINI_API_KEY)
    }

# Mount Static Files & Serve Frontend
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": f"Welcome to {settings.PROJECT_NAME} API. Visit /docs for OpenAPI specs."}
