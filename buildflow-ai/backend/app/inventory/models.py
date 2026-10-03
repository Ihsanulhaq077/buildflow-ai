import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

QTY = Numeric(18, 4)
COST = Numeric(18, 4)


class MovementType(str, enum.Enum):
    OPENING_STOCK = "OPENING_STOCK"
    PURCHASE_RECEIPT = "PURCHASE_RECEIPT"
    MATERIAL_ISSUE = "MATERIAL_ISSUE"
    MATERIAL_RETURN = "MATERIAL_RETURN"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"
    WASTE = "WASTE"


class Warehouse(BaseMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)  # None = central


class InventoryItem(BaseMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
    min_stock: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    max_stock: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    reorder_level: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))


class StockBalance(BaseMixin, Base):
    """Derived, lock-protected running balance (weighted-average cost). Always reconcilable to the ledger."""
    __tablename__ = "stock_balances"
    __table_args__ = (UniqueConstraint("warehouse_id", "item_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(COST, default=Decimal("0"))


class StockTransaction(BaseMixin, Base):
    """Append-only ledger. quantity is signed (+in / -out). Never updated or deleted."""
    __tablename__ = "stock_transactions"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    type: Mapped[MovementType] = mapped_column(Enum(MovementType, native_enum=False, length=20))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_cost: Mapped[Decimal] = mapped_column(COST)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
    reference_type: Mapped[str] = mapped_column(String(30), default="")
    reference_id: Mapped[str] = mapped_column(String(60), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class MaterialIssue(BaseMixin, Base):
    """Header for a site issue (kind=ISSUE) or return-to-store (kind=RETURN)."""
    __tablename__ = "material_issues"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(10))
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class MaterialIssueLine(BaseMixin, Base):
    __tablename__ = "material_issue_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    issue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material_issues.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_cost: Mapped[Decimal] = mapped_column(COST)
