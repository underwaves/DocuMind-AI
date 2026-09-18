import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, TypeDecorator
from sqlalchemy.orm import relationship
from app.core.database import Base, is_pgvector_active

# Vector column definition that adapts between PostgreSQL pgvector and SQLite JSON
if is_pgvector_active:
    from pgvector.sqlalchemy import Vector
    VectorColumn = Vector(768)
else:
    class SQLiteVector(TypeDecorator):
        impl = Text
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is not None:
                if hasattr(value, "tolist"):
                    value = value.tolist()
                return json.dumps(value)
            return None

        def process_result_value(self, value, dialect):
            if value is not None:
                return json.loads(value)
            return None

    VectorColumn = SQLiteVector()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(50), default="PROCESSING")  # PROCESSING, READY, FAILED
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(VectorColumn, nullable=True)
    page_number = Column(Integer, default=1)
    char_count = Column(Integer, default=0)

    # Relationships
    document = relationship("Document", back_populates="chunks")
