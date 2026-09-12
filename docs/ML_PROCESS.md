# PayLens ML Process

Status: **Prepared company history validated; Logistic Regression baseline trained.**

The process accepts the data-owner's prepared canonical CSV, builds temporal splits, and trains a binary Logistic Regression model to predict whether the company's next valid reporting period will show high payment-delay behaviour.

## Open contract divergence

`preprocess/build_training_data.py` defines its own eight-feature `MODEL_FEATURES` that drops `pct_paid_within_term` and `payment_term_gap` and adds `estimated_avg_payment_time_days`. The ML side still uses the nine locked features below, because measurement on identical temporal splits showed the two sets perform the same (test ROC-AUC 0.9320 locked vs 0.9318 the eight-feature set vs 0.9344 for their union), so there is no accuracy reason to pay the cost of re-cutting the contract.

`preprocess/training_data.csv` follows the eight-feature set and therefore no longer satisfies this contract. `preprocess/company_history.csv` contains both sets and is the input used here. This divergence needs a team decision.

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
INPUT_FILE = "preprocess/company_history.csv"
```

The model is binary Logistic Regression. The UI may map its probability to `LOW`, `MODERATE`, `HIGH`, or `CRITICAL`; those are presentation bands, not training labels.

## Input contract

The validated input is `preprocess/company_history.csv`. It already contains the canonical model features and next-period label. The source workbook mapping is owned by the data pipeline and is not repeated in the ML training step.

The prepared CSV must contain:
abn
entity_name
period_start
period_end
industry_division
payment_band_has_data
estimated_avg_payment_time_days
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
```

The prepared CSV stores payment percentages on a `0–100` scale. Therefore the
locked canonical threshold `0.20` is validated as `20` in this input file:
`high_payment_delay = 1` exactly when `next_period_pct_paid_over_60 >= 20`.
`industry_percentile` is already on a `0–1` scale and is not rescaled.
```

One row represents one company report. Repeated company-period observations are treated as revisions; when `report_submitted_date` exists, the latest submitted revision is kept.

Two row types are excluded at load time. Rows where `payment_band_has_data` is false carry no payment behaviour at all, so an imputed version of them would be an invented company. Rows with no `high_payment_delay` are each company's most recent period, which has no next-period outcome yet; they stay in the file because the UI needs them for the current profile, but they are not training examples.

`payment_trend` and `payment_volatility` are absent for a company's first period. These rows are kept: the imputer fills them with the training median and `add_indicator=True` records that they were missing, which retains 9,211 rows that would otherwise be dropped.

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

## Baseline results and how to read them

Current baseline, reproduced from `preprocess/company_history.csv` and recorded
in `reports/model_metrics.json`:

| Split | Rows | Positive | Negative | ROC-AUC | F1 | Precision | Recall |
|---|---|---|---|---|---|---|---|
| train | 28,188 | 3,257 | 24,931 | 0.9151 | 0.5994 | 0.4669 | 0.8367 |
| validation | 8,065 | 811 | 7,254 | 0.9243 | 0.5753 | 0.4317 | 0.8619 |
| test | 7,775 | 775 | 7,000 | 0.9250 | 0.5958 | 0.4597 | 0.8465 |

Period coverage: train `2020-12-28` to `2023-01-31`, validation `2023-02-01` to
`2023-10-27`, test `2023-10-28` to `2024-06-02`. Classification threshold 0.5.

### What each number means

One row is one company in one reporting period. `Positive` counts the rows whose
next valid period shows `pct_paid_over_60 >= 20`, which is the event the model
predicts.

- **ROC-AUC** is ranking quality and is independent of the classification
  threshold. At `0.9250`, given one company that will pay late and one that will
  not, the model assigns the higher risk to the late payer about 92.5% of the
  time. 0.5 would be random.
- **Recall `0.8465`** means the model flags 84.7% of the companies that do go on
  to pay late, and misses the remaining 15%.
- **Precision `0.4597`** means 46.0% of the companies the model flags actually
  pay late; the other 54% are false alarms.
- **F1 `0.5958`** is the harmonic mean of precision and recall, reported as a
  single balanced figure.

### Why precision is deliberately low

The positive class is roughly 10-11% of rows in every split. The model is
trained with `class_weight="balanced"`, which up-weights that minority class,
and is scored at a 0.5 threshold. The result is a model that prefers a false
alarm over a miss.

That trade-off matches the product decision PayLens supports: the cost of
accepting a contract from a customer who pays 60+ days late is far higher than
the cost of one unnecessary round of diligence. Teams that want fewer false
alarms should raise `classification_threshold` above 0.5, which increases
precision, decreases recall, and leaves ROC-AUC unchanged. Do not tune that
threshold on the test split.

### Evidence against overfitting

ROC-AUC across train, validation, and test is `0.9151`, `0.9243`, and `0.9250`.
Unseen later periods score no worse than the training periods, so the nine
features are not memorising the training set. The positive-class share is also
stable across the three splits, which indicates the chronological split did not
distort the label distribution.

These are baseline results on government payment-times reporting, not a
validated commercial credit score.

## Run

Install the ML dependencies:

```bash
pip install -r requirements.txt
```

Train from the validated prepared CSV and save the artifact:

```bash
python -m src.ml_process preprocess/company_history.csv /tmp/training_rows.csv \
    --artifact models/payment_risk.joblib
```

The command reports class balance and metrics for the chronological train,
validation, and test splits. The current baseline is recorded in
`reports/model_metrics.json`.

See **Baseline results and how to read them** above for the current figures
and their interpretation.

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

The company history supplies `avg_days_to_pay` per reporting period from
`estimated_avg_payment_time_days`. This is the data owner's band-midpoint
estimate, not an exact invoice-level average, because the government source
publishes payment-time ranges rather than individual invoice times. It should
be described as an estimated average payment time wherever it is shown.

Inference uses each company's most recent reported period, including the
period that has no next-period label yet. That row is exactly the one the
product needs to score and is not available in `training_data.csv`.

The generated CSV is a training intermediate, not source data. Do not run this against invented or synthetic production data. Do not commit generated training outputs or model artifacts until the target class balance and temporal evaluation have been reviewed.
