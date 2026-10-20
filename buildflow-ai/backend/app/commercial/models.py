"""Commercial models for subscriptions, onboarding, and monitoring."""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class SubscriptionTier(str):
    """Subscription tier levels."""
    FREE = "FREE"          # Limited features, max users
    BASIC = "BASIC"        # Standard features, max projects
    PRO = "PRO"            # Full features, unlimited usage
    ENTERPRISE = "ENTERPRISE"  # Full features with support and SLA


class SubscriptionStatus(str):
    """Subscription status."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    TRIALING = "TRIALING"


class Subscription(BaseMixin, Base):
    """Organization subscription details."""
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_subscription_org"),
        {"comment": "Organization subscription details"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), index=True, nullable=False
    )
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    monthly_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.tier} status={self.status}>"


class OnboardingStep(str):
    """Onboarding steps for new organizations."""
    CREATE_ORG = "CREATE_ORG"
    SETUP_TEAMS = "SETUP_TEAMS"
    ADD_USERS = "ADD_USERS"
    CHOOSE_PLAN = "CHOOSE_PLAN"
    COMPLETE_SETUP = "COMPLETE_SETUP"


class OnboardingProgress(BaseMixin, Base):
    """Track onboarding progress for organizations."""
    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_onboarding_org"),
        {"comment": "Onboarding progress tracking"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), index=True, nullable=False
    )
    current_step: Mapped[str] = mapped_column(String(30), nullable=False)
    completed_steps: Mapped[list] = mapped_column(
        String(500), nullable=False
    )  # JSON array
    step_data: Mapped[dict] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<OnboardingProgress step={self.current_step}>"


class PaymentMethod(str):
    """Accepted payment methods."""
    CREDIT_CARD = "CREDIT_CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    PAYPAL = "PAYPAL"
    BITCOIN = "BITCOIN"


class BillingInfo(BaseMixin, Base):
    """Billing information for organizations."""
    __tablename__ = "billing_info"
    __table_args__ = (
        {"comment": "Billing information"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), index=True, nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    card_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<BillingInfo {self.payment_method}>"


class SystemEvent(BaseMixin, Base):
    """System events for monitoring and auditing."""
    __tablename__ = "system_events"
    __table_args__ = (
        {"comment": "System events for monitoring"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SystemEvent {self.event_type} severity={self.severity}>"