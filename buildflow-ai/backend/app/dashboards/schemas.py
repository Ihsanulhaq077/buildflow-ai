"""Pydantic schemas for Dashboards module."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DashboardCreate(BaseModel):
    """Create dashboard request."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    dashboard_type: str = "CUSTOM"
    target_role: Optional[str] = None
    layout_config: Optional[Dict] = None
    is_default: bool = False


class DashboardUpdate(BaseModel):
    """Update dashboard request."""
    name: Optional[str] = None
    description: Optional[str] = None
    layout_config: Optional[Dict] = None
    refresh_interval: Optional[int] = None


class DashboardOut(BaseModel):
    """Dashboard response."""
    id: UUID
    organization_id: UUID
    name: str
    description: str
    dashboard_type: str
    target_role: Optional[str] = None
    is_public: bool
    is_default: bool
    layout_config: Dict
    refresh_interval: int
    created_at: datetime
    updated_at: datetime
    widget_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class WidgetCreate(BaseModel):
    """Create widget request."""
    title: str
    widget_type: str
    data_source: str
    chart_type: Optional[str] = None
    position: int
    width: int = 6
    height: int = 4
    config: Optional[Dict] = None
    filters: Optional[Dict] = None


class WidgetUpdate(BaseModel):
    """Update widget request."""
    title: Optional[str] = None
    data_source: Optional[str] = None
    config: Optional[Dict] = None
    filters: Optional[Dict] = None
    is_visible: Optional[bool] = None


class WidgetOut(BaseModel):
    """Widget response."""
    id: UUID
    dashboard_id: UUID
    title: str
    widget_type: str
    data_source: str
    chart_type: Optional[str] = None
    position: int
    width: int
    height: int
    config: Dict
    filters: Dict
    is_visible: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardPermissionCreate(BaseModel):
    """Create dashboard permission."""
    user_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    can_view: bool = True
    can_edit: bool = False
    can_share: bool = False
    expires_at: Optional[datetime] = None


class DashboardPermissionOut(BaseModel):
    """Dashboard permission response."""
    id: UUID
    dashboard_id: UUID
    user_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    can_view: bool
    can_edit: bool
    can_share: bool
    granted_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    """Summary of all dashboards in an organization."""
    total_dashboards: int
    default_dashboards: int
    templates: int
    custom_dashboards: int


class WidgetData(BaseModel):
    """Data returned by a widget."""
    title: str
    type: str
    data: dict
    metadata: Optional[Dict] = None


class DashboardData(BaseModel):
    """Complete dashboard data including all widgets."""
    dashboard: DashboardOut
    widgets: List[WidgetData] = []
    updated_at: datetime = Field(default_factory=datetime.now)