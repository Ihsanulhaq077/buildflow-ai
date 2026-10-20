"""ML forecasting service."""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.ml.models import Forecast, ForecastStatus, ModelMetadata, ForecastType

log = logging.getLogger("buildflow.ml")


class MLService:
    """Manage ML forecasting operations."""

    def __init__(self, db: Session, org_id: str, user: User):
        self.db = db
        self.org_id = org_id
        self.user = user

    # --- Forecast CRUD ---

    def create_forecast(self, data: dict) -> Forecast:
        """Create a new forecast record."""
        forecast = Forecast(
            organization_id=self.org_id,
            forecast_type=data.get("forecast_type", "COST_OVERRUN"),
            target_id=data.get("target_id"),
            target_type=data.get("target_type"),
            status=ForecastStatus.PENDING,
            forecast_metadata=data.get("metadata", {}),
            model_version=data.get("model_version"),
        )
        self.db.add(forecast)
        self.db.commit()
        return forecast

    def get_forecast(self, forecast_id: str) -> Optional[Forecast]:
        """Get a forecast by ID."""
        stmt = select(Forecast).where(
            Forecast.id == forecast_id,
            Forecast.organization_id == self.org_id,
        )
        return self.db.scalar(stmt)

    def list_forecasts(
        self,
        limit: int = 50,
        offset: int = 0,
        forecast_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Forecast]:
        """List forecasts for the organization."""
        stmt = select(Forecast).where(
            Forecast.organization_id == self.org_id,
            Forecast.deleted_at.is_(None),
        )
        if forecast_type:
            stmt = stmt.where(Forecast.forecast_type == forecast_type)
        if status:
            stmt = stmt.where(Forecast.status == status)
        stmt = stmt.order_by(Forecast.created_at.desc()).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    def update_forecast(self, forecast_id: str, data: dict) -> Optional[Forecast]:
        """Update a forecast."""
        forecast = self.get_forecast(forecast_id)
        if not forecast:
            return None
        for key, value in data.items():
            if hasattr(forecast, key):
                setattr(forecast, key, value)
        self.db.commit()
        return forecast

    def soft_delete_forecast(self, forecast_id: str) -> bool:
        """Soft-delete a forecast."""
        forecast = self.get_forecast(forecast_id)
        if forecast:
            forecast.deleted_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    # --- Model Metadata ---

    def register_model(self, data: dict) -> ModelMetadata:
        """Register an ML model."""
        model = ModelMetadata(
            organization_id=self.org_id,
            model_name=data.get("model_name", "ml_model"),
            version=data.get("version", "1.0.0"),
            model_type=data.get("model_type", "regression"),
            features=data.get("features", {}),
            trained_at=data.get("trained_at"),
            accuracy=data.get("accuracy"),
            is_active=data.get("is_active", True),
        )
        self.db.add(model)
        self.db.commit()
        return model

    def get_model(self, model_name: str, version: Optional[str] = None) -> Optional[ModelMetadata]:
        """Get a model by name and version."""
        stmt = select(ModelMetadata).where(
            ModelMetadata.organization_id == self.org_id,
            ModelMetadata.model_name == model_name,
            ModelMetadata.is_active == True,
        )
        if version:
            stmt = stmt.where(ModelMetadata.version == version)
        return self.db.scalar(stmt)

    def list_models(self) -> List[ModelMetadata]:
        """List all registered models."""
        stmt = select(ModelMetadata).where(
            ModelMetadata.organization_id == self.org_id,
            ModelMetadata.is_active == True,
        )
        return self.db.scalars(stmt).all()

    def activate_model(self, model_name: str, version: str) -> Optional[ModelMetadata]:
        """Activate a model and deactivate others of the same name."""
        model = self.get_model(model_name, version)
        if model:
            # Deactivate other versions of the same model
            stmt = select(ModelMetadata).where(
                ModelMetadata.organization_id == self.org_id,
                ModelMetadata.model_name == model_name,
                ModelMetadata.version != version,
            )
            self.db.execute(stmt.update({"is_active": False}))
            self.db.commit()
        return model

    # --- Statistics ---

    def get_stats(self) -> Dict:
        """Get ML module statistics."""
        total_forecasts = self.db.execute(
            select(func.count(Forecast.id)).where(
                Forecast.organization_id == self.org_id,
                Forecast.deleted_at.is_(None)
            )
        ).scalar() or 0

        active_models = self.db.execute(
            select(func.count(ModelMetadata.id)).where(
                ModelMetadata.organization_id == self.org_id,
                ModelMetadata.is_active == True
            )
        ).scalar() or 0

        last_prediction = self.db.execute(
            select(Forecast.created_at).where(
                Forecast.organization_id == self.org_id,
                Forecast.deleted_at.is_(None),
                Forecast.status == ForecastStatus.COMPLETED
            ).order_by(Forecast.created_at.desc()).limit(1)
        ).scalar()

        avg_confidence = self.db.execute(
            select(func.avg(Forecast.confidence)).where(
                Forecast.organization_id == self.org_id,
                Forecast.deleted_at.is_(None),
                Forecast.status == ForecastStatus.COMPLETED
            )
        ).scalar()

        return {
            "total_forecasts": total_forecasts,
            "active_models": active_models,
            "last_prediction": last_prediction,
            "avg_confidence": avg_confidence,
        }