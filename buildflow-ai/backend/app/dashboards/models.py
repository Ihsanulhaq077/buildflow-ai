"""
Dashboard models for role-based analytics and visualizations.

Models:
- Dashboard: a dashboard layout for a role/user
- Widget: a visual component on a dashboard
- Chart: data visualization configuration
- DashboardPermission: access control for dashboards
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class DashboardType(str, Enum):
    """Type of dashboard."""
    ROLE_BASED = "ROLE_BASED"  # Pre-built for user role
    CUSTOM = "CUSTOM"          # User-created custom dashboard
    TEMPLATE = "TEMPLATE"      # Template for creating dashboards


class WidgetType(str, Enum):
    """Type of dashboard widget."""
    METRIC = "METRIC"          # Single value (e.g., total projects)
    CHART = "CHART"            # Chart visualization
    TABLE = "TABLE"            # Data table
    LIST = "LIST"              # List of items
    PROGRESS = "PROGRESS"      # Progress bar
    GAUGE = "GAUGE"            # Gauge/meter
    TIMELINE = "TIMELINE"      # Timeline view
    MAP = "MAP"                # Geographic map
    CALENDAR = "CALENDAR"      # Calendar view


class ChartType(str, Enum):
    """Type of chart visualization."""
    BAR = "BAR"
    LINE = "LINE"
    PIE = "PIE"
    DONUT = "DONUT"
    SCATTER = "SCATTER"
    AREA = "AREA"
    HEATMAP = "HEATMAP"
    RADAR = "RADAR"
    GAUGE = "GAUGE"
    FUNNEL = "FUNNEL"


class Dashboard(BaseMixin, Base):
    """
    A dashboard layout containing widgets for data visualization.

    Dashboards can be role-based templates or user-customized views.
    """
    __tablename__ = "dashboards"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_dashboard_org_name"),
        {"comment": "Role-based and custom dashboards"},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    dashboard_type: Mapped[str] = mapped_column(
        String(20), default=DashboardType.CUSTOM
    )
    target_role: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g., "PROJECT_MANAGER", "CEO", etc.
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    layout_config: Mapped[dict] = mapped_column(JSON, default=dict)  # Grid layout settings
    refresh_interval: Mapped[int] = mapped_column(Integer, default=300)  # seconds
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    widgets: Mapped[List["Widget"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan", order_by="Widget.position"
    )

    def __repr__(self) -> str:
        return f"<Dashboard {self.name} ({self.dashboard_type})>"


class Widget(BaseMixin, Base):
    """
    A visual component on a dashboard.

    Each widget displays data from a specific source (project, BOQ, inventory, etc.)
    with a specific visualization type.
    """
    __tablename__ = "widgets"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "position", name="uq_widget_dashboard_pos"),
        {"comment": "Dashboard widgets (charts, metrics, tables)"},
    )

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200))
    widget_type: Mapped[str] = mapped_column(String(20))
    data_source: Mapped[str] = mapped_column(String(100))  # e.g., "project.summary", "boq.costs"
    chart_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # Grid position
    width: Mapped[int] = mapped_column(Integer, default=6)  # Grid columns
    height: Mapped[int] = mapped_column(Integer, default=4)  # Grid rows
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # Widget-specific settings
    filters: Mapped[dict] = mapped_column(JSON, default=dict)  # Data filters
    refresh_interval: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Override dashboard interval
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)

    dashboard: Mapped["Dashboard"] = relationship(back_populates="widgets")

    def __repr__(self) -> str:
        return f"<Widget {self.title} ({self.widget_type})>"


class DashboardPermission(BaseMixin, Base):
    """
    Permission for accessing a dashboard.
    Controls which users/roles can view/edit specific dashboards.
    """
    __tablename__ = "dashboard_permissions"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "user_id", "role_id", name="uq_dash_perm"),
        {"comment": "Dashboard access permissions"},
    )

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roles.id"), index=True, nullable=True
    )
    can_view: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_share: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<DashboardPermission dash={self.dashboard_id} user={self.user_id} role={self.role_id}>"