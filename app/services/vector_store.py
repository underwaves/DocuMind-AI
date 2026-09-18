import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session
from app.core.database import is_pgvector_active
from app.models.document import Document, DocumentChunk
from app.config import settings

logger = logging.getLogger(__name__)


def search_similar_chunks(
    db: Session,
    query_embedding: List[float],
    user_id: int,
    document_ids: Optional[List[int]] = None,
    top_k: int = settings.TOP_K_RETRIEVAL,
    query_text: str = ""
) -> List[Dict[str, Any]]:
    """
    Retrieves the most semantically relevant document chunks using vector similarity.
    Enforces user isolation and optional document filtering.
    Includes smart metadata preamble augmentation for author/title/overview questions.
    """
    if is_pgvector_active:
        results = _search_pgvector(db, query_embedding, user_id, document_ids, top_k)
    else:
        results = _search_sqlite(db, query_embedding, user_id, document_ids, top_k)

    # Smart preamble augmentation for metadata/overview queries
    meta_keywords = ["ใคร", "เจ้าของ", "คนทำ", "ผู้แต่ง", "ผู้เขียน", "วิจัย", "author", "creator", "publisher", "who", "หน่วยงาน", "องค์กร", "ชื่อ", "สรุป", "overview"]
    is_meta = any(k in query_text.lower() for k in meta_keywords) if query_text else False

    if is_meta:
        # Check if first page/preamble chunk is already in results
        has_page1 = any(r.get("page_number", 0) <= 2 for r in results)
        if not has_page1:
            # Fetch preamble chunks (page 1 or 2)
            preamble_query = (
                db.query(DocumentChunk, Document)
                .join(Document, DocumentChunk.document_id == Document.id)
                .filter(Document.user_id == user_id, Document.status == "READY")
            )
            if document_ids:
                preamble_query = preamble_query.filter(Document.id.in_(document_ids))
            
            preamble_chunks = (
                preamble_query.filter(DocumentChunk.page_number <= 2)
                .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
                .limit(2)
                .all()
            )
            for c, d in preamble_chunks:
                results.insert(0, {
                    "chunk_id": c.id,
                    "document_id": d.id,
                    "filename": d.filename,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "content": c.content,
                    "similarity_score": 0.88
                })

    return results[:top_k]


def _search_pgvector(
    db: Session,
    query_embedding: List[float],
    user_id: int,
    document_ids: Optional[List[int]],
    top_k: int
) -> List[Dict[str, Any]]:
    """Native PostgreSQL pgvector search using cosine distance (<=> operator)."""
    # Join Document to enforce user ownership
    query = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.user_id == user_id)
        .filter(Document.status == "READY")
    )

    if document_ids:
        query = query.filter(Document.id.in_(document_ids))

    # In pgvector: cosine distance is 1 - cosine_similarity (0 = identical, 2 = opposite)
    # Order by ascending cosine distance
    results = (
        query.order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
        .all()
    )

    matched = []
    q_vec = np.array(query_embedding)
    q_norm = np.linalg.norm(q_vec)

    for chunk, doc in results:
        # Calculate similarity score: 1 - distance
        score = 0.85  # Default baseline
        if chunk.embedding is not None and q_norm > 0:
            c_vec = np.array(chunk.embedding)
            c_norm = np.linalg.norm(c_vec)
            if c_norm > 0:
                score = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))

        matched.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "filename": doc.filename,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "similarity_score": round(max(0.0, min(1.0, score)), 4)
        })

    return matched


def _search_sqlite(
    db: Session,
    query_embedding: List[float],
    user_id: int,
    document_ids: Optional[List[int]],
    top_k: int
) -> List[Dict[str, Any]]:
    """Local vector search using numpy cosine similarity over stored embeddings."""
    query = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.user_id == user_id)
        .filter(Document.status == "READY")
    )

    if document_ids:
        query = query.filter(Document.id.in_(document_ids))

    all_chunks = query.all()
    if not all_chunks:
        return []

    q_vec = np.array(query_embedding)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return []

    scored_chunks = []
    for chunk, doc in all_chunks:
        if chunk.embedding is None:
            continue
        
        c_vec = np.array(chunk.embedding)
        c_norm = np.linalg.norm(c_vec)
        if c_norm == 0:
            continue

        cosine_sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
        scored_chunks.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "filename": doc.filename,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "similarity_score": round(max(0.0, min(1.0, cosine_sim)), 4)
        })

    # Sort descending by similarity score
    scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_chunks[:top_k]
