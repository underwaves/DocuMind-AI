import os
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.config import settings

router = APIRouter()

class ApiKeyUpdate(BaseModel):
    api_key: str

@router.get("/status")
def get_settings_status():
    return {
        "has_api_key": bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5),
        "chat_model": settings.CHAT_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL
    }

@router.post("/api-key")
def update_api_key(payload: ApiKeyUpdate):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API Key cannot be empty.")

    # 1. Update runtime settings
    settings.GEMINI_API_KEY = key
    os.environ["GEMINI_API_KEY"] = key

    # 2. Re-initialize GenAI Client in services
    try:
        from google import genai
        import app.services.ingestion as ing_service
        ing_service.genai_client = genai.Client(api_key=key)
    except Exception as e:
        pass

    # 3. Persist to .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "GEMINI_API_KEY=" in content:
                content = re.sub(r'GEMINI_API_KEY=.*', f'GEMINI_API_KEY="{key}"', content)
            else:
                content += f'\nGEMINI_API_KEY="{key}"\n'
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    return {"status": "success", "message": "Gemini API Key updated successfully."}
