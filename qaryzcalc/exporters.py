from __future__ import annotations

import csv
from pathlib import Path

from qaryzcalc.formatters import format_date
from qaryzcalc.models import CalculationResult


def export_schedule_to_csv(path: str | Path, result: CalculationResult) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(
            [
                "Номер платежа",
                "Дата",
                "Остаток до платежа",
                "Платеж",
                "Проценты",
                "Погашение основного долга",
                "Комиссии",
                "Досрочное погашение",
                "Остаток после платежа",
            ]
        )
        for row in result.schedule:
            writer.writerow(
                [
                    row.payment_number,
                    format_date(row.payment_date),
                    f"{row.balance_before:.2f}",
                    f"{row.regular_payment:.2f}",
                    f"{row.interest:.2f}",
                    f"{row.principal_paid:.2f}",
                    f"{row.commission:.2f}",
                    f"{row.extra_payment:.2f}",
                    f"{row.balance_after:.2f}",
                ]
            )

    return target
