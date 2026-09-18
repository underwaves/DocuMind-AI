from pydantic import BaseModel
from typing import List, Optional

class Citation(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    page_number: int
    similarity_score: float
    snippet: str

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    query: str
    document_ids: Optional[List[int]] = None  # If None, search all accessible documents
    conversation_history: Optional[List[ChatMessage]] = []
    stream: bool = True

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
