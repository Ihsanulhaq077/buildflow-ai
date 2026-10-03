import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)
QTY = Numeric(18, 4)


class ReqStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ORDERED = "ORDERED"
    CANCELLED = "CANCELLED"


class POStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


def _enum(e):
    return Enum(e, native_enum=False, length=24)


class Supplier(BaseMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    contact_person: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseRequisition(BaseMixin, Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[ReqStatus] = mapped_column(_enum(ReqStatus), default=ReqStatus.DRAFT)
    notes: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decision_comment: Mapped[str] = mapped_column(String(500), default="")


class RequisitionLine(BaseMixin, Base):
    __tablename__ = "requisition_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    requisition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_requisitions.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    boq_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("boq_items.id"), nullable=True)
    stock_on_hand: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))   # snapshot at last check
    on_order: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))        # snapshot at last check
    shortage_qty: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))    # quantity that must be bought
    exceeds_boq: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(String(300), default="")


class SupplierQuote(BaseMixin, Base):
    __tablename__ = "supplier_quotes"
    __table_args__ = (UniqueConstraint("requisition_id", "supplier_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    requisition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_requisitions.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"))
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class QuoteLine(BaseMixin, Base):
    __tablename__ = "quote_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_quotes.id"), index=True)
    requisition_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requisition_lines.id"))
    unit_rate: Mapped[Decimal] = mapped_column(MONEY)


class PurchaseOrder(BaseMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"))
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"))
    requisition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_requisitions.id"), nullable=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_quotes.id"), nullable=True)
    status: Mapped[POStatus] = mapped_column(_enum(POStatus), default=POStatus.DRAFT)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str] = mapped_column(String(500), default="")


class POLine(BaseMixin, Base):
    __tablename__ = "po_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_rate: Mapped[Decimal] = mapped_column(MONEY)
    received_qty: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))  # accepted quantity only
    requisition_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requisition_lines.id"), nullable=True)


class GoodsReceipt(BaseMixin, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"))
    delivery_note: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(String(500), default="")
    received_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class GRNLine(BaseMixin, Base):
    __tablename__ = "grn_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    grn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    po_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("po_lines.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    quantity_accepted: Mapped[Decimal] = mapped_column(QTY)
    quantity_rejected: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    unit_rate: Mapped[Decimal] = mapped_column(MONEY)
