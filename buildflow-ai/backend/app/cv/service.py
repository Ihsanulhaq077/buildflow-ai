"""Computer Vision service - PPE detection and site photo analysis."""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.cv.models import DetectionResult, SitePhoto, PPERegistration, PPEType, PPEStatus

log = logging.getLogger("buildflow.cv")


class CVService:
    """Manage computer vision operations."""

    def __init__(self, db: Session, org_id: str, user: User):
        self.db = db
        self.org_id = org_id
        self.user = user

    # --- Detection Result CRUD ---

    def create_detection_result(self, data: dict) -> DetectionResult:
        """Create a new detection result."""
        detection = DetectionResult(
            organization_id=self.org_id,
            project_id=data.get("project_id"),
            photo_id=data.get("photo_id"),
            detections=json.dumps([{
                "ppe_type": d.get("ppe_type"),
                "confidence": d.get("confidence"),
                "bbox": d.get("bbox"),
                "status": d.get("status", "UNKNOWN"),
            } for d in data.get("detection_items", [])]),
            confidence_threshold=data.get("confidence_threshold", 0.5),
        )
        self.db.add(detection)
        self.db.commit()
        return detection

    def get_detection_result(self, result_id: str) -> Optional[DetectionResult]:
        """Get detection result by ID."""
        stmt = select(DetectionResult).where(
            DetectionResult.id == result_id,
            DetectionResult.organization_id == self.org_id,
        )
        return self.db.scalar(stmt)

    def list_detection_results(
        self,
        limit: int = 50,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> List[DetectionResult]:
        """List detection results."""
        stmt = select(DetectionResult).where(
            DetectionResult.organization_id == self.org_id,
            DetectionResult.deleted_at.is_(None),
        )
        if project_id:
            stmt = stmt.where(DetectionResult.project_id == project_id)
        stmt = stmt.order_by(DetectionResult.created_at.desc()).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    # --- Site Photo CRUD ---

    def create_site_photo(self, data: dict) -> SitePhoto:
        """Create a new site photo record."""
        photo = SitePhoto(
            organization_id=self.org_id,
            project_id=data.get("project_id"),
            filename=data.get("filename"),
            storage_path=data.get("storage_path"),
            caption=data.get("caption"),
            uploaded_by=self.user.id if self.user else None,
        )
        self.db.add(photo)
        self.db.commit()
        return photo

    def get_site_photo(self, photo_id: str) -> Optional[SitePhoto]:
        """Get site photo by ID."""
        stmt = select(SitePhoto).where(
            SitePhoto.id == photo_id,
            SitePhoto.organization_id == self.org_id,
        )
        return self.db.scalar(stmt)

    def list_site_photos(
        self,
        limit: int = 50,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> List[SitePhoto]:
        """List site photos."""
        stmt = select(SitePhoto).where(
            SitePhoto.organization_id == self.org_id,
            SitePhoto.deleted_at.is_(None),
        )
        if project_id:
            stmt = stmt.where(SitePhoto.project_id == project_id)
        stmt = stmt.order_by(SitePhoto.created_at.desc()).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    # --- Photo Analysis ---

    def analyze_photo(self, photo_id: str, confidence_threshold: float = 0.5) -> dict:
        """Analyze a site photo for PPE compliance."""
        photo = self.get_site_photo(photo_id)
        if not photo:
            raise ValueError(f"Photo {photo_id} not found")

        # In a real implementation, this would call an actual CV model
        # For now, we simulate analysis
        detection_items = []
        compliant_count = 0
        non_compliant_count = 0

        # Simulate detection based on detection status
        if photo.analysis_status == "pending":
            # Mock detection results
            mock_detections = [
                {"ppe_type": "HARD_HAT", "confidence": 0.92, "bbox": [100, 50, 200, 250]},
                {"ppe_type": "SAFETY_VEST", "confidence": 0.88, "bbox": [300, 60, 450, 300]},
                {"ppe_type": "SAFETY_GOOGLES", "confidence": 0.75, "bbox": [150, 100, 250, 200]},
            ]

            for d in mock_detections:
                confidence = d["confidence"]
                if confidence >= confidence_threshold:
                    # Assume compliant if confidence high enough
                    status = "COMPLIANT"
                    compliant_count += 1
                else:
                    status = "NON_COMPLIANT"
                    non_compliant_count += 1

                detection_items.append({
                    "ppe_type": d["ppe_type"],
                    "confidence": round(confidence, 3),
                    "status": status,
                    "bbox": d["bbox"],
                })

            # Update photo analysis status
            photo.analysis_status = "completed"

            # Create detection result record
            result_data = {
                "project_id": str(photo.project_id) if photo.project_id else None,
                "photo_id": photo.id,
                "detection_items": detection_items,
                "confidence_threshold": confidence_threshold,
            }
            self.create_detection_result(result_data)

        result = {
            "detections": detection_items,
            "compliance_summary": {
                "COMPLIANT": compliant_count,
                "NON_COMPLIANT": non_compliant_count,
            },
            "overall_compliance": compliant_count > 0 and non_compliant_count == 0,
            "processed_at": datetime.utcnow(),
        }

        return result

    def get_photo_analysis(self, photo_id: str) -> Optional[dict]:
        """Get photo analysis result."""
        photo = self.get_site_photo(photo_id)
        if not photo or photo.analysis_status == "pending":
            return None

        # Return last analysis result
        # In production, we'd store analysis results explicitly
        return {
            "photo_id": photo_id,
            "analysis_status": photo.analysis_status,
        }

    # --- PPE Registration ---

    def register_ppe_for_role(self, data: dict) -> PPERegistration:
        """Register required PPE for a role."""
        registration = PPERegistration(
            organization_id=self.org_id,
            role_name=data.get("role_name", ""),
            required_ppetypes=json.dumps(data.get("required_ppetypes", [])),
        )
        self.db.add(registration)
        self.db.commit()
        return registration

    def get_ppe_registration(self, role_name: str) -> Optional[PPERegistration]:
        """Get PPE registration for a role."""
        stmt = select(PPERegistration).where(
            PPERegistration.organization_id == self.org_id,
            PPERegistration.role_name == role_name,
            PPERegistration.is_active == True,
        )
        return self.db.scalar(stmt)

    def list_ppe_registrations(self) -> List[PPERegistration]:
        """List all PPE registrations."""
        stmt = select(PPERegistration).where(
            PPERegistration.organization_id == self.org_id,
            PPERegistration.is_active == True,
        )
        return self.db.scalars(stmt).all()

    # --- Statistics ---

    def get_stats(self) -> Dict:
        """Get CV module statistics."""
        total_photos = self.db.execute(
            select(func.count(SitePhoto.id)).where(
                SitePhoto.organization_id == self.org_id,
                SitePhoto.deleted_at.is_(None),
            )
        ).scalar() or 0

        analyzed_photos = self.db.execute(
            select(func.count(SitePhoto.id)).where(
                SitePhoto.organization_id == self.org_id,
                SitePhoto.deleted_at.is_(None),
                SitePhoto.analysis_status == "completed",
            )
        ).scalar() or 0

        pending_photos = self.db.execute(
            select(func.count(SitePhoto.id)).where(
                SitePhoto.organization_id == self.org_id,
                SitePhoto.deleted_at.is_(None),
                SitePhoto.analysis_status == "pending",
            )
        ).scalar() or 0

        compliance_rate = 0.0
        if total_photos > 0:
            compliance_rate = round((analyzed_photos / total_photos) * 100, 2)

        return {
            "total_photos": total_photos,
            "analyzed_photos": analyzed_photos,
            "pending_analysis": pending_photos,
            "compliance_rate": compliance_rate,
        }