"""
Document management API routes.

Endpoints:
- POST /documents/upload     - Upload a new document
- GET  /documents             - List organization documents
- GET  /documents/{doc_id}    - Get document details
- DELETE /documents/{doc_id}  - Soft-delete a document
- POST /documents/{doc_id}/access - Grant access to a user
- GET  /documents/{doc_id}/versions - List document versions
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.documents.models import Document, DocVersion
from app.deps import get_current_user, org_scoped, require_permission
from app.models import User
from app.rag.schemas import (
    DocAccessPolicyIn,
    DocAccessPolicyOut,
    DocSearchRequest,
    DocSearchResponse,
    DocumentProcessingStatus,
    EmbeddingConfig,
    ReprocessRequest,
    UploadResponse,
)
from app.rag.service import RagService
from app.rag.embedder import embedding_service
from app.documents.service import DocumentService

log = logging.getLogger("buildflow.documents.routes")
router = APIRouter(tags=["documents"])

PERM_READ = require_permission("documents.read")
PERM_UPLOAD = require_permission("documents.upload")
PERM_WRITE = require_permission("documents.write")


@router.post("/documents/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = "",
    project_id: Optional[UUID] = None,
    tags: Optional[str] = "",
    request: Request = None,
    user: User = Depends(PERM_UPLOAD),
    db: Session = Depends(get_db),
):
    """Upload a document file."""
    org_id = user.organization_id
    file_bytes = await file.read()
    file_type = file.content_type or "application/octet-stream"
    mime_type = file.content_type or "application/octet-stream"

    # Validate file size (100 MB limit)
    max_size = 100 * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {len(file_bytes)} bytes (max {max_size})",
        )

    service = DocumentService(db, org_id)
    doc = service.upload_file(
        file_bytes=file_bytes,
        file_name=file.filename,
        file_type=file_type,
        mime_type=mime_type,
        description=description or "",
        project_id=project_id,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else [],
    )

    # Trigger RAG processing (async in production)
    try:
        rag_service = RagService(db, org_id)
        rag_service.process_document(str(doc.id))
    except Exception as e:
        log.warning(f"RAG processing failed for document {doc.id}: {e}")

    return UploadResponse(
        doc_id=str(doc.id),
        name=doc.name,
        file_name=doc.file_name,
        version=doc.version,
        status=doc.status,
    )


@router.get("/documents", response_model=list)
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    file_type: Optional[str] = None,
    project_id: Optional[UUID] = None,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """List documents for the organization."""
    stmt = select(Document).where(
        Document.organization_id == user.organization_id,
        Document.deleted_at.is_(None),
    )
    if search:
        stmt = stmt.where(Document.name.ilike(f"%{search}%"))
    if file_type:
        stmt = stmt.where(Document.file_type == file_type)
    if project_id:
        stmt = stmt.where(Document.project_id == project_id)
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    docs = db.scalars(stmt).all()
    return [doc.__dict__ for doc in docs]


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: UUID,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """Get document details."""
    stmt = select(Document).where(
        Document.organization_id == user.organization_id,
        Document.id == doc_id,
        Document.deleted_at.is_(None),
    )
    doc = db.scalar(stmt)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Soft-delete a document."""
    stmt = select(Document).where(
        Document.organization_id == user.organization_id,
        Document.id == doc_id,
    )
    doc = db.scalar(stmt)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.deleted_at = db.func.now()
    db.commit()


@router.get("/documents/{doc_id}/versions", response_model=list)
async def list_versions(
    doc_id: UUID,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """List document versions."""
    stmt = select(DocVersion).where(DocVersion.document_id == doc_id).order_by(DocVersion.version)
    versions = db.scalars(stmt).all()
    return [v.__dict__ for v in versions]


@router.post("/documents/{doc_id}/access", response_model=DocAccessPolicyOut)
async def grant_document_access(
    doc_id: UUID,
    body: DocAccessPolicyIn,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Grant document access to a user."""
    stmt = select(Document).where(
        Document.organization_id == user.organization_id,
        Document.id == doc_id,
    )
    doc = db.scalar(stmt)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    service = DocumentService(db, user.organization_id)
    policy = service.grant_access(
        doc_id=doc_id,
        user_id=body.user_id,
        can_read=body.can_read,
        can_write=body.can_write,
        granted_by=user.id,
        expires_at=body.expires_at,
    )
    return policy


# --- RAG integration endpoints ---

@router.post("/rag/search", response_model=DocSearchResponse)
async def search_chunks(
    body: DocSearchRequest,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """Semantic search over document chunks."""
    org_id = user.organization_id
    service = RagService(db, org_id)
    results = service.search(
        query=body.query,
        top_k=body.top_k,
        doc_ids=body.doc_ids,
        threshold=body.similarity_threshold,
    )
    return DocSearchResponse(
        results=results["results"],
        query=results["query"],
        total_results=results["total_results"],
    )


@router.post("/rag/process/{doc_id}")
async def process_document(
    doc_id: UUID,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Process a single document through the RAG pipeline."""
    org_id = user.organization_id
    stmt = select(Document).where(
        Document.organization_id == org_id,
        Document.id == doc_id,
    )
    doc = db.scalar(stmt)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    rag_service = RagService(db, org_id)
    result = rag_service.process_document(str(doc.id))
    return result


@router.post("/rag/process-all")
async def process_all_documents(
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Process all documents through RAG pipeline."""
    org_id = user.organization_id
    rag_service = RagService(db, org_id)
    result = rag_service.process_all_documents(force=False)
    return result


@router.get("/rag/status/{doc_id}", response_model=DocumentProcessingStatus)
async def get_rag_status(
    doc_id: UUID,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """Get RAG processing status for a document."""
    org_id = user.organization_id
    rag_service = RagService(db, org_id)
    status = rag_service.get_processing_status(str(doc_id))
    return DocumentProcessingStatus(**status)


@router.post("/rag/reprocess")
async def reprocess_documents(
    body: ReprocessRequest,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Reprocess documents (all or selected)."""
    org_id = user.organization_id
    rag_service = RagService(db, org_id)
    result = rag_service.process_all_documents(force=body.force)
    return result


@router.post("/rag/cleanup")
async def cleanup_chunks(
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Cleanup stale chunks."""
    org_id = user.organization_id
    rag_service = RagService(db, org_id)
    deleted = rag_service.cleanup_expired_chunks(days=30)
    return {"chunks_deleted": deleted}


@router.post("/rag/embedding-config")
async def update_embedding_config(
    body: EmbeddingConfig,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Update embedding model configuration."""
    embedding_service.initialize(
        config=body.model_dump(exclude_unset=True)
    )
    return {"model_name": body.model_name, "dimension": body.dimension}