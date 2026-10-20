"""Computer Vision models for PPE detection and site photo analysis."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class PPEType(str):
    """Types of PPE."""
    HARD_HAT = "HARD_HAT"
    SAFETY_VEST = "SAFETY_VEST"
    SAFETY_GOOGLES = "SAFETY_GOOGLES"
    GLOVES = "GLOVES"
    SAFETY_BOOTS = "SAFETY_BOOTS"
    MASK = "MASK"


class PPEStatus(str):
    """PPE compliance status."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class DetectionResult(BaseMixin, Base):
    """A PPE detection result from a site photo."""
    __tablename__ = "detection_results"
    __table_args__ = (
        {"comment": "PPE detection results from site photos"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True
    )
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True
    )
    detections: Mapped[str] = mapped_column(
        Text, nullable=False  # JSON string of detection data
    )
    confidence_threshold: Mapped[float] = mapped_column(
        nullable=False, default=0.5
    )
    is_approved: Mapped[bool] = mapped_column(
        nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<DetectionResult {self.id} compliant={self.is_approved}>"


class SitePhoto(BaseMixin, Base):
    """A site photo uploaded for inspection."""
    __tablename__ = "site_photos"
    __table_args__ = (
        {"comment": "Site photos uploaded for inspection"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    caption: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    analysis_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SitePhoto {self.id} status={self.analysis_status}>"


class PPERegistration(BaseMixin, Base):
    """Required PPE for specific roles on projects."""
    __tablename__ = "ppe_registrations"
    __table_args__ = (
        {"comment": "Required PPE types per role"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    role_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    required_ppetypes: Mapped[str] = mapped_column(
        Text, nullable=False  # JSON string of required PPE types
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<PPERegistration {self.role_name}>"