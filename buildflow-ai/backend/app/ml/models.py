"""ML forecasting models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class ForecastType(str):
    """Type of forecast."""
    COST_OVERRUN = "COST_OVERRUN"
    DELAY = "DELAY"
    MATERIAL = "MATERIAL"


class ForecastStatus(str):
    """Status of a forecast."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Forecast(BaseMixin, Base):
    """A single forecast/prediction result."""
    __tablename__ = "forecasts"
    __table_args__ = (
        {"comment": "ML forecast results"},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), index=True, nullable=False
    )
    forecast_type: Mapped[str] = mapped_column(String(20), nullable=False)  # COST_OVERRUN, DELAY, MATERIAL
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # project_id, etc.
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "project", "boq", etc.
    status: Mapped[str] = mapped_column(String(20), default=ForecastStatus.PENDING)
    predicted_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-1
    lower_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forecast_metadata: Mapped[dict] = mapped_column(Text, default="{}")  # JSON string for compatibility
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Forecast {self.forecast_type} status={self.status}>"


class ModelMetadata(BaseMixin, Base):
    """Metadata for ML models used in forecasting."""
    __tablename__ = "model_metadata"
    __table_args__ = (
        {"comment": "ML model versions and metadata"},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), index=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)  # regression, classification, etc.
    features: Mapped[dict] = mapped_column(Text, default="{}")  # JSON string
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<ModelMetadata {self.model_name} v{self.version}>"