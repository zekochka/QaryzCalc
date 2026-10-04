from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

LoanMode = Literal["loan", "mortgage"]
PaymentType = Literal["annuity", "differentiated"]
TermUnit = Literal["years", "months"]
RecalcType = Literal["reduce_term", "reduce_payment"]


@dataclass(slots=True)
class EarlyPayment:
    payment_date: date
    amount: Decimal
    recalc_type: RecalcType
    title: str = ""


@dataclass(slots=True)
class CalculationInput:
    mode: LoanMode
    loan_amount: Decimal
    annual_rate: Decimal
    term_value: int
    term_unit: TermUnit
    issue_date: date
    first_payment_date: date
    payment_type: PaymentType
    one_time_commission: Decimal = Decimal("0")
    monthly_commission: Decimal = Decimal("0")
    insurance_cost: Decimal = Decimal("0")
    apr_rate: Decimal | None = None
    property_price: Decimal | None = None
    down_payment_amount: Decimal = Decimal("0")
    down_payment_percent: Decimal = Decimal("0")
    early_payments: list[EarlyPayment] = field(default_factory=list)

    @property
    def term_months(self) -> int:
        return self.term_value * 12 if self.term_unit == "years" else self.term_value


@dataclass(slots=True)
class ScheduleRow:
    payment_number: int
    payment_date: date
    balance_before: Decimal
    regular_payment: Decimal
    interest: Decimal
    principal_paid: Decimal
    commission: Decimal
    extra_payment: Decimal
    balance_after: Decimal

    @property
    def total_payment(self) -> Decimal:
        return self.regular_payment + self.commission + self.extra_payment


@dataclass(slots=True)
class FirstPaymentBreakdown:
    balance_before: Decimal
    monthly_rate: Decimal
    interest: Decimal
    regular_payment: Decimal
    principal_paid: Decimal
    extra_payment: Decimal
    balance_after: Decimal


@dataclass(slots=True)
class CalculationSummary:
    monthly_payment_min: Decimal
    monthly_payment_max: Decimal
    loan_amount: Decimal
    total_paid_to_bank: Decimal
    total_overpayment: Decimal
    total_interest: Decimal
    total_commissions: Decimal
    total_insurance: Decimal
    down_payment_amount: Decimal
    full_property_cost: Decimal
    last_payment_date: date
    payment_count: int
    interest_saved: Decimal
    effective_ratio: Decimal
    first_payment: FirstPaymentBreakdown


@dataclass(slots=True)
class CalculationResult:
    input_data: CalculationInput
    schedule: list[ScheduleRow]
    summary: CalculationSummary
