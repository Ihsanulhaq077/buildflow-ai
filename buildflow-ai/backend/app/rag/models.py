"""
RAG models: document chunks, embeddings, and processing status.

Uses pgvector for vector similarity search.
Falls back to JSON array storage when pgvector is unavailable.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey, Integer,
    String, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import FLOAT
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

# Embeddings live in a Postgres array in production and as a JSON array elsewhere
# (SQLite in dev, which cannot render ARRAY at all).
EMBEDDING_TYPE = ARRAY(FLOAT).with_variant(JSON(), "sqlite")


class DocumentStatus(str, Enum):
    """Processing lifecycle of a document in the RAG pipeline."""
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    READY = "READY"
    FAILED = "FAILED"


class DocChunk(BaseMixin, Base):
    """
    A single text chunk from a document, ready for embedding and retrieval.

    Each chunk has:
    - Full text content
    - A positional index within its source document
    - An embedding vector for similarity search (pgvector)
    - Optional metadata: page number, section, character offset
    """
    __tablename__ = "doc_chunks"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_doc_chunk_index"),
        {"comment": "RAG document chunks with embeddings"},
    )

    doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        EMBEDDING_TYPE, nullable=True,
    )  # dimension depends on model; null until embedded
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "doc_id": str(self.doc_id),
            "chunk_index": self.chunk_index,
            "text": self.text,
            "char_count": self.char_count,
            "page": self.page,
            "token_estimate": self.token_estimate,
            "status": self.status,
        }