from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class ChunkResponse(BaseModel):
    id: int
    chunk_index: int
    page_number: int
    char_count: int
    content_snippet: str

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    chunks: List[ChunkResponse] = []
