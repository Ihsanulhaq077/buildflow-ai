"""Commercial API routes."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models import User

from app.commercial.schemas import (
    SubscriptionTier, SubscriptionStatus, SubscriptionCreate, SubscriptionOut,
    SubscriptionUpdate, OnboardingStep, OnboardingProgressCreate,
    OnboardingProgressOut, BillingInfoCreate, BillingInfoOut, PaymentMethod,
    SystemEventType, SystemEventSeverity, SystemEventCreate, SystemEventOut,
    CommercialStats
)
from app.commercial.service import CommercialService

router = APIRouter(prefix="/commercial", tags=["commercial"])

READ = require_permission("commercial.read")
MANAGE = require_permission("commercial.manage")


def get_commercial_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommercialService:
    """Get commercial service with current user and organization."""
    org_id = str(current_user.organization_id) if hasattr(current_user, 'organization_id') else "00000000-0000-0000-0000-000000000000"
    return CommercialService(db, org_id, current_user)


# --- Subscription Routes ---

@router.post("/subscription", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(
    data: SubscriptionCreate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Create a new subscription."""
    return service.create_subscription(data.dict())


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    _: bool = Depends(READ),
    service: CommercialService = Depends(get_commercial_service),
):
    """Get current organization's subscription."""
    return service.get_subscription()


@router.put("/subscription", response_model=SubscriptionOut)
def update_subscription(
    data: SubscriptionUpdate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Update subscription."""
    # Note: This is a placeholder - production would need more logic
    current = service.get_subscription()
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )
    return current


# --- Onboarding Routes ---

@router.post("/onboarding", response_model=OnboardingProgressOut, status_code=status.HTTP_201_CREATED)
def create_onboarding(
    data: OnboardingProgressCreate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Create onboarding progress."""
    return service.create_onboarding(data.dict())


@router.put("/onboarding", response_model=OnboardingProgressOut)
def update_onboarding(
    data: OnboardingProgressCreate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Update onboarding progress."""
    return service.update_onboarding(data=data.dict())


@router.get("/onboarding/complete")
def check_onboarding_complete(
    _: bool = Depends(READ),
    service: CommercialService = Depends(get_commercial_service),
):
    """Check if onboarding is complete."""
    complete = service.onboarding_complete()
    return {"complete": complete}


# --- Billing Routes ---

@router.post("/billing", response_model=BillingInfoOut, status_code=status.HTTP_201_CREATED)
def create_billing_info(
    data: BillingInfoCreate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Create billing info."""
    return service.create_billing_info(data.dict())


@router.get("/billing", response_model=BillingInfoOut)
def get_billing_info(
    _: bool = Depends(READ),
    service: CommercialService = Depends(get_commercial_service),
):
    """Get billing info."""
    return service.get_billing_info()


@router.put("/billing/card")
def set_card_last4(
    card_last4: str,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Set card last 4 digits."""
    result = service.set_card_last4(card_last4=card_last4)
    return {"success": True, "card_last4": card_last4}


# --- System Events Routes ---

@router.post("/events", response_model=SystemEventOut, status_code=status.HTTP_201_CREATED)
def log_event(
    data: SystemEventCreate,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Log a system event."""
    return service.log_event(data.dict())


@router.get("/events", response_model=List[SystemEventOut])
def list_events(
    limit: int = 50,
    offset: int = 0,
    severity: Optional[str] = None,
    _: bool = Depends(READ),
    service: CommercialService = Depends(get_commercial_service),
):
    """List system events."""
    return service.get_events(limit, offset, severity)


@router.post("/events/{event_id}/resolve")
def resolve_event(
    event_id: UUID,
    _: bool = Depends(MANAGE),
    service: CommercialService = Depends(get_commercial_service),
):
    """Mark an event as resolved."""
    success = service.resolve_event(str(event_id))
    return {"success": success, "event_id": str(event_id)}


# --- Statistics Route ---

@router.get("/stats", response_model=CommercialStats)
def get_stats(
    _: bool = Depends(READ),
    service: CommercialService = Depends(get_commercial_service),
):
    """Get commercial module statistics."""
    return service.get_stats()


def check_subscription_validity(
    service: CommercialService = Depends(get_commercial_service),
):
    """Check if subscription is valid."""
    return service.check_subscription_validity()