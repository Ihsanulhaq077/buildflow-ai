"""Deterministic labour cost. cost = days * daily_rate + overtime_hours * overtime_rate (Decimal, rounded half-up to 0.01)."""
from decimal import Decimal

from app.boq.calculations import q2
from app.labour.models import DAYS, AttendanceStatus


def entry_cost(status: AttendanceStatus, overtime_hours: Decimal, daily_rate: Decimal, overtime_rate: Decimal) -> Decimal:
    return q2(DAYS[status] * daily_rate + overtime_hours * overtime_rate)
