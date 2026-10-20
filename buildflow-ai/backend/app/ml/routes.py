"""ML forecasting API routes."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models import User

from app.ml.schemas import (
    CostOverrunForecastRequest,
    DelayForecastRequest,
    MaterialForecastRequest,
    BatchForecastRequest,
    ForecastOut,
    ModelMetadataOut,
    ForecastResult,
    BatchForecastResult,
    MLStats,
)
from app.ml.service import MLService
from app.ml.forecaster import MLForecaster

router = APIRouter(prefix="/ml", tags=["ml"])

READ = require_permission("ml.read")
MANAGE = require_permission("ml.manage")


def get_ml_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MLService:
    """Get ML service with current user and organization."""
    org_id = str(current_user.organization_id) if hasattr(current_user, 'organization_id') else "00000000-0000-0000-0000-000000000000"
    return MLService(db, org_id, current_user)


def get_ml_forecaster(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MLForecaster:
    """Get ML forecaster instance."""
    org_id = str(current_user.organization_id) if hasattr(current_user, 'organization_id') else "00000000-0000-0000-0000-000000000000"
    return MLForecaster(db, org_id)


# --- Forecast Endpoints ---

@router.post("/cost-overrun", response_model=ForecastResult, status_code=status.HTTP_201_CREATED)
def predict_cost_overrun(
    request: CostOverrunForecastRequest,
    _: bool = Depends(MANAGE),
    forecaster: MLForecaster = Depends(get_ml_forecaster),
    ml_service: MLService = Depends(get_ml_service),
):
    """Predict cost overrun for a project."""
    # Create forecast record
    forecast = ml_service.create_forecast({
        "forecast_type": "COST_OVERRUN",
        "target_id": request.project_id,
        "target_type": "project",
    })

    # Run prediction
    result = forecaster.predict_cost_overrun(request.project_id, request.forecast_days)

    # Update forecast with results
    ml_service.update_forecast(str(forecast.id), {
        "status": "COMPLETED",
        "predicted_value": result.value,
        "confidence": result.confidence,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "metadata": {"insights": result.insights, "risk_level": result.risk_level},
    })

    return ForecastResult(
        forecast=forecast,
        insights=result.insights,
        risk_level=result.risk_level,
    )


@router.post("/delay", response_model=ForecastResult, status_code=status.HTTP_201_CREATED)
def predict_delay(
    request: DelayForecastRequest,
    _: bool = Depends(MANAGE),
    forecaster: MLForecaster = Depends(get_ml_forecaster),
    ml_service: MLService = Depends(get_ml_service),
):
    """Predict project delay."""
    forecast = ml_service.create_forecast({
        "forecast_type": "DELAY",
        "target_id": request.project_id,
        "target_type": "project",
    })

    result = forecaster.predict_delay(request.project_id, request.forecast_days)

    ml_service.update_forecast(str(forecast.id), {
        "status": "COMPLETED",
        "predicted_value": result.value,
        "confidence": result.confidence,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "metadata": {"insights": result.insights, "risk_level": result.risk_level},
    })

    return ForecastResult(
        forecast=forecast,
        insights=result.insights,
        risk_level=result.risk_level,
    )


@router.post("/material", response_model=ForecastResult, status_code=status.HTTP_201_CREATED)
def predict_material(
    request: MaterialForecastRequest,
    _: bool = Depends(MANAGE),
    forecaster: MLForecaster = Depends(get_ml_forecaster),
    ml_service: MLService = Depends(get_ml_service),
):
    """Predict material needs for a project."""
    forecast = ml_service.create_forecast({
        "forecast_type": "MATERIAL",
        "target_id": request.project_id,
        "target_type": "project",
    })

    result = forecaster.predict_material(request.project_id, request.material_type, request.forecast_days)

    ml_service.update_forecast(str(forecast.id), {
        "status": "COMPLETED",
        "predicted_value": result.value,
        "confidence": result.confidence,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "metadata": {"insights": result.insights, "risk_level": result.risk_level, "material_type": request.material_type},
    })

    return ForecastResult(
        forecast=forecast,
        insights=result.insights,
        risk_level=result.risk_level,
    )


@router.post("/batch", response_model=BatchForecastResult, status_code=status.HTTP_201_CREATED)
def batch_predict(
    request: BatchForecastRequest,
    _: bool = Depends(MANAGE),
    forecaster: MLForecaster = Depends(get_ml_forecaster),
    ml_service: MLService = Depends(get_ml_service),
):
    """Run batch predictions across multiple forecast types."""
    material_type = None
    if "MATERIAL" in request.forecast_types:
        # For now, default to cement for batch material forecast
        material_type = "cement"

    results = forecaster.batch_predict(
        request.project_id,
        request.forecast_types,
        material_type,
        request.forecast_days,
    )

    forecast_results = []
    for ft, result in results.items():
        forecast = ml_service.create_forecast({
            "forecast_type": ft,
            "target_id": request.project_id,
            "target_type": "project",
        })
        ml_service.update_forecast(str(forecast.id), {
            "status": "COMPLETED",
            "predicted_value": result.value,
            "confidence": result.confidence,
            "lower_bound": result.lower_bound,
            "upper_bound": result.upper_bound,
            "metadata": {"insights": result.insights, "risk_level": result.risk_level},
        })
        forecast_results.append(ForecastResult(
            forecast=forecast,
            insights=result.insights,
            risk_level=result.risk_level,
        ))

    # Generate summary
    summary = {
        "total_forecasts": len(forecast_results),
        "high_risk_count": sum(1 for r in forecast_results if r.risk_level in ["HIGH", "CRITICAL"]),
        "avg_confidence": sum(r.confidence for r in forecast_results) / len(forecast_results) if forecast_results else 0,
    }

    return BatchForecastResult(
        project_id=request.project_id,
        results=forecast_results,
        summary=summary,
    )


@router.get("/risk/{project_id}", response_model=dict)
def get_risk_assessment(
    project_id: str,
    _: bool = Depends(READ),
    forecaster: MLForecaster = Depends(get_ml_forecaster),
):
    """Get comprehensive risk assessment for a project."""
    assessment = forecaster.get_risk_assessment(project_id)
    return assessment


# --- Forecast History ---

@router.get("/forecasts", response_model=List[ForecastOut])
def list_forecasts(
    limit: int = 50,
    offset: int = 0,
    forecast_type: Optional[str] = None,
    status: Optional[str] = None,
    _: bool = Depends(READ),
    ml_service: MLService = Depends(get_ml_service),
):
    """List forecast history."""
    return ml_service.list_forecasts(limit, offset, forecast_type, status)


@router.get("/forecasts/{forecast_id}", response_model=ForecastOut)
def get_forecast(
    forecast_id: UUID,
    _: bool = Depends(READ),
    ml_service: MLService = Depends(get_ml_service),
):
    """Get a specific forecast by ID."""
    forecast = ml_service.get_forecast(str(forecast_id))
    if not forecast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast {forecast_id} not found",
        )
    return forecast


# --- Model Management ---

@router.post("/models", response_model=ModelMetadataOut, status_code=status.HTTP_201_CREATED)
def register_model(
    model_name: str,
    version: str,
    model_type: str,
    features: dict,
    accuracy: Optional[float] = None,
    _: bool = Depends(MANAGE),
    ml_service: MLService = Depends(get_ml_service),
):
    """Register an ML model."""
    return ml_service.register_model({
        "model_name": model_name,
        "version": version,
        "model_type": model_type,
        "features": features,
        "accuracy": accuracy,
    })


@router.get("/models", response_model=List[ModelMetadataOut])
def list_models(
    _: bool = Depends(READ),
    ml_service: MLService = Depends(get_ml_service),
):
    """List registered ML models."""
    return ml_service.list_models()


@router.post("/models/{model_name}/{version}/activate", response_model=ModelMetadataOut)
def activate_model(
    model_name: str,
    version: str,
    _: bool = Depends(MANAGE),
    ml_service: MLService = Depends(get_ml_service),
):
    """Activate a model version."""
    model = ml_service.activate_model(model_name, version)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_name} v{version} not found",
        )
    return model


# --- Statistics ---

@router.get("/stats", response_model=MLStats)
def get_stats(
    _: bool = Depends(READ),
    ml_service: MLService = Depends(get_ml_service),
):
    """Get ML module statistics."""
    stats = ml_service.get_stats()
    return MLStats(**stats)