import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentResponse, DocumentDetailResponse, ChunkResponse
from app.services.ingestion import extract_text_from_file, chunk_text, generate_embeddings

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_EXTENSIONS = {"pdf", "txt", "md", "markdown"}


def process_document_background(document_id: int, file_bytes: bytes, filename: str):
    """Background task to extract, chunk, embed, and store document data."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        # 1. Extract text
        pages_text = extract_text_from_file(file_bytes, filename)
        if not pages_text:
            doc.status = "FAILED"
            doc.error_message = "No readable text found in document."
            db.commit()
            return

        # 2. Chunk text
        chunks = chunk_text(pages_text)
        if not chunks:
            doc.status = "FAILED"
            doc.error_message = "Failed to generate chunks from text."
            db.commit()
            return

        # 3. Generate embeddings
        chunk_contents = [c["content"] for c in chunks]
        embeddings = generate_embeddings(chunk_contents)

        # 4. Save chunks to database
        for i, chunk_data in enumerate(chunks):
            emb = embeddings[i] if i < len(embeddings) else None
            chunk_obj = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                page_number=chunk_data["page_number"],
                char_count=chunk_data["char_count"],
                embedding=emb
            )
            db.add(chunk_obj)

        doc.chunk_count = len(chunks)
        doc.status = "READY"
        db.commit()
        logger.info(f"Successfully processed document {doc.filename} ({len(chunks)} chunks).")

    except Exception as e:
        logger.error(f"Error in background processing of document {document_id}: {e}")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "FAILED"
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = file.filename or "untitled"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Supported formats are: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > 25 * 1024 * 1024:  # 25 MB max
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum limit of 25MB."
        )

    # Create document record
    doc = Document(
        user_id=current_user.id,
        filename=filename,
        file_type=ext,
        file_size=file_size,
        status="PROCESSING"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Dispatch background worker
    background_tasks.add_task(process_document_background, doc.id, file_bytes, filename)

    return doc


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc()).all()
    return docs


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunk_responses = [
        ChunkResponse(
            id=c.id,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            char_count=c.char_count,
            content_snippet=c.content[:150] + ("..." if len(c.content) > 150 else "")
        )
        for c in doc.chunks
    ]

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        error_message=doc.error_message,
        chunks=chunk_responses
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    db.delete(doc)
    db.commit()
    return None
