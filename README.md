# QaryzCalc

`QaryzCalc` is a desktop calculator for consumer loans and mortgages on Windows. The app runs locally, does not need a server, and helps compare monthly payments, total overpayment, early repayments, and the full amortization schedule in a friendly visual form.

## Features

- Loan and mortgage modes in one window
- Light and dark themes
- Annuity and differentiated repayment
- Down payment sync in amount and percent
- Multiple early repayments with two recalculation strategies
- Summary cards, detailed payment table, and two charts
- CSV export of the amortization schedule
- Simple explanation block describing how the calculation works

## Installation

1. Create and activate a virtual environment if you want an isolated setup.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

If `python` is not in `PATH`, use the full path to your interpreter instead.

## Run

```powershell
python main.py
```

If your system Python is a different version, you can also start the app with a double click on `start_qaryzcalc.bat`. That launcher prefers the bundled compatible runtime automatically.

## Tests

Run the calculation tests with:

```powershell
python -m unittest discover -s tests -v
```

The tests cover:

- control annuity case from the specification
- differentiated repayment
- early repayment with reduced payment
- early repayment with reduced term
- mortgage helper calculations

## Notes

- The calculator uses the nominal annual rate for the payment schedule.
- `ГЭСВ` is informational and is not used in the amortization math.
- The result is approximate. Real bank schedules can differ because of day-count rules, commissions, insurance, issue dates, and contract details.
