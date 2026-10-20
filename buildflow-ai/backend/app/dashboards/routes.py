"""Dashboards API routes."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models import User

from app.dashboards.schemas import (
    DashboardCreate,
    DashboardOut,
    DashboardUpdate,
    WidgetCreate,
    WidgetOut,
    WidgetUpdate,
    DashboardData,
)
from app.dashboards.service import DashboardService, DashboardDataService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

READ = require_permission("dashboards.read")
MANAGE = require_permission("dashboards.manage")


def get_dashboard_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardService:
    """Get dashboard service scoped to the caller's organization."""
    return DashboardService(db, current_user.organization_id, current_user)


def get_dashboard_data_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardDataService:
    """Get dashboard data service scoped to the caller's organization."""
    return DashboardDataService(db, current_user.organization_id)


# --- Dashboard Routes ---

@router.get("", response_model=List[DashboardOut])
@router.get("/", response_model=List[DashboardOut], include_in_schema=False)
def list_dashboards(
    limit: int = 50,
    offset: int = 0,
    dashboard_type: str = None,
    is_default: bool = None,
    target_role: str = None,
    include_all: bool = False,
    user: User = Depends(READ),
    service: DashboardService = Depends(get_dashboard_service),
):
    """List dashboards visible to the caller.

    By default only dashboards matching the caller's role (or public ones) are returned.
    Owners and dashboard managers can pass ``include_all=true`` to see every dashboard.
    """
    if include_all and not (user.role and user.role.name == "OWNER"):
        from app.deps import has_permission
        if not has_permission(user, "dashboards.manage"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
    dashboards = service.list_dashboards(
        limit=limit,
        offset=offset,
        dashboard_type=dashboard_type,
        is_default=is_default,
        target_role=target_role,
        include_all=include_all,
    )
    return dashboards


@router.get("/my-dashboard", response_model=Optional[DashboardOut])
def my_dashboard(user: User = Depends(READ),
                 service: DashboardService = Depends(get_dashboard_service)):
    """The dashboard this user should land on: their role's default dashboard."""
    dashboard = service.get_default_dashboard()
    if dashboard is None:
        return None
    return DashboardOut.model_validate(dashboard)


@router.post("", response_model=DashboardOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DashboardOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_dashboard(
    data: DashboardCreate,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Create a new dashboard."""
    dashboard = service.create_dashboard(data.dict())
    return dashboard


@router.get("/{dashboard_id}", response_model=DashboardOut)
def get_dashboard(
    dashboard_id: UUID,
    _: bool = Depends(READ),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Get a dashboard by ID."""
    dashboard = service.get_dashboard(str(dashboard_id))
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    return dashboard


@router.put("/{dashboard_id}", response_model=DashboardOut)
def update_dashboard(
    dashboard_id: UUID,
    data: DashboardUpdate,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Update a dashboard."""
    dashboard = service.update_dashboard(str(dashboard_id), data.dict(exclude_unset=True))
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    return dashboard


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(
    dashboard_id: UUID,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Delete a dashboard."""
    success = service.delete_dashboard(str(dashboard_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    return None


# --- Widget Routes ---

@router.get("/{dashboard_id}/widgets", response_model=List[WidgetOut])
def list_widgets(
    dashboard_id: UUID,
    _: bool = Depends(READ),
    service: DashboardService = Depends(get_dashboard_service),
):
    """List widgets for a dashboard."""
    widgets = service.list_widgets(str(dashboard_id))
    return widgets


@router.post("/{dashboard_id}/widgets", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def add_widget(
    dashboard_id: UUID,
    data: WidgetCreate,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Add a widget to a dashboard."""
    widget = service.add_widget(str(dashboard_id), data.dict())
    return widget


@router.put("/{dashboard_id}/widgets/{widget_id}", response_model=WidgetOut)
def update_widget(
    _dashboard_id: UUID,
    widget_id: UUID,
    data: WidgetUpdate,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Update a widget."""
    widget = service.update_widget(str(widget_id), data.dict(exclude_unset=True))
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Widget {widget_id} not found",
        )
    return widget


@router.delete("/{dashboard_id}/widgets/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    _dashboard_id: UUID,
    widget_id: UUID,
    _: bool = Depends(MANAGE),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Delete a widget."""
    success = service.delete_widget(str(widget_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Widget {widget_id} not found",
        )
    return None


# --- Dashboard Data Route ---

@router.get("/{dashboard_id}/data", response_model=DashboardData)
def get_dashboard_data(
    dashboard_id: UUID,
    _: bool = Depends(READ),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    data_service: DashboardDataService = Depends(get_dashboard_data_service),
):
    """Get complete dashboard data including all widgets and their data."""
    dashboard = dashboard_service.get_dashboard(str(dashboard_id))
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )

    # Get widgets
    widgets = dashboard_service.list_widgets(str(dashboard_id))

    # Get data for each widget based on its data source
    widget_data_list = []
    for widget in widgets:
        data = {}
        try:
            # Route to appropriate data service method based on data_source
            if widget.data_source == "project.summary":
                data = data_service.get_project_summary()
            elif widget.data_source == "budget.summary":
                data = data_service.get_budget_summary()
            elif widget.data_source == "procurement.summary":
                data = data_service.get_procurement_summary()
            elif widget.data_source == "inventory.summary":
                data = data_service.get_inventory_summary()
            elif widget.data_source == "labour.summary":
                data = data_service.get_labour_summary()
            elif widget.data_source == "dailylog.summary":
                data = data_service.get_dailylog_summary()
            elif widget.data_source == "expense.summary":
                data = data_service.get_expense_summary()
            elif widget.data_source == "task.summary":
                data = data_service.get_task_summary()
            elif widget.data_source == "overall.summary":
                data = data_service.get_overall_summary()
            else:
                # Default empty data for unknown sources
                data = {"message": f"No data source implementation for {widget.data_source}"}
        except Exception as e:
            data = {"error": f"Failed to load data: {str(e)}"}

        widget_data_list.append(
            {
                "title": widget.title,
                "type": widget.widget_type,
                "data": data,
                "metadata": {
                    "chart_type": widget.chart_type,
                    "config": widget.config,
                    "filters": widget.filters,
                }
            }
        )

    return DashboardData(
        dashboard=dashboard,
        widgets=widget_data_list,
    )