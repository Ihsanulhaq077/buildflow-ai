"""
Document storage service.

Handles file upload, versioning, and MinIO/S3-compatible storage operations.
"""
import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.documents.models import DocAccessPolicy, Document, DocVersion

log = logging.getLogger("buildflow.documents")


class DocumentService:
    """Manage document uploads, downloads, and versioning."""

    def __init__(self, db: Session, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id
        self._minio_endpoint = os.getenv("MINIO_ENDPOINT")
        self._minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self._minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self._minio_bucket = os.getenv("MINIO_BUCKET", "documents")

    # --- MinIO integration ---

    def _minio_enabled(self) -> bool:
        return bool(self._minio_endpoint and self._minio_access_key and self._minio_secret_key)

    def _minio_presigned_url(self, key: str, method: str = "GET") -> str:
        """Generate a presigned URL for MinIO storage (not implemented yet)."""
        return ""

    # --- Local storage (dev mode) ---

    def _get_local_path(self, key: str) -> str:
        local_dir = os.getenv("LOCAL_STORAGE_DIR", "/tmp/buildflow-documents")
        os.makedirs(local_dir, exist_ok=True)
        return os.path.join(local_dir, key)

    def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        file_type: str,
        mime_type: str = "application/octet-stream",
        description: str = "",
        project_id: Optional[uuid.UUID] = None,
        tags: Optional[list[str]] = None,
    ) -> "Document":
        """Upload a file to storage and create a Document record."""
        # Generate deterministic storage key
        file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
        ext = os.path.splitext(file_name)[1].lower().lstrip(".")
        key = f"{self.org_id}/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}_{file_hash}.{ext}"

        if self._minio_enabled():
            path = key  # MinIO key
            blob_key = key
            storage_path = f"{self._minio_endpoint}/bucket/{key}"
        else:
            path = self._get_local_path(key)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(file_bytes)
            blob_key = None
            storage_path = path

        # Versioning: check if same content already exists
        existing = self.db.scalar(
            Document.query.filter_by(
                organization_id=self.org_id,
                file_name=file_name,
                blob_key=blob_key,
                is_active=True,
            ).order_by(Document.version.desc()).first()
        )
        version = (existing.version + 1) if existing else 1

        doc = Document(
            organization_id=self.org_id,
            project_id=project_id,
            name=file_name,
            description=description,
            file_name=file_name,
            file_type=file_type.upper(),
            file_size=len(file_bytes),
            mime_type=mime_type,
            storage_path=path,
            blob_key=blob_key,
            version=version,
            tags=";".join(tags) or "",
            status="UPLOADED",
        )
        self.db.add(doc)
        self.db.flush()

        # Update file name on blob
        if blob_key:
            self._update_file_name(blob_key, file_name)

        # Create initial version record
        version_record = DocVersion(
            document_id=doc.id,
            version=version,
            file_name=file_name,
            file_size=len(file_bytes),
            storage_path=path,
            etag=file_hash,
        )
        self.db.add(version_record)

        self.db.commit()
        return doc

    def _update_file_name(self, blob_key: str, new_name: str):
        """Update the file name on the blob storage."""
        # MinIO rename via S3 API (not implemented)
        pass

    def delete_document(self, doc_id: uuid.UUID, user_id: uuid.UUID):
        """Soft-delete a document."""
        doc = self.db.get(Document, doc_id)
        if doc:
            doc.deleted_at = datetime.utcnow()
            self.db.commit()

    def get_document(self, doc_id: uuid.UUID) -> Optional["Document"]:
        """Get a document by ID."""
        return self.db.get(Document, doc_id)

    def list_documents(self, limit: int = 100, offset: int = 0) -> list["Document"]:
        """List documents for the organization."""
        return (
            self.db.query(Document)
            .filter(Document.organization_id == self.org_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_access_policy(self, doc_id: uuid.UUID, user_id: uuid.UUID) -> Optional["DocAccessPolicy"]:
        """Get access policy for a user on a document."""
        return DocAccessPolicy.query.filter_by(document_id=doc_id, user_id=user_id).first()

    def grant_access(
        self,
        doc_id: uuid.UUID,
        user_id: uuid.UUID,
        can_read: bool = True,
        can_write: bool = False,
        granted_by: uuid.UUID = None,
        expires_at: datetime = None,
    ) -> DocAccessPolicy:
        """Grant document access to a user."""
        policy = DocAccessPolicy(
            document_id=doc_id,
            user_id=user_id,
            can_read=can_read,
            can_write=can_write,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        self.db.add(policy)
        self.db.commit()
        return policy


# Legacy alias
document_service = DocumentService