"""API v1 router registry"""
from fastapi import APIRouter
from app.api.v1 import auth, documents, chat, settings as api_settings

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["RAG Chat"])
api_router.include_router(api_settings.router, prefix="/settings", tags=["Settings"])
