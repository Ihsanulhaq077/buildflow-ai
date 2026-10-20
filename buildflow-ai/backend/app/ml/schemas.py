"""Pydantic schemas for ML forecasting."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Request Schemas ---

class CostOverrunForecastRequest(BaseModel):
    """Request for cost overrun prediction."""
    project_id: str
    forecast_days: int = 30
    include_revisions: bool = True


class DelayForecastRequest(BaseModel):
    """Request for project delay prediction."""
    project_id: str
    forecast_days: int = 30
    include_dependencies: bool = True


class MaterialForecastRequest(BaseModel):
    """Request for material forecasting."""
    project_id: str
    material_type: str  # e.g., "cement", "steel", "sand"
    forecast_days: int = 30


class BatchForecastRequest(BaseModel):
    """Request for batch forecasting across multiple items."""
    project_id: str
    forecast_types: List[str]  # ["COST_OVERRUN", "DELAY", "MATERIAL"]
    forecast_days: int = 30


# --- Response Schemas ---

class ForecastOut(BaseModel):
    """Forecast response."""
    id: UUID
    organization_id: UUID
    forecast_type: str
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    status: str
    predicted_value: Optional[float] = None
    confidence: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    metadata: Dict = {}
    model_version: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelMetadataOut(BaseModel):
    """Model metadata response."""
    id: UUID
    organization_id: UUID
    model_name: str
    version: str
    model_type: str
    features: Dict = {}
    trained_at: Optional[datetime] = None
    accuracy: Optional[float] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ForecastResult(BaseModel):
    """Complete forecast result with details."""
    forecast: ForecastOut
    insights: List[str] = []
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL


class BatchForecastResult(BaseModel):
    """Batch forecast results."""
    project_id: str
    results: List[ForecastResult] = []
    summary: Dict = {}


class MLStats(BaseModel):
    """ML module statistics."""
    total_forecasts: int = 0
    active_models: int = 0
    last_prediction: Optional[datetime] = None
    avg_confidence: Optional[float] = None