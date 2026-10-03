"""Deterministic BOQ maths (Decimal only). No LLM, no floats.

unit_rate = material_rate * (1 + waste%) + labour_rate + equipment_rate      (waste applies to material only)
amount    = quantity * unit_rate
direct    = sum(item amounts)            (sum of the rounded amounts users see)
overhead  = direct * overhead%;  contingency = direct * contingency%
subtotal  = direct + overhead + contingency
profit    = subtotal * profit%;  selling_price = subtotal + profit;  margin% = profit / selling_price
"""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def q2(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def unit_rate(material_rate: Decimal, waste_pct: Decimal, labour_rate: Decimal, equipment_rate: Decimal) -> Decimal:
    return q2(material_rate * (1 + waste_pct / HUNDRED) + labour_rate + equipment_rate)


def item_amount(quantity: Decimal, rate: Decimal) -> Decimal:
    return q2(quantity * rate)


def summarize(items, overhead_pct: Decimal, contingency_pct: Decimal, profit_pct: Decimal) -> dict:
    material = labour = equipment = Decimal("0")
    direct = Decimal("0")
    for i in items:
        material += i.quantity * i.material_rate * (1 + i.waste_pct / HUNDRED)
        labour += i.quantity * i.labour_rate
        equipment += i.quantity * i.equipment_rate
        direct += item_amount(i.quantity, unit_rate(i.material_rate, i.waste_pct, i.labour_rate, i.equipment_rate))
    overhead = q2(direct * overhead_pct / HUNDRED)
    contingency = q2(direct * contingency_pct / HUNDRED)
    subtotal = direct + overhead + contingency
    profit = q2(subtotal * profit_pct / HUNDRED)
    selling = subtotal + profit
    margin = q2(profit / selling * HUNDRED) if selling else Decimal("0.00")
    return {
        "material_cost": q2(material), "labour_cost": q2(labour), "equipment_cost": q2(equipment),
        "direct_cost": direct, "overhead": overhead, "contingency": contingency, "subtotal": subtotal,
        "profit": profit, "selling_price": selling, "gross_margin_pct": margin,
    }
