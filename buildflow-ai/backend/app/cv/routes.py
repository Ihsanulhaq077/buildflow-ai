"""Computer Vision API routes."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models import User

from app.cv.schemas import (
    PPEDetectionItem,
    DetectionResultCreate,
    DetectionResultOut,
    PPERegistrationCreate,
    PPERegistrationOut,
    SitePhotoCreate,
    SitePhotoOut,
    PhotoAnalysisRequest,
    PhotoAnalysisResult,
    CVStats,
)
from app.cv.service import CVService

router = APIRouter(prefix="/cv", tags=["cv"])

READ = require_permission("cv.read")
MANAGE = require_permission("cv.manage")


def get_cv_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CVService:
    """Get CV service with current user and organization."""
    org_id = str(current_user.organization_id) if hasattr(current_user, 'organization_id') else "00000000-0000-0000-0000-000000000000"
    return CVService(db, org_id, current_user)


# --- Detection Result Routes ---

@router.post("/detections", response_model=DetectionResultOut, status_code=status.HTTP_201_CREATED)
def create_detection_result(
    data: DetectionResultCreate,
    _: bool = Depends(MANAGE),
    service: CVService = Depends(get_cv_service),
):
    """Create a detection result."""
    # Convert Pydantic model to dict for service
    service_data = {
        "project_id": data.project_id,
        "photo_id": data.photo_id,
        "detection_items": [d.dict() for d in data.detections],
        "confidence_threshold": data.confidence_threshold,
    }
    result = service.create_detection_result(service_data)
    return DetectionResultOut.from_orm(result)


@router.get("/detections/{result_id}", response_model=DetectionResultOut)
def get_detection_result(
    result_id: UUID,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """Get a detection result by ID."""
    result = service.get_detection_result(str(result_id))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection result {result_id} not found",
        )
    return DetectionResultOut.from_orm(result)


@router.get("/detections", response_model=List[DetectionResultOut])
def list_detection_results(
    limit: int = 50,
    offset: int = 0,
    project_id: Optional[str] = None,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """List detection results."""
    results = service.list_detection_results(limit, offset, project_id)
    return [DetectionResultOut.from_orm(r) for r in results]


# --- Site Photo Routes ---

@router.post("/photos", response_model=SitePhotoOut, status_code=status.HTTP_201_CREATED)
def create_site_photo(
    data: SitePhotoCreate,
    _: bool = Depends(MANAGE),
    service: CVService = Depends(get_cv_service),
):
    """Upload a site photo."""
    service_data = {
        "project_id": data.project_id,
        "filename": data.filename,
        "storage_path": data.storage_path,
        "caption": data.caption,
    }
    photo = service.create_site_photo(service_data)
    return SitePhotoOut.from_orm(photo)


@router.get("/photos/{photo_id}", response_model=SitePhotoOut)
def get_site_photo(
    photo_id: UUID,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """Get a site photo by ID."""
    photo = service.get_site_photo(str(photo_id))
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site photo {photo_id} not found",
        )
    return SitePhotoOut.from_orm(photo)


@router.get("/photos", response_model=List[SitePhotoOut])
def list_site_photos(
    limit: int = 50,
    offset: int = 0,
    project_id: Optional[str] = None,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """List site photos."""
    photos = service.list_site_photos(limit, offset, project_id)
    return [SitePhotoOut.from_orm(p) for p in photos]


# --- Photo Analysis Route ---

@router.post("/photos/{photo_id}/analyze", response_model=PhotoAnalysisResult)
def analyze_photo(
    photo_id: UUID,
    data: PhotoAnalysisRequest,
    _: bool = Depends(MANAGE),
    service: CVService = Depends(get_cv_service),
):
    """Analyze a site photo for PPE compliance."""
    # Override photo_id from path
    data.photo_id = str(photo_id)
    result = service.analyze_photo(data.photo_id, data.confidence_threshold)
    return PhotoAnalysisResult(**result)


@router.get("/photos/{photo_id}/analysis")
def get_photo_analysis(
    photo_id: UUID,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """Get photo analysis result."""
    result = service.get_photo_analysis(str(photo_id))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for photo {photo_id}",
        )
    return result


# --- PPE Registration Routes ---

@router.post("/ppe-registrations", response_model=PPERegistrationOut, status_code=status.HTTP_201_CREATED)
def register_ppe(
    data: PPERegistrationCreate,
    _: bool = Depends(MANAGE),
    service: CVService = Depends(get_cv_service),
):
    """Register required PPE for a role."""
    service_data = {
        "role_name": data.role_name,
        "required_ppetypes": data.required_ppetypes,
    }
    registration = service.register_ppe_for_role(service_data)
    return PPERegistrationOut.from_orm(registration)


@router.get("/ppe-registrations/{role_name}", response_model=PPERegistrationOut)
def get_ppe_registration(
    role_name: str,
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """Get PPE registration for a role."""
    registration = service.get_ppe_registration(role_name)
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PPE registration for role '{role_name}' not found",
        )
    return PPERegistrationOut.from_orm(registration)


@router.get("/ppe-registrations", response_model=List[PPERegistrationOut])
def list_ppe_registrations(
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """List all PPE registrations."""
    registrations = service.list_ppe_registrations()
    return [PPERegistrationOut.from_orm(r) for r in registrations]


# --- Statistics Route ---

@router.get("/stats", response_model=CVStats)
def get_stats(
    _: bool = Depends(READ),
    service: CVService = Depends(get_cv_service),
):
    """Get CV module statistics."""
    stats = service.get_stats()
    return CVStats(**stats)