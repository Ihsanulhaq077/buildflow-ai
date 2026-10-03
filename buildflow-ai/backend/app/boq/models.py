import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)
QTY = Numeric(18, 4)
PCT = Numeric(6, 2)

# Starter units seeded per organization. Fully editable; conversion factors are NOT seeded (no hardcoded assumptions).
DEFAULT_UNITS = [
    ("BAG", "Cement Bag"), ("KG", "Kilogram"), ("TON", "Ton"), ("CFT", "Cubic Feet"),
    ("SQFT", "Square Feet"), ("SQM", "Square Metre"), ("NOS", "Numbers"), ("BRICK", "Bricks"),
    ("LDAY", "Labour Day"),
]


class CostCategory(str, enum.Enum):
    MATERIAL = "MATERIAL"
    LABOUR = "LABOUR"
    EQUIPMENT = "EQUIPMENT"
    SUBCONTRACT = "SUBCONTRACT"
    TRANSPORT = "TRANSPORT"
    SITE_EXPENSE = "SITE_EXPENSE"
    OVERHEAD = "OVERHEAD"
    CONTINGENCY = "CONTINGENCY"
    OTHER = "OTHER"


class ApprovalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class CostCode(BaseMixin, Base):
    __tablename__ = "cost_codes"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[CostCategory] = mapped_column(Enum(CostCategory, native_enum=False, length=20))


class Unit(BaseMixin, Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))


class UnitConversion(BaseMixin, Base):
    """1 from_unit = factor * to_unit. Defined by the organization."""
    __tablename__ = "unit_conversions"
    __table_args__ = (UniqueConstraint("organization_id", "from_unit_id", "to_unit_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    from_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"))
    to_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"))
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 8))


class BOQ(BaseMixin, Base):
    __tablename__ = "boqs"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, native_enum=False, length=20),
                                                   default=ApprovalStatus.DRAFT)
    overhead_pct: Mapped[Decimal] = mapped_column(PCT, default=Decimal("0"))
    contingency_pct: Mapped[Decimal] = mapped_column(PCT, default=Decimal("0"))
    profit_pct: Mapped[Decimal] = mapped_column(PCT, default=Decimal("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class BOQItem(BaseMixin, Base):
    __tablename__ = "boq_items"
    __table_args__ = (UniqueConstraint("boq_id", "item_code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    boq_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("boqs.id"), index=True)
    item_code: Mapped[str] = mapped_column(String(50))
    trade: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"))
    waste_pct: Mapped[Decimal] = mapped_column(PCT, default=Decimal("0"))
    material_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    labour_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    equipment_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
