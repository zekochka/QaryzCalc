from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from qaryzcalc.models import (
    CalculationInput,
    CalculationResult,
    CalculationSummary,
    EarlyPayment,
    FirstPaymentBreakdown,
    ScheduleRow,
)

MONEY = Decimal("0.01")
ZERO = Decimal("0")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(source: date, months: int) -> date:
    month_index = source.month - 1 + months
    year = source.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_mortgage_loan_amount(property_price: Decimal, down_payment_amount: Decimal) -> Decimal:
    return quantize_money(property_price - down_payment_amount)


def calculate_down_payment_percent(property_price: Decimal, down_payment_amount: Decimal) -> Decimal:
    if property_price <= ZERO:
        return ZERO
    return (down_payment_amount / property_price * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def calculate_down_payment_amount(property_price: Decimal, down_payment_percent: Decimal) -> Decimal:
    return quantize_money(property_price * down_payment_percent / Decimal("100"))


def annuity_payment(balance: Decimal, monthly_rate: Decimal, months: int) -> Decimal:
    if months <= 0:
        return ZERO
    if monthly_rate == ZERO:
        return quantize_money(balance / Decimal(months))
    ratio = (Decimal("1") + monthly_rate) ** months
    payment = balance * monthly_rate * ratio / (ratio - Decimal("1"))
    return quantize_money(payment)


def validate_input(data: CalculationInput) -> None:
    errors: list[str] = []

    if data.loan_amount <= ZERO:
        errors.append("Сумма кредита должна быть больше нуля.")
    if data.annual_rate < ZERO:
        errors.append("Номинальная ставка не может быть отрицательной.")
    if data.term_months <= 0:
        errors.append("Срок кредита должен быть больше нуля.")
    if data.one_time_commission < ZERO:
        errors.append("Единовременная комиссия не может быть отрицательной.")
    if data.monthly_commission < ZERO:
        errors.append("Ежемесячная комиссия не может быть отрицательной.")
    if data.insurance_cost < ZERO:
        errors.append("Стоимость страховки не может быть отрицательной.")
    if data.first_payment_date < data.issue_date:
        errors.append("Дата первого платежа не может быть раньше даты выдачи кредита.")

    if data.mode == "mortgage":
        if data.property_price is None or data.property_price <= ZERO:
            errors.append("Для ипотеки укажите стоимость квартиры больше нуля.")
        if data.down_payment_amount < ZERO:
            errors.append("Первоначальный взнос не может быть отрицательным.")
        if data.property_price is not None and data.down_payment_amount > data.property_price:
            errors.append("Первоначальный взнос не может превышать стоимость квартиры.")

    last_planned_payment = add_months(data.first_payment_date, data.term_months - 1)
    for payment in sorted(data.early_payments, key=lambda item: item.payment_date):
        if payment.amount <= ZERO:
            errors.append("Сумма досрочного погашения должна быть больше нуля.")
        if payment.payment_date < data.issue_date or payment.payment_date > last_planned_payment:
            errors.append("Дата досрочного погашения должна находиться внутри срока кредита.")

    if errors:
        raise ValueError("\n".join(errors))


def calculate(data: CalculationInput) -> CalculationResult:
    validate_input(data)
    normalized = _normalize_input(data)
    baseline = _build_schedule(replace(normalized, early_payments=[]))
    result = _build_schedule(normalized)
    result.summary.interest_saved = quantize_money(
        max(baseline.summary.total_interest - result.summary.total_interest, ZERO)
    )
    return result


def _normalize_input(data: CalculationInput) -> CalculationInput:
    early_payments = sorted(data.early_payments, key=lambda item: item.payment_date)
    loan_amount = quantize_money(data.loan_amount)

    if data.mode == "mortgage" and data.property_price is not None:
        down_payment_amount = quantize_money(data.down_payment_amount)
        loan_amount = calculate_mortgage_loan_amount(data.property_price, down_payment_amount)
        down_payment_percent = calculate_down_payment_percent(data.property_price, down_payment_amount)
    else:
        down_payment_amount = quantize_money(data.down_payment_amount)
        down_payment_percent = data.down_payment_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    normalized_early_payments = [
        EarlyPayment(payment.payment_date, quantize_money(payment.amount), payment.recalc_type, payment.title)
        for payment in early_payments
    ]

    return replace(
        data,
        loan_amount=loan_amount,
        down_payment_amount=down_payment_amount,
        down_payment_percent=down_payment_percent,
        one_time_commission=quantize_money(data.one_time_commission),
        monthly_commission=quantize_money(data.monthly_commission),
        insurance_cost=quantize_money(data.insurance_cost),
        early_payments=normalized_early_payments,
    )


def _build_schedule(data: CalculationInput) -> CalculationResult:
    monthly_rate = (data.annual_rate / Decimal("100") / Decimal("12")).quantize(
        Decimal("0.0000000001"), rounding=ROUND_HALF_UP
    )
    balance = data.loan_amount
    remaining_months = data.term_months
    payment_date = data.first_payment_date
    payment_number = 1
    max_iterations = data.term_months + len(data.early_payments) + 1200

    annuity_target = annuity_payment(balance, monthly_rate, remaining_months)
    diff_principal_target = quantize_money(balance / Decimal(remaining_months))
    schedule: list[ScheduleRow] = []
    early_index = 0
    sorted_early = data.early_payments
    previous_payment_date = data.issue_date

    while balance > ZERO and payment_number <= max_iterations:
        interest = quantize_money(balance * monthly_rate)

        if data.payment_type == "annuity":
            if remaining_months <= 1:
                principal_paid = balance
                regular_payment = quantize_money(balance + interest)
            else:
                regular_payment = min(annuity_target, quantize_money(balance + interest))
                principal_paid = quantize_money(regular_payment - interest)
        else:
            if remaining_months <= 1:
                principal_paid = balance
            else:
                principal_paid = min(diff_principal_target, balance)
            regular_payment = quantize_money(principal_paid + interest)

        balance_after_regular = quantize_money(balance - principal_paid)
        extra_payment_requested, recalc_type, early_index = _collect_extra_payment(
            sorted_early,
            early_index,
            previous_payment_date,
            payment_date,
            payment_number,
        )
        extra_payment = quantize_money(min(extra_payment_requested, balance_after_regular))
        balance_after = quantize_money(balance_after_regular - extra_payment)

        if abs(balance_after) < MONEY:
            balance_after = ZERO

        schedule.append(
            ScheduleRow(
                payment_number=payment_number,
                payment_date=payment_date,
                balance_before=balance,
                regular_payment=regular_payment,
                interest=interest,
                principal_paid=principal_paid,
                commission=data.monthly_commission,
                extra_payment=extra_payment,
                balance_after=balance_after,
            )
        )

        balance = balance_after
        previous_payment_date = payment_date
        payment_date = add_months(payment_date, 1)
        payment_number += 1
        remaining_months = max(remaining_months - 1, 0)

        if balance > ZERO and remaining_months > 0 and extra_payment > ZERO:
            if data.payment_type == "annuity" and recalc_type == "reduce_payment":
                annuity_target = annuity_payment(balance, monthly_rate, remaining_months)
            if data.payment_type == "differentiated" and recalc_type == "reduce_payment":
                diff_principal_target = quantize_money(balance / Decimal(remaining_months))

    if balance > ZERO:
        raise ValueError("Не удалось завершить расчёт. Проверьте параметры кредита.")

    if early_index != len(sorted_early):
        raise ValueError("Один из досрочных платежей выходит за пределы фактического срока кредита.")

    summary = _build_summary(data, schedule, monthly_rate)
    return CalculationResult(input_data=data, schedule=schedule, summary=summary)


def _collect_extra_payment(
    payments: list[EarlyPayment],
    start_index: int,
    previous_payment_date: date,
    current_payment_date: date,
    payment_number: int,
) -> tuple[Decimal, str | None, int]:
    total = ZERO
    index = start_index
    recalc_type: str | None = None

    while index < len(payments):
        payment = payments[index]
        in_period = (
            previous_payment_date <= payment.payment_date <= current_payment_date
            if payment_number == 1
            else previous_payment_date < payment.payment_date <= current_payment_date
        )
        if not in_period:
            break
        total += payment.amount
        recalc_type = payment.recalc_type
        index += 1

    return quantize_money(total), recalc_type, index


def _build_summary(
    data: CalculationInput,
    schedule: list[ScheduleRow],
    monthly_rate: Decimal,
) -> CalculationSummary:
    total_regular = quantize_money(sum(row.regular_payment for row in schedule))
    total_interest = quantize_money(sum(row.interest for row in schedule))
    total_commissions = quantize_money(data.one_time_commission + sum(row.commission for row in schedule))
    total_insurance = quantize_money(data.insurance_cost)
    total_extra = quantize_money(sum(row.extra_payment for row in schedule))
    total_paid_to_bank = quantize_money(total_regular + total_extra + total_commissions)
    total_overpayment = quantize_money(total_interest + total_commissions + total_insurance)

    if data.mode == "mortgage":
        full_property_cost = quantize_money((data.property_price or data.loan_amount) + total_overpayment)
    else:
        full_property_cost = quantize_money(total_paid_to_bank + total_insurance)

    payment_values = [row.regular_payment + row.commission for row in schedule]
    first_row = schedule[0]
    effective_ratio = ZERO if data.loan_amount == ZERO else total_paid_to_bank / data.loan_amount

    return CalculationSummary(
        monthly_payment_min=min(payment_values),
        monthly_payment_max=max(payment_values),
        loan_amount=data.loan_amount,
        total_paid_to_bank=total_paid_to_bank,
        total_overpayment=total_overpayment,
        total_interest=total_interest,
        total_commissions=total_commissions,
        total_insurance=total_insurance,
        down_payment_amount=data.down_payment_amount,
        full_property_cost=full_property_cost,
        last_payment_date=schedule[-1].payment_date,
        payment_count=len(schedule),
        interest_saved=ZERO,
        effective_ratio=effective_ratio,
        first_payment=FirstPaymentBreakdown(
            balance_before=first_row.balance_before,
            monthly_rate=(monthly_rate * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            interest=first_row.interest,
            regular_payment=first_row.regular_payment,
            principal_paid=first_row.principal_paid,
            extra_payment=first_row.extra_payment,
            balance_after=first_row.balance_after,
        ),
    )
