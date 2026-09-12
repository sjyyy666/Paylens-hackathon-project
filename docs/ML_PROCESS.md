# PayLens ML Process

Status: **Pipeline specification and implementation ready; validated training data is still pending.**

The process is not currently connected to the PayLens UI and must not be used to claim model performance until the data owner confirms the input schema, class balance, and temporal evaluation. It reads the agreed cleaned workbook input when that data is available, builds one training observation per company and reporting period, and predicts whether the company's next valid reporting period will show high payment-delay behaviour.

## Locked parameters

These names and values are part of the ML contract and must not be changed without an explicit team decision:

```python
MODEL_FEATURES = [
    "pct_paid_30",
    "pct_paid_31_60",
    "pct_paid_over_60",
    "pct_paid_within_term",
    "payment_trend",
    "payment_volatility",
    "industry_percentile",
    "num_reporting_periods",
    "payment_term_gap",
]

TARGET_COLUMN = "high_payment_delay"
NEXT_OUTCOME_COLUMN = "next_period_pct_paid_over_60"
TARGET_THRESHOLD = 0.20
INPUT_SHEET = "historical_for_analysis"
```

The model is binary Logistic Regression. The UI may map its probability to `LOW`, `MODERATE`, `HIGH`, or `CRITICAL`; those are presentation bands, not training labels.

## Input contract

When validated data is available, input is the cleaned workbook created by `preprocess/data_process.py`, using the `historical_for_analysis` sheet. The required source columns are:

```text
abn
period_end
pct_invoices_0_30_days
pct_invoices_31_60_days
pct_invoices_60_plus_days
pct_paid_within_payment_term
avg_payment_time_days
common_payment_term_days
industry_division
```

One row represents one company report. Repeated company-period observations are treated as revisions; when `report_submitted_date` exists, the latest submitted revision is kept.

## Feature definitions

| Model feature | Source/derivation |
|---|---|
| `pct_paid_30` | `pct_invoices_0_30_days`, normalized to 0-1 |
| `pct_paid_31_60` | `pct_invoices_31_60_days`, normalized to 0-1 |
| `pct_paid_over_60` | `pct_invoices_60_plus_days`, normalized to 0-1 |
| `pct_paid_within_term` | `pct_paid_within_payment_term`, normalized to 0-1 |
| `payment_trend` | current `avg_payment_time_days` minus the previous valid period for the same ABN; first period is 0 |
| `payment_volatility` | population standard deviation of current and prior average payment days for the same ABN; first period is 0 |
| `industry_percentile` | percentile rank of current average payment days within the same reporting period and industry |
| `num_reporting_periods` | cumulative count of valid periods for the same ABN through period `t` |
| `payment_term_gap` | current average payment days minus current common payment term days |

All features are calculated from period `t` or earlier. Contract value, cash reserve, monthly cost, upfront payment, and payment terms are excluded.

## Label construction

For each company:

1. Sort rows by `abn` and `period_end`.
2. Build features from information available at or before period `t`.
3. Find the next valid reporting period `t+1`.
4. Set `next_period_pct_paid_over_60` to `pct_invoices_60_plus_days` at `t+1`.
5. Set `high_payment_delay = 1` when that value is greater than or equal to `0.20`; otherwise set it to `0`.
6. Drop the final observation for each company because it has no next-period outcome.

No value from `t+1` or later is included in the model feature columns. The next-period value exists in the output only as an audit/label source.

## Temporal validation

The process splits unique reporting periods chronologically:

```text
oldest 60% -> train
next 20% -> validation
latest 20% -> test
```

Splits are made by period, never by random rows. The process requires at least three unique reporting periods. Class balance must be reported separately for each split. ROC-AUC is not valid for a split containing only one class.

## Run

Install the ML dependencies when the data is ready:

```bash
pip install -r requirements.txt
```

Prepare training rows after the input contract has been confirmed:

```bash
python -m src.ml_process preprocess/clean.xlsx data/training_rows.csv
```

Prepare rows and save the Logistic Regression artifact:

```bash
python -m src.ml_process preprocess/clean.xlsx data/training_rows.csv --artifact models/payment_risk.joblib
```

The generated CSV is a training intermediate, not source data. Do not run this against invented or synthetic production data. Do not commit generated training outputs or model artifacts until the target class balance and temporal evaluation have been reviewed.
