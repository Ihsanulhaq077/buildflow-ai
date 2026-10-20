"""
API routes for the RAG module.

Endpoints:
- POST /rag/search          - semantic search over document chunks
- POST /rag/process/{doc_id} - process a single document through RAG pipeline
- POST /rag/process-all      - process all organization documents
- GET  /rag/status/{doc_id}  - processing status for a document
- POST /rag/reprocess        - re-process documents (all or selected)
- POST /rag/cleanup          - garbage collect stale chunks
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, org_scoped, require_permission
from app.models import User
from app.rag.schemas import (
    DocumentProcessingStatus,
    DocSearchRequest,
    DocSearchResponse,
    DocChunkSearchResult,
    EmbeddingConfig,
    ReprocessRequest,
)
from app.rag.service import DocumentProcessor, RagService

log = logging.getLogger("buildflow.rag")
router = APIRouter(tags=["rag"])

PERM_READ = require_permission("documents.read")
PERM_UPLOAD = require_permission("documents.upload")
PERM_PROCESS = require_permission("rag.process")  # custom permission to be added


@router.post("/rag/search", response_model=DocSearchResponse)
async def search_chunks(
    body: DocSearchRequest,
    user: User = Depends(get_current_user),
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
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process a single document through the full RAG pipeline."""
    org_id = user.organization_id
    # Verify document exists and belongs to org
    from app.documents.models import Document

    doc = db.scalar(
        org_scoped(Document, user)
        .where(Document.id == doc_id)
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found or not owned by organization",
        )

    # Trigger async processing (in production, this would go to a queue)
    try:
        processor = DocumentProcessor(db, doc_id)
        result = processor.process(doc.text if hasattr(doc, "text") else "")
        return {
            "status": "processing_started",
            "doc_id": doc_id,
            "chunks_created": result["chunks_created"],
            "chunks_embedded": result["chunks_embedded"],
        }
    except Exception as e:
        log.exception(f"Failed to process document {doc_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.post("/rag/process-all")
async def process_all_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process all documents for the organization through RAG pipeline."""
    org_id = user.organization_id
    service = RagService(db, org_id)
    result = service.process_all_documents(force=False)
    return {
        "status": "processing_started",
        "organization_id": str(org_id),
        "documents_processed": result["processed"],
        "results": result["results"],
    }


@router.get("/rag/status/{doc_id}", response_model=DocumentProcessingStatus)
async def get_processing_status(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the processing status of a single document."""
    org_id = user.organization_id
    from app.documents.models import Document

    doc = db.scalar(
        org_scoped(Document, user)
        .where(Document.id == doc_id)
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found or not owned by organization",
        )

    service = RagService(db, org_id)
    status = service.get_processing_status(doc_id)
    return DocumentProcessingStatus(**status)


@router.post("/rag/reprocess")
async def reprocess_documents(
    body: ReprocessRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-process documents (all or selected)."""
    org_id = user.organization_id
    service = RagService(db, org_id)
    result = service.process_all_documents(force=body.force)
    return {
        "status": "reprocessing_started",
        "organization_id": str(org_id),
        "force": body.force,
        "documents_processed": result["processed"],
    }


@router.post("/rag/cleanup")
async def cleanup_chunks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Garbage collect chunks from deleted documents."""
    org_id = user.organization_id
    service = RagService(db, org_id)
    result = service.cleanup_expired_chunks(days=30)
    return {
        "status": "cleanup_completed",
        "organization_id": str(org_id),
        "chunks_deleted": result["chunks_deleted"],
    }


@router.post("/rag/embedding-config")
async def update_embedding_config(
    body: EmbeddingConfig,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the embedding model configuration."""
    org_id = user.organization_id
    # Save to org settings or user preferences; for now, just update service
    embedding_service.initialize(
        config=body.model_dump(exclude_unset=True)
    )
    return {
        "status": "config_updated",
        "organization_id": str(org_id),
        "model_name": body.model_name,
        "dimension": body.dimension,
    }