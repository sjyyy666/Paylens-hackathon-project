# PayLens ML Process

Status: **Prepared training data validated; Logistic Regression baseline trained.**

The process is not currently connected to the PayLens UI. It accepts the data-owner's prepared canonical CSV, builds temporal splits, and trains a binary Logistic Regression model to predict whether the company's next valid reporting period will show high payment-delay behaviour.

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

The preferred validated input is `preprocess/training_data.csv`. It already contains the canonical model features and next-period label. The source workbook mapping is owned by the data pipeline and is not repeated in the ML training step.

The prepared CSV must contain:
abn
period_end
pct_paid_30
pct_paid_31_60
pct_paid_over_60
pct_paid_within_term
payment_trend
payment_volatility
industry_percentile
num_reporting_periods
payment_term_gap
next_period_pct_paid_over_60
high_payment_delay
industry_division
```

The prepared CSV stores payment percentages on a `0–100` scale. Therefore the
locked canonical threshold `0.20` is validated as `20` in this input file:
`high_payment_delay = 1` exactly when `next_period_pct_paid_over_60 >= 20`.
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

Install the ML dependencies:

```bash
pip install -r requirements.txt
```

Train from the validated prepared CSV and save the artifact:

```bash
python -m src.ml_process preprocess/training_data.csv /tmp/training_rows.csv \
    --artifact models/payment_risk.joblib
```

The command reports class balance and metrics for the chronological train,
validation, and test splits. The current baseline is recorded in
`reports/model_metrics.json`.

For the current data, the test split has ROC-AUC `0.9211`, F1 `0.5982`,
precision `0.4670`, and recall `0.8319`, with 791 positive and 7,300 negative
rows. These are baseline results, not a validated commercial credit score.

The older workbook-to-canonical preparation path remains available only after
the data owner confirms its source-column mapping:

```bash
python -m src.ml_process preprocess/clean.xlsx /tmp/training_rows.csv
```

## Integration without UI changes

The prepared-data backend is opt-in and preserves the existing service facade:

```bash
PAYLENS_BACKEND=src.real_services streamlit run app.py
```

`src/real_services.py` reads the canonical prepared CSV, calls
`src/model_service.py`, and returns the existing `factors` output shape. The
default backend remains `src.mock_services`, so the demo remains available if
the real data or model artifact is unavailable.

The prepared CSV does not contain exact historical average payment-day values.
The real backend therefore returns period markers only for history and does not
invent `avg_days_to_pay` values. This is an explicit data limitation.

The generated CSV is a training intermediate, not source data. Do not run this against invented or synthetic production data. Do not commit generated training outputs or model artifacts until the target class balance and temporal evaluation have been reviewed.
