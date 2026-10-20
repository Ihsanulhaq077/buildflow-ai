"""Pydantic schemas for the RAG module."""
from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocChunkBase(BaseModel):
    doc_id: UUID
    chunk_index: int
    text: str
    char_count: int = 0
    page: Optional[int] = None
    token_estimate: int = 0


class DocChunkCreate(DocChunkBase):
    pass


class DocChunkUpdate(BaseModel):
    text: Optional[str] = None
    embedding: Optional[List[float]] = None
    token_estimate: Optional[int] = None
    status: Optional[str] = None


class DocChunkOut(DocChunkBase):
    id: UUID
    embedding: Optional[List[float]] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocChunkSearchResult(BaseModel):
    """A chunk returned by a similarity search with its relevance score."""
    chunk: DocChunkOut
    score: float
    distance: float  # lower = more similar


class DocSearchRequest(BaseModel):
    """Request payload for a semantic search over document chunks."""
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)
    doc_ids: Optional[List[UUID]] = None  # optional filter by document
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)


class DocSearchResponse(BaseModel):
    results: List[DocChunkSearchResult]
    query: str
    total_results: int


class DocumentProcessingStatus(BaseModel):
    """Current processing state of a document in the RAG pipeline."""
    doc_id: UUID
    status: str  # one of DocumentStatus values
    progress: int = Field(..., ge=0, le=100)
    error: Optional[str] = None
    chunks_created: int = 0
    chunks_embedded: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ReprocessRequest(BaseModel):
    """Request to re-process a document (or all documents)."""
    doc_ids: Optional[List[UUID]] = None
    force: bool = False  # if true, delete existing chunks and reprocess


class EmbeddingConfig(BaseModel):
    """Configuration for the embedding model."""
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    batch_size: int = 32
    use_gpu: bool = False


# Upload response schemas
class UploadResponse(BaseModel):
    doc_id: UUID = Field(..., description="The document ID in the system")
    name: str = Field(..., description="Original file name")
    file_name: str = Field(..., description="Stored file name")
    file_type: str = Field(..., description="Document file type (PDF, DOCX, TXT, etc.)")
    version: int = Field(..., description="Document version number")
    status: str = Field(..., description="Document status (UPLOADED, PROCESSING, READY, FAILED)")
    storage_path: Optional[str] = Field(None, description="Path to stored file")
    size: int = Field(..., description="File size in bytes")


# Document access policy schemas
class DocAccessPolicyIn(BaseModel):
    """Input for granting document access."""
    user_id: UUID = Field(..., description="User ID to grant access to")
    can_read: bool = Field(True, description="Grant read access")
    can_write: bool = Field(False, description="Grant write access")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration time")


class DocAccessPolicyOut(BaseModel):
    """Output representation of document access policy."""
    id: UUID = Field(..., description="Policy ID")
    document_id: UUID = Field(..., description="Document ID")
    user_id: UUID = Field(..., description="User ID granted access")
    can_read: bool = Field(True, description="Grant read access")
    can_write: bool = Field(False, description="Grant write access")
    granted_by: UUID | None = Field(None, description="Who granted access")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When access was granted")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration time")


# Search result helper
class SearchHelper(BaseModel):
    """Helper for presenting search results."""
    score: float = Field(..., ge=0, le=1, description="Similarity score")
    distance: float = Field(0, ge=0, description="Distance (1 - score)")


class UploadResult(BaseModel):
    """Result of document upload."""
    doc_id: UUID
    message: str
    chunks_created: int = 0
    chunks_embedded: int = 0


# Legacy aliases
DocChunkSearch = DocChunkSearchResult