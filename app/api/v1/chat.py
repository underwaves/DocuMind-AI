from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.ingestion import generate_embeddings
from app.services.vector_store import search_similar_chunks
from app.services.rag_engine import generate_rag_response_sync, stream_rag_response

router = APIRouter()

@router.post("", response_model=ChatResponse)
def ask_question(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Standard synchronous RAG response returning full answer and citation list.
    """
    if not request.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")

    # 1. Embed query
    query_vec = generate_embeddings([request.query])[0]

    # 2. Retrieve top-k chunks
    matched_chunks = search_similar_chunks(
        db=db,
        query_embedding=query_vec,
        user_id=current_user.id,
        document_ids=request.document_ids,
        query_text=request.query
    )

    # 3. Generate answer
    answer = generate_rag_response_sync(request.query, matched_chunks)

    # 4. Format citations
    citations = [
        Citation(
            document_id=c["document_id"],
            filename=c["filename"],
            chunk_index=c["chunk_index"],
            page_number=c["page_number"],
            similarity_score=c["similarity_score"],
            snippet=c["content"]
        )
        for c in matched_chunks
    ]

    return ChatResponse(answer=answer, citations=citations)


@router.post("/stream")
async def stream_question(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint.
    Emits events: 'citations', 'delta', 'done'.
    """
    if not request.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")

    # 1. Embed query
    query_vec = generate_embeddings([request.query])[0]

    # 2. Retrieve top-k chunks
    matched_chunks = search_similar_chunks(
        db=db,
        query_embedding=query_vec,
        user_id=current_user.id,
        document_ids=request.document_ids,
        query_text=request.query
    )

    # 3. Return StreamingResponse
    return StreamingResponse(
        stream_rag_response(request.query, matched_chunks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
