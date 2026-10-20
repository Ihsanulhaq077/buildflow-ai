"""
Document models for storage, versioning, and access permissions.

Models:
- Document: the document entity (references stored file from documents module)
- DocVersion: immutable version of a document's text content
- DocAccess: document-level access permissions for individual users
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class DocAccess(str, Enum):
    """Access level for document sharing."""
    READ = "READ"
    WRITE = "WRITE"


class DocFileType(str, Enum):
    """Supported document file types."""
    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"
    TXT = "TXT"
    MD = "MD"
    CSV = "CSV"
    JSON = "JSON"


class Document(BaseMixin, Base):
    """
    A document stored in the system.

    References the blob path in MinIO/MinIO-compatible storage.
    Supports versioning, access control, and status tracking.
    """
    __tablename__ = "documents"
    __table_args__ = ({"comment": "Documents managed in the RAG/documents system"},)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    storage_path: Mapped[str] = mapped_column(String(500))
    blob_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(
        String(30), default="UPLOADED",
        comment="UPLOADED, PROCESSING, READY, FAILED"
    )
    tags: Mapped[list[str]] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Document {self.name} ({self.file_type}, v{self.version})>"


class DocVersion(BaseMixin, Base):
    """
    Immutable version of a document's text content.

    Each time a document is updated, a new version is created.
    """
    __tablename__ = "doc_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(500))
    etag: Mapped[str] = mapped_column(String(128), default="")
    text: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<DocVersion doc={self.document_id} v{self.version}>"


class DocAccessPolicy(BaseMixin, Base):
    """
    Document-level access policy for individual users.
    Grants read/write access beyond the default RBAC permissions.
    """
    __tablename__ = "doc_access_policies"
    __table_args__ = ({"comment": "Per-user document access overrides"},)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DocAccessPolicy doc={self.document_id} user={self.user_id}>"