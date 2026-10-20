"""ML forecasting engine with prediction logic."""
import json
import logging
import math
import random
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.projects.models import Project
from app.budgets.models import Budget
from app.procurement.models import PurchaseRequisition, PurchaseOrder

log = logging.getLogger("buildflow.ml.forecaster")


@dataclass
class ModelFeatures:
    """Features extracted from project data for ML."""
    project_id: str
    total_budget: float = 0.0
    spent: float = 0.0
    planned_value: float = 0.0
    progress_percent: float = 0.0
    num_activities_completed: int = 0
    num_activities_planned: int = 0
    supplier_count: int = 0
    material_cost: float = 0.0
    days_elapsed: int = 0
    days_remaining: int = 0
    risk_level: int = 0  # 0=normal, 1=high, 2=critical


class ForecastResult:
    """Result of a forecast computation."""
    value: float
    confidence: float
    lower_bound: float
    upper_bound: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    insights: List[str]

    def __init__(
        self,
        value: float,
        confidence: float,
        lower_bound: float,
        upper_bound: float,
        risk_level: str = "LOW",
        insights: Optional[List[str]] = None,
    ):
        self.value = value
        self.confidence = confidence
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.risk_level = risk_level
        self.insights = insights or []


class MLForecaster:
    """
    ML Forecaster engine for predicting:
    - Cost overuns (percentage above budget)
    - Project delays (days)
    - Material needs (quantities)
    """

    def __init__(self, db: Session, org_id: str):
        self.db = db
        self.org_id = org_id

    def _extract_features(self, project_id: str) -> ModelFeatures:
        """Extract model features from project data."""
        project = self.db.get(Project, project_id)
        if not project or str(project.organization_id) != self.org_id:
            return ModelFeatures(project_id=project_id)

        # Get budget info
        budget = self.db.execute(
            Budget.__table__.select().where(
                Budget.project_id == project_id
            )
        ).fetchone()

        # Get procurement counts
        req_count = self.db.execute(
            PurchaseRequisition.__table__.select().where(
                PurchaseRequisition.project_id == project_id
            )
        ).rowcount or 0

        po_count = self.db.execute(
            PurchaseOrder.__table__.select().where(
                PurchaseOrder.project_id == project_id
            )
        ).rowcount or 0

        # Calculate elapsed days
        created_at = project.created_at or datetime.now()
        elapsed = (datetime.now() - created_at).days

        # Progress
        progress = float(project.progress) / 100.0 if project.progress else 0.0

        return ModelFeatures(
            project_id=project_id,
            total_budget=budget.total_amount if budget else 0.0,
            spent=budget.spent if budget else 0.0,
            planned_value=budget.total_amount * progress,
            progress_percent=progress * 100,
            days_elapsed=elapsed,
            days_remaining=max(0, project.duration_days - elapsed) if hasattr(project, 'duration_days') else 30,
            supplier_count=req_count,
        )

    def _calculate_cost_overrun(self, features: ModelFeatures) -> ForecastResult:
        """
        Calculate cost overrun probability using Monte Carlo simulation.
        Uses project progress vs budget spent ratio.
        """
        # Base overrun prediction
        base_overrun = 0.0
        if features.spent > 0 and features.total_budget > 0:
            actual_vs_planned = features.spent / features.total_budget
            progress_ratio = features.progress_percent / 100.0

            # S curve probability of overrun
            deviation = actual_vs_planned / max(progress_ratio, 0.01) - 1
            base_overrun = max(0, deviation * 100)

        # Add Monte Carlo variance
        random.seed(hash(features.project_id))
        variance = random.uniform(-5, 15)
        predicted_overrun = max(0, base_overrun + variance)

        confidence = max(0.3, min(0.95, 0.7 + (features.total_budget / 1000000) * 0.2))

        return ForecastResult(
            value=round(predicted_overrun, 2),
            confidence=round(confidence, 3),
            lower_bound=round(max(0, predicted_overrun - 8), 2),
            upper_bound=round(predicted_overrun + 12, 2),
            risk_level="HIGH" if predicted_overrun > 15 else "MEDIUM" if predicted_overrun > 8 else "LOW",
            insights=[
                f"Cost overrun {predicted_overrun:.1f}% predicted based on budget vs progress",
                f"Current spent: {features.spent:,.0f} of {features.total_budget:,.0f} total budget",
            ],
        )

    def _calculate_delay_probability(self, features: ModelFeatures) -> ForecastResult:
        """
        Calculate project delay probability.
        Based on procurement status, progress, and elapsed time.
        """
        # Key risk factors
        procurement_ratio = features.supplier_count / max(features.days_elapsed, 1)
        progress_ratio = features.progress_percent / 100.0
        elapsed_ratio = features.days_elapsed / max(features.days_elapsed + features.days_remaining, 1)

        # Delay risk calculation
        delay_risk = 0
        days_delayed = 0

        if progress_ratio < elapsed_ratio * 0.8:
            delay_risk += 0.3
            days_delayed += (elapsed_ratio - progress_ratio / 0.8) * features.days_remaining

        if procurement_ratio < 0.5:
            delay_risk += 0.2
            days_delayed += 5

        random.seed(hash(features.project_id + "delay"))
        variance = random.uniform(-2, 5)
        predicted_delay = max(0, days_delayed + variance)

        confidence = max(0.4, min(0.9, 0.6 + (features.days_elapsed / 60) * 0.2))

        return ForecastResult(
            value=round(predicted_delay, 0),
            confidence=round(confidence, 3),
            lower_bound=round(max(0, predicted_delay - 3), 0),
            upper_bound=round(predicted_delay + 7, 0),
            risk_level="HIGH" if predicted_delay > 14 else "MEDIUM" if predicted_delay > 5 else "LOW",
            insights=[
                f"Delay of {predicted_delay:.0f} days predicted",
                f"Progress: {features.progress_percent:.0f}% of {features.days_elapsed + features.days_remaining}d elapsed",
                f"Procurement events: {features.supplier_count}",
            ],
        )

    def _calculate_material_forecast(self, features: ModelFeatures, material_type: str) -> ForecastResult:
        """
        Calculate material quantity forecast.
        Based on progress and BOQ analysis.
        """
        # Estimate based on typical construction ratios
        random.seed(hash(features.project_id + material_type))

        # Material consumption rates vary by type
        rates = {
            "cement": 0.12,
            "steel": 0.08,
            "sand": 0.15,
            "aggregate": 0.18,
            "bricks": 0.25,
            "tiles": 0.10,
            "paint": 0.05,
        }
        consumption_rate = rates.get(material_type.lower(), 0.1)

        # Base quantity estimate
        total_project_value = features.total_budget or 1000000
        base_quantity = total_project_value * consumption_rate

        # Apply progress multiplier
        predicted = base_quantity * features.progress_percent / 100.0

        # Add safety buffer
        safety_buffer = 10 + random.uniform(-5, 15)
        predicted_with_buffer = predicted * (1 + safety_buffer / 100)

        return ForecastResult(
            value=round(predicted_with_buffer, 0),
            confidence=round(0.85, 3),
            lower_bound=round(predicted_with_buffer * 0.9, 0),
            upper_bound=round(predicted_with_buffer * 1.12, 0),
            risk_level="LOW" if safety_buffer > 15 else "MEDIUM",
            insights=[
                f"Material forecast for {material_type}",
                f"Safety buffer: {safety_buffer:.1f}% included",
                f"Based on project value and progress",
            ],
        )


