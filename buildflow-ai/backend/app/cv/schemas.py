"""Pydantic schemas for Computer Vision module."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Detection Schemas ---

class PPEDetectionItem(BaseModel):
    """Single PPE detection item."""
    ppe_type: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    status: str  # COMPLIANT, NON_COMPLIANT


class DetectionResultCreate(BaseModel):
    """Create detection result request."""
    project_id: Optional[str] = None
    photo_id: Optional[str] = None
    detections: List[PPEDetectionItem]
    confidence_threshold: float = 0.5


class DetectionResultOut(BaseModel):
    """Detection result response."""
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    photo_id: Optional[UUID] = None
    detections: List[PPEDetectionItem]
    confidence_threshold: float
    is_approved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PPERegistrationCreate(BaseModel):
    """Register required PPE for a role."""
    role_name: str
    required_ppetypes: List[str]


class PPERegistrationOut(BaseModel):
    """PPE registration response."""
    id: UUID
    organization_id: UUID
    role_name: str
    required_ppetypes: List[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SitePhotoCreate(BaseModel):
    """Upload site photo request."""
    project_id: Optional[str] = None
    filename: str
    storage_path: str
    caption: Optional[str] = None


class SitePhotoOut(BaseModel):
    """Site photo response."""
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    filename: str
    storage_path: str
    caption: Optional[str] = None
    uploaded_by: UUID
    analysis_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhotoAnalysisRequest(BaseModel):
    """Request to analyze a site photo."""
    photo_id: str
    confidence_threshold: float = 0.5


class PhotoAnalysisResult(BaseModel):
    """Photo analysis result."""
    photo_id: UUID
    detections: List[PPEDetectionItem]
    compliance_summary: Dict[str, int]  # e.g., {"COMPLIANT": 3, "NON_COMPLIANT": 1}
    overall_compliance: bool
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class CVStats(BaseModel):
    """CV module statistics."""
    total_photos: int = 0
    analyzed_photos: int = 0
    pending_analysis: int = 0
    compliance_rate: float = 0.0