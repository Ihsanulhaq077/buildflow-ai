"""Commercial service - subscriptions, onboarding, and monitoring."""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Organization, User
from app.commercial.models import (
    Subscription, SubscriptionStatus, SubscriptionTier,
    OnboardingProgress, OnboardingStep,
    BillingInfo, PaymentMethod,
    SystemEvent,
)

from app.commercial.schemas import (
    SubscriptionTier, SubscriptionStatus, OnboardingStep,
    PaymentMethod, SystemEventType, SystemEventSeverity,
)

log = logging.getLogger("buildflow.commercial")


class CommercialService:
    """Manage commercial operations."""

    # Tier feature limits
    TIER_LIMITS = {
        SubscriptionTier.FREE: {"monthly_events": 1000, "max_projects": 3, "max_users": 3, "ai_enabled": False},
        SubscriptionTier.BASIC: {"monthly_events": 10000, "max_projects": 20, "max_users": 10, "ai_enabled": True},
        SubscriptionTier.PRO: {"monthly_events": 100000, "max_projects": None, "max_users": None, "ai_enabled": True},
        SubscriptionTier.ENTERPRISE: {"monthly_events": None, "max_projects": None, "max_users": None, "ai_enabled": True},
    }

    def __init__(self, db: Session, org_id: str, user: User):
        self.db = db
        self.org_id = org_id
        self.user = user

    # --- Subscription Operations ---

    def create_subscription(self, data: dict) -> Subscription:
        """Create a new subscription for an organization."""
        now = datetime.utcnow()
        subscription = Subscription(
            organization_id=self.org_id,
            tier=data.get("tier", SubscriptionTier.FREE),
            status=SubscriptionStatus.TRIALING if data.get("is_trial", False) else SubscriptionStatus.INACTIVE,
            start_date=now,
            end_date=now + timedelta(days=30) if data.get("is_trial", False) else None,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        self.db.add(subscription)
        self.db.commit()
        return subscription

    def get_subscription(self, org_id: str = None) -> Optional[Subscription]:
        """Get subscription for an organization."""
        target_org = org_id or self.org_id
        stmt = select(Subscription).where(
            Subscription.organization_id == target_org,
        )
        return self.db.scalar(stmt)

    def activate_subscription(self, org_id: str = None) -> Optional[Subscription]:
        """Activate a subscription."""
        subscription = self.get_subscription(org_id)
        if subscription:
            subscription.status = SubscriptionStatus.ACTIVE
            self.db.commit()
        return subscription

    def cancel_subscription(self, org_id: str = None) -> Optional[Subscription]:
        """Cancel a subscription."""
        subscription = self.get_subscription(org_id)
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            self.db.commit()
        return subscription

    def get_tier_limits(self, tier: str = None) -> Dict:
        """Get feature limits for a tier."""
        sub = self.get_subscription()
        tier = tier or (sub.tier if sub else SubscriptionTier.FREE)
        return self.TIER_LIMITS.get(tier, self.TIER_LIMITS[SubscriptionTier.FREE])

    def check_limits(self, tier: str = None) -> Dict:
        """Check if current usage is within limits for the tier."""
        limits = self.get_tier_limits(tier)
        results = {"monthly_events_within": True, "max_projects_within": True, "max_users_within": True}

        # In production, we'd query actual usage counts here
        # For now, return defaults
        return results

    # --- Onboarding Operations ---

    def create_onboarding(self, data: dict) -> OnboardingProgress:
        """Create onboarding progress for an organization."""
        now = datetime.utcnow()
        progress = OnboardingProgress(
            organization_id=data.get("organization_id", self.org_id),
            current_step=data.get("current_step", OnboardingStep.CREATE_ORG),
            completed_steps=json.dumps(data.get("completed_steps", [])),
            step_data=json.dumps(data.get("step_data", {})),
            created_at=now,
            updated_at=now,
        )
        self.db.add(progress)
        self.db.commit()
        return progress

    def update_onboarding(self, org_id: str = None, *, data: dict) -> Optional[OnboardingProgress]:
        """Update onboarding progress."""
        target_org = org_id or self.org_id
        progress = self.get_onboarding(target_org)
        if not progress:
            return None

        step = data.get("current_step")
        if step:
            progress.current_step = step
        if data.get("completed_steps"):
            progress.completed_steps = json.dumps(data["completed_steps"])
        if data.get("step_data"):
            progress.step_data = json.dumps(data["step_data"])
        progress.updated_at = datetime.utcnow()
        self.db.commit()
        return progress

    def get_onboarding(self, org_id: str = None) -> Optional[OnboardingProgress]:
        """Get onboarding progress for an organization."""
        target_org = org_id or self.org_id
        stmt = select(OnboardingProgress).where(
            OnboardingProgress.organization_id == target_org,
        )
        return self.db.scalar(stmt)

    def onboarding_complete(self, org_id: str = None) -> bool:
        """Check if onboarding is complete."""
        progress = self.get_onboarding(org_id)
        if not progress:
            return False
        return progress.current_step == OnboardingStep.COMPLETE_SETUP

    # --- Billing Operations ---

    def create_billing_info(self, data: dict) -> BillingInfo:
        """Create billing info for an organization."""
        billing = BillingInfo(
            organization_id=data.get("organization_id", self.org_id),
            payment_method=data.get("payment_method", PaymentMethod.CREDIT_CARD),
            billing_email=data.get("billing_email"),
            tax_id=data.get("tax_id"),
        )
        self.db.add(billing)
        self.db.commit()
        return billing

    def get_billing_info(self, org_id: str = None) -> Optional[BillingInfo]:
        """Get billing info for an organization."""
        target_org = org_id or self.org_id
        stmt = select(BillingInfo).where(
            BillingInfo.organization_id == target_org,
        )
        return self.db.scalar(stmt)

    def set_card_last4(self, org_id: str = None, card_last4: str = None) -> Optional[BillingInfo]:
        """Update card last 4 digits."""
        billing = self.get_billing_info(org_id)
        if billing:
            billing.card_last4 = card_last4
            self.db.commit()
        return billing

    # --- System Event Operations ---

    def log_event(self, data: dict) -> SystemEvent:
        """Log a system event."""
        event = SystemEvent(
            event_type=data.get("event_type", "CUSTOM"),
            severity=data.get("severity", "LOW"),
            message=data.get("message"),
            source=data.get("source", "application"),
            event_metadata=json.dumps(data.get("metadata", {})),
            resolved=False,
        )
        self.db.add(event)
        self.db.commit()
        return event

    def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: Optional[str] = None,
        resolved: bool = False,
    ) -> List[SystemEvent]:
        """Get system events."""
        stmt = select(SystemEvent).where(
            SystemEvent.organization_id == self.org_id,
            SystemEvent.deleted_at.is_(None),
        ).order_by(SystemEvent.created_at.desc()).limit(limit).offset(offset)

        if severity:
            stmt = stmt.where(SystemEvent.severity == severity)
        stmt = stmt.where(SystemEvent.resolved == resolved)
        return self.db.scalars(stmt).all()

    def resolve_event(self, event_id: str) -> bool:
        """Mark an event as resolved."""
        event = self.db.get(SystemEvent, event_id)
        if event:
            event.resolved = True
            self.db.commit()
            return True
        return False

    # --- Monitoring Statistics ---

    def get_stats(self) -> Dict:
        """Get commercial module statistics."""
        # Organizations
        total_orgs = self.db.execute(
            select(func.count(Organization.id)).where(Organization.is_active.is_(True))
        ).scalar() or 0

        # Active subscriptions
        active_subs = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).scalar() or 0

        # Trial organizations
        trial_subs = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.TRIALING
            )
        ).scalar() or 0

        # New registrations in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_registrations = self.db.execute(
            select(func.count(User.id)).where(
                User.created_at >= thirty_days_ago,
                User.deleted_at.is_(None),
            )
        ).scalar() or 0

        # Average subscription duration
        # Placeholder - in production, query actual dates
        avg_duration = 0.0

        return {
            "total_organizations": total_orgs,
            "active_subscriptions": active_subs,
            "trial_organizations": trial_subs,
            "new_registrations_last_30_days": new_registrations,
            "avg_subscription_duration_days": avg_duration,
        }

    def check_subscription_validity(self) -> bool:
        """Check if the current organization has a valid subscription."""
        subscription = self.get_subscription()
        if not subscription:
            return False

        if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            return False

        if subscription.end_date and subscription.end_date < datetime.utcnow():
            return False

        return True