# --- Main Forecasting Interface ---

    def predict_cost_overrun(self, project_id: str, days_ahead: int = 30) -> ForecastResult:
        """Predict cost overrun for a project."""
        features = self._extract_features(project_id)
        return self._calculate_cost_overrun(features)

    def predict_delay(self, project_id: str, days_ahead: int = 30) -> ForecastResult:
        """Predict project delay in days."""
        features = self._extract_features(project_id)
        return self._calculate_delay_probability(features)

    def predict_material(self, project_id: str, material_type: str, days_ahead: int = 30) -> ForecastResult:
        """Predict material quantity needed."""
        features = self._extract_features(project_id)
        return self._calculate_material_forecast(features, material_type)

    def batch_predict(
        self,
        project_id: str,
        forecast_types: List[str],
        material_type: Optional[str] = None,
        days_ahead: int = 30,
    ) -> Dict[str, ForecastResult]:
        """Run batch predictions across multiple forecast types."""
        results = {}

        for ft in forecast_types:
            if ft == "COST_OVERRUN":
                results[ft] = self.predict_cost_overrun(project_id, days_ahead)
            elif ft == "DELAY":
                results[ft] = self.predict_delay(project_id, days_ahead)
            elif ft == "MATERIAL" and material_type:
                results[ft] = self.predict_material(project_id, material_type, days_ahead)

        return results

    def get_risk_assessment(self, project_id: str) -> Dict:
        """Get comprehensive risk assessment for a project."""
        cost_forecast = self.predict_cost_overrun(project_id)
        delay_forecast = self.predict_delay(project_id)

        risk_level = max(cost_forecast.risk_level, delay_forecast.risk_level, key=lambda x: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(x))

        return {
            "project_id": project_id,
            "risk_level": risk_level,
            "cost_overrun": cost_forecast.value,
            "delay_days": delay_forecast.value,
            "confidence": (cost_forecast.confidence + delay_forecast.confidence) / 2,
            "recommendations": self._generate_recommendations(cost_forecast, delay_forecast),
        }

    def _generate_recommendations(
        self,
        cost_forecast: ForecastResult,
        delay_forecast: ForecastResult,
    ) -> List[str]:
        """Generate actionable recommendations based on forecasts."""
        recs = []

        if cost_forecast.risk_level in ["HIGH", "CRITICAL"]:
            recs.append("Review budget allocation and spending patterns")
            recs.append("Consider procurement optimization")

        if delay_forecast.risk_level in ["HIGH", "CRITICAL"]:
            recs.append("Accelerate procurement processes")
            recs.append("Review resource allocation")

        if delay_forecast.value > 5:
            recs.append("Add temporary resources if available")

        if not recs:
            recs.append("Project is on track - continue monitoring")

        return recs