"""
Core RAG service: extract, chunk, embed, and search document text.

Service provides:
- process_document(): full pipeline for one document
- search(): semantic search over document chunks
- get_processing_status(): current pipeline state
- republish_documents(): bulk processing
- cleanup_expired_chunks(): garbage collection
"""
import logging
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.deps import org_scoped
from app.rag.chunker import ChunkerFactory
from app.rag.embedder import embedding_service
from app.rag.extractor import text_extractor
from app.rag.models import DocChunk

log = logging.getLogger("buildflow.rag.service")

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50


class DocumentProcessor:
    """Pipeline processor for a single document."""

    def __init__(self, db: Session, doc_id):
        self.db = db
        self.doc_id = doc_id
        self.chunks: List = []
        self.embedded_count = 0

    def process(self, text: str, metadata: dict = None) -> dict:
        """Run the full extraction/chunking/embedding pipeline."""
        metadata = metadata or {}

        # 1. Chunk text
        self.chunks = self._chunk_text(text)

        # 2. Insert chunks into DB
        self._save_chunks()

        # 3. Embed chunks
        self.embedded_count = self._embed_chunks()

        return {
            "doc_id": str(self.doc_id),
            "chunks_created": len(self.chunks),
            "chunks_embedded": self.embedded_count,
        }

    def _chunk_text(self, text: str) -> List:
        """Split text into chunks using the configured strategy."""
        chunker = ChunkerFactory.create(
            strategy="semantic", chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP
        )
        return chunker.chunk(text)

    def _save_chunks(self):
        """Insert chunks into the database."""
        # Get existing chunk indexes
        existing = [
            chunk.index for chunk in self.db.scalars(
                select(DocChunk).where(DocChunk.doc_id == self.doc_id)
            ).all()
        ]
        for chunk in self.chunks:
            if chunk.index in existing:
                continue
            c = DocChunk(
                doc_id=self.doc_id,
                chunk_index=chunk.index,
                text=chunk.text,
                char_count=chunk.char_count,
                page=chunk.page,
                token_estimate=chunk.token_estimate,
                status="CHUNKED",
            )
            self.db.add(c)
        self.db.commit()

    def _embed_chunks(self) -> int:
        """Generate and store embeddings for chunks."""
        try:
            embedding_service.initialize()
            # Get chunks that need embedding
            stmt = select(DocChunk).where(
                DocChunk.doc_id == self.doc_id,
                DocChunk.embedding.is_(None)
            )
            chunks = self.db.scalars(stmt).all()
            if not chunks:
                return 0

            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = embedding_service.embed(chunk_texts)
            count = 0
            for chunk, embedding in zip(chunks, embeddings):
                if len(embedding) == embedding_service.dimension:
                    chunk.embedding = embedding
                    chunk.status = "EMBEDDED"
                    count += 1
            self.db.commit()
            return count
        except Exception as e:
            log.error(f"Embedding failed for doc {self.doc_id}: {e}")
            self.db.rollback()
            return 0


class RagService:
    """Main RAG service for processing and searching documents."""

    def __init__(self, db: Session, org_id):
        self.db = db
        self.org_id = org_id

    def _get_doc_text(self, doc_id: str) -> str:
        """Get the text content of a document."""
        from app.documents.models import Document

        doc = self.db.scalar(
            select(Document).where(
                Document.id == doc_id,
                Document.organization_id == self.org_id
            )
        )
        if not doc:
            return ""
        # In a real system, you'd retrieve the actual text from storage
        # For now, we'll assume the document has a text attribute or we extract it from storage
        return getattr(doc, "text", "") or f"Document {doc_id} content"

    def process_document(self, doc_id: str) -> dict:
        """Process a single document through the full pipeline."""
        processor = DocumentProcessor(self.db, doc_id)
        return processor.process(self._get_doc_text(doc_id))

    def process_all_documents(self, force: bool = False) -> dict:
        """Process all documents for the organization."""
        from app.documents.models import Document

        docs = self.db.scalars(
            select(Document).where(
                Document.organization_id == self.org_id,
                Document.deleted_at.is_(None)
            )
        ).all()

        results = []
        for doc in docs:
            try:
                if force:
                    # Delete existing chunks
                    self.db.execute(
                        delete(DocChunk).where(DocChunk.doc_id == doc.id)
                    )
                result = self.process_document(str(doc.id))
                results.append(result)
            except Exception as e:
                log.error(f"Failed to process document {doc.id}: {e}")
        return {"processed": len(results), "results": results}

    def search(self, query: str, top_k: int = 5, doc_ids: List[str] = None, threshold: float = 0.5) -> dict:
        """Semantic search over document chunks."""
        embedding_service.initialize()
        query_vec = embedding_service.embed_single(query)

        stmt = (
            select(DocChunk)
            .where(
                DocChunk.doc_id.in_(
                    select(Document.id).where(
                        Document.organization_id == self.org_id,
                        Document.deleted_at.is_(None)
                    )
                ),
                DocChunk.embedding.is_not(None)
            )
        )
        if doc_ids:
            stmt = stmt.where(DocChunk.doc_id.in_(doc_ids))

        chunks = self.db.scalars(stmt).all()

        results = []
        for chunk in chunks:
            if not chunk.embedding:
                continue
            similarity = embedding_service.cosine_similarity(query_vec, chunk.embedding)
            if similarity >= threshold:
                results.append({
                    "chunk": chunk,
                    "score": similarity,
                    "distance": 1 - similarity,  # for compatibility
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return {
            "results": results[:top_k],
            "query": query,
            "total_results": len(results),
        }

    def get_processing_status(self, doc_id: str) -> dict:
        """Get the current processing state of a document."""
        chunks = self.db.scalars(
            select(DocChunk).where(DocChunk.doc_id == doc_id)
        ).all()
        total = len(chunks)
        embedded = sum(1 for c in chunks if c.embedding is not None)
        status = "READY" if total > 0 and embedded == total else "IN_PROGRESS"
        return {
            "doc_id": doc_id,
            "status": status,
            "chunks_created": total,
            "chunks_embedded": embedded,
            "progress": (embedded / total * 100) if total > 0 else 0,
        }

    def cleanup_expired_chunks(self, days: int = 30) -> int:
        """Garbage collect chunks that are no longer referenced by documents."""
        from app.documents.models import Document

        deleted = self.db.execute(
            delete(DocChunk).where(
                ~DocChunk.doc_id.in_(
                    select(Document.id).where(
                        Document.organization_id == self.org_id,
                        Document.deleted_at.is_(None)
                    )
                )
            )
        ).rowcount
        self.db.commit()
        return deleted


# Legacy alias for compatibility with existing code
process_document = RagService.process_document
search_chunks = RagService.search
get_status = RagService.get_processing_status