from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")


def parse_decimal(value: str, field_name: str) -> Decimal:
    cleaned = value.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not cleaned:
        return ZERO
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f'Поле "{field_name}" заполнено некорректно.') from exc


def format_money(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    integer_part, _, fraction = f"{normalized:.2f}".partition(".")
    integer_with_spaces = f"{int(integer_part):,}".replace(",", " ")
    if fraction == "00":
        return f"{integer_with_spaces} \u20b8"
    return f"{integer_with_spaces},{fraction} \u20b8"


def format_percent(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}".replace(".", ",") + "%"


def format_ratio(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}".replace(".", ",")


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")

