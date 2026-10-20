"""Pydantic schemas for Commercial module."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Subscription Schemas ---

class SubscriptionTier(str, Enum):
    """Subscription tier levels."""
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    TRIALING = "TRIALING"


class SubscriptionCreate(BaseModel):
    """Create subscription request."""
    tier: SubscriptionTier
    payment_method: str
    billing_email: str
    tax_id: Optional[str] = None


class SubscriptionOut(BaseModel):
    """Subscription response."""
    id: UUID
    organization_id: UUID
    tier: str
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionUpdate(BaseModel):
    """Update subscription request."""
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None


# --- Onboarding Schemas ---

class OnboardingStep(str, Enum):
    """Onboarding steps."""
    CREATE_ORG = "CREATE_ORG"
    SETUP_TEAMS = "SETUP_TEAMS"
    ADD_USERS = "ADD_USERS"
    CHOOSE_PLAN = "CHOOSE_PLAN"
    COMPLETE_SETUP = "COMPLETE_SETUP"


class OnboardingProgressCreate(BaseModel):
    """Create onboarding progress request."""
    organization_id: str
    current_step: OnboardingStep
    completed_steps: List[str] = []
    step_data: Dict = {}


class OnboardingProgressOut(BaseModel):
    """Onboarding progress response."""
    id: UUID
    organization_id: UUID
    current_step: str
    completed_steps: List[str]
    step_data: Dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Billing Schemas ---

class PaymentMethod(str, Enum):
    """Payment methods."""
    CREDIT_CARD = "CREDIT_CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    PAYPAL = "PAYPAL"
    BITCOIN = "BITCOIN"


class BillingInfoCreate(BaseModel):
    """Create billing info request."""
    organization_id: str
    payment_method: PaymentMethod
    billing_email: str
    tax_id: Optional[str] = None


class BillingInfoOut(BaseModel):
    """Billing info response."""
    id: UUID
    organization_id: UUID
    payment_method: str
    card_last4: Optional[str] = None
    billing_email: str
    tax_id: Optional[str] = None
    is_valid: bool

    model_config = ConfigDict(from_attributes=True)


# --- System Event Schemas ---

class SystemEventType(str, Enum):
    """System event types."""
    USER_CREATED = "USER_CREATED"
    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    LOGIN_FAILED = "LOGIN_FAILED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    API_RATE_LIMIT = "API_RATE_LIMIT"
    SECURITY_ALERT = "SECURITY_ALERT"


class SystemEventSeverity(str, Enum):
    """Event severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SystemEventCreate(BaseModel):
    """Create system event request."""
    organization_id: str
    event_type: SystemEventType
    severity: SystemEventSeverity
    message: str
    source: str


class SystemEventOut(BaseModel):
    """System event response."""
    id: UUID
    event_type: str
    severity: str
    message: str
    source: str
    metadata: Dict
    resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Monitoring Stats ---

class CommercialStats(BaseModel):
    """Commercial module statistics."""
    total_organizations: int = 0
    active_subscriptions: int = 0
    trial_organizations: int = 0
    new_registrations_last_30_days: int = 0
    avg_subscription_duration_days: float = 0.0