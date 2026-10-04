from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from qaryzcalc.calculations import (
    calculate,
    calculate_down_payment_amount,
    calculate_down_payment_percent,
    calculate_mortgage_loan_amount,
)
from qaryzcalc.models import CalculationInput, EarlyPayment


class CalculationTests(unittest.TestCase):
    def test_control_annuity_case_matches_spec(self) -> None:
        result = calculate(
            CalculationInput(
                mode="mortgage",
                loan_amount=Decimal("16000000"),
                annual_rate=Decimal("10"),
                term_value=15,
                term_unit="years",
                issue_date=date(2026, 7, 31),
                first_payment_date=date(2026, 8, 31),
                payment_type="annuity",
                property_price=Decimal("20000000"),
                down_payment_amount=Decimal("4000000"),
                down_payment_percent=Decimal("20"),
            )
        )

        self.assertAlmostEqual(float(result.summary.monthly_payment_max), 171937, delta=1.5)
        self.assertAlmostEqual(float(result.summary.total_paid_to_bank), 30948627, delta=2.0)
        self.assertAlmostEqual(float(result.summary.total_interest), 14948627, delta=2.0)
        self.assertEqual(result.summary.payment_count, 180)

    def test_differentiated_payments_go_down(self) -> None:
        result = calculate(
            CalculationInput(
                mode="loan",
                loan_amount=Decimal("12000000"),
                annual_rate=Decimal("12"),
                term_value=24,
                term_unit="months",
                issue_date=date(2026, 7, 31),
                first_payment_date=date(2026, 8, 31),
                payment_type="differentiated",
            )
        )

        self.assertGreater(result.schedule[0].regular_payment, result.schedule[-1].regular_payment)
        self.assertEqual(result.summary.total_interest, Decimal("1500000.00"))

    def test_early_payment_reduce_payment_keeps_term_and_reduces_future_payment(self) -> None:
        result = calculate(
            CalculationInput(
                mode="loan",
                loan_amount=Decimal("12000000"),
                annual_rate=Decimal("12"),
                term_value=24,
                term_unit="months",
                issue_date=date(2026, 7, 31),
                first_payment_date=date(2026, 8, 31),
                payment_type="annuity",
                early_payments=[EarlyPayment(date(2026, 12, 15), Decimal("1000000"), "reduce_payment")],
            )
        )

        self.assertEqual(result.summary.payment_count, 24)
        self.assertGreater(result.summary.interest_saved, Decimal("0"))
        self.assertGreater(result.schedule[4].regular_payment, result.schedule[5].regular_payment)

    def test_early_payment_reduce_term_shortens_schedule(self) -> None:
        result = calculate(
            CalculationInput(
                mode="loan",
                loan_amount=Decimal("12000000"),
                annual_rate=Decimal("12"),
                term_value=24,
                term_unit="months",
                issue_date=date(2026, 7, 31),
                first_payment_date=date(2026, 8, 31),
                payment_type="annuity",
                early_payments=[EarlyPayment(date(2026, 12, 15), Decimal("1000000"), "reduce_term")],
            )
        )

        self.assertLess(result.summary.payment_count, 24)
        self.assertGreater(result.summary.interest_saved, Decimal("0"))

    def test_mortgage_helpers_sync_values(self) -> None:
        property_price = Decimal("20000000")
        down_payment_amount = calculate_down_payment_amount(property_price, Decimal("20"))
        loan_amount = calculate_mortgage_loan_amount(property_price, down_payment_amount)
        down_payment_percent = calculate_down_payment_percent(property_price, down_payment_amount)

        self.assertEqual(down_payment_amount, Decimal("4000000.00"))
        self.assertEqual(loan_amount, Decimal("16000000.00"))
        self.assertEqual(down_payment_percent, Decimal("20.00"))


if __name__ == "__main__":
    unittest.main()
