PayLens ML Process

Status: Prepared company history validated; Logistic Regression baseline trained.

This document describes the current data-preparation and training process
for the PayLens ML Risk Engine.

The process accepts the prepared company-history CSV, constructs temporal
training examples, and trains a binary Logistic Regression model to predict
whether the same company's next valid reporting period will show high
payment-delay behaviour.

1. Model purpose

The ML Risk Engine estimates customer payment-delay risk from historical
payment behaviour.

It does not estimate:

Contract exposure

Cash reserves

Monthly operating costs

Contract affordability

Profitability

Bankruptcy

Insolvency

Default

Those contract-related calculations are handled separately by the
Contract Model.

2. Current model configuration

The current model is binary Logistic Regression.

The locked feature schema is:

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

The current target configuration is:

TARGET_COLUMN = "high_payment_delay"
NEXT_OUTCOME_COLUMN = "next_period_pct_paid_over_60"
TARGET_THRESHOLD = 0.20
INPUT_FILE = "preprocess/company_history.csv"

The prepared CSV stores payment percentages on a 0–100 scale. Therefore,
the target is created using a threshold of 20 in the prepared CSV:

high_payment_delay = 1
when next_period_pct_paid_over_60 >= 20

The target is based on the next valid reporting period.

3. Input dataset

The current validated input file is:

preprocess/company_history.csv

The prepared CSV is expected to contain:

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

The source workbook-to-canonical mapping belongs to the data pipeline and is
not repeated in the model-training step.

4. Training-row definition

One row represents one company report for one reporting period.

For a row at period t:

Features are calculated from information available at or before t.

The next valid reporting period for the same company is identified.

The next period's pct_paid_over_60 value is used to construct the label.

The final observation for each company has no next-period outcome and is
not used as a labelled training row.

The latest observation may still be used for current UI inference.

Repeated company-period observations are treated as revisions. When
report_submitted_date exists, the latest submitted revision is retained.

Rows without payment-behaviour data are excluded from training because
imputing all their payment behaviour would create an artificial history.

5. Feature definitions

Feature

Source or derivation

pct_paid_30

Percentage of invoices paid within 30 days, normalized to 0–1

pct_paid_31_60

Percentage of invoices paid within 31–60 days, normalized to 0–1

pct_paid_over_60

Percentage of invoices paid after more than 60 days, normalized to 0–1

pct_paid_within_term

Percentage paid within the applicable payment term, normalized to 0–1

payment_trend

Current average payment time minus the previous valid period's average payment time

payment_volatility

Population standard deviation of current and prior average payment days

industry_percentile

Percentile rank of current average payment days within the same reporting period and industry

num_reporting_periods

Cumulative count of valid periods for the same company through period t

payment_term_gap

Current average payment days minus current common payment-term days

All features must be available no later than period t.

The following are not ML features:

contract_value
cash_reserve
monthly_cost
upfront_pct
delivery_time_days
payment_terms_days

6. Label construction

For each company:

Sort observations by company identifier and reporting period.

Build features from information available at or before period t.

Find the next valid reporting period t+1.

Read the next period's pct_paid_over_60.

Set high_payment_delay = 1 when the next-period value is at least 20
in the prepared CSV.

Set high_payment_delay = 0 otherwise.

Exclude the final observation for each company from labelled training.

No value from t+1 or later may enter the feature matrix.

The next-period value is retained only for label construction and auditing.

7. Temporal validation

The process uses chronological splits by unique reporting period:

Oldest 60% of periods -> training
Next 20% of periods   -> validation
Latest 20% of periods -> test

The split is performed by period, never by random rows.

The process requires at least three unique reporting periods.

For each split, report:

Number of rows

Positive labels

Negative labels

ROC-AUC, when both classes are present

Precision

Recall

F1-score

Classification threshold

8. Baseline results

The current baseline, recorded from the prepared company-history data, is:

Split

Rows

Positive

Negative

ROC-AUC

F1

Precision

Recall

Train

28,188

3,257

24,931

0.9151

0.5994

0.4669

0.8367

Validation

8,065

811

7,254

0.9243

0.5753

0.4317

0.8619

Test

7,775

775

7,000

0.9250

0.5958

0.4597

0.8465

Period coverage:

Train:      2020-12-28 to 2023-01-31
Validation:  2023-02-01 to 2023-10-27
Test:       2023-10-28 to 2024-06-02

The reported classification threshold is 0.5.

The ROC-AUC value is independent of the classification threshold. The
classification threshold affects precision, recall, and F1-score.

9. Interpreting the baseline

The positive class represents companies whose next valid reporting period
has pct_paid_over_60 >= 20.

The test metrics mean:

ROC-AUC 0.9250: strong ranking performance on the held-out later
periods; the model ranks a randomly selected positive case above a
randomly selected negative case approximately 92.5% of the time.

Recall 0.8465: approximately 84.7% of positive cases are detected at
the current classification threshold.

Precision 0.4597: approximately 46.0% of cases flagged positive are
actually positive.

F1 0.5958: a combined measure of precision and recall.

The positive class is approximately 10–11% of rows. The model uses
class_weight="balanced" and a classification threshold of 0.5, which
favours detecting risky cases over minimizing false alarms.

The threshold should not be tuned on the test set.

10. Preprocessing divergence

The repository contains an older or alternative preprocessing path that
uses an eight-feature schema and includes:

estimated_avg_payment_time_days

instead of the currently locked nine-feature schema.

The current ML contract and baseline results refer to the nine-feature
schema. The team must resolve the preprocessing divergence before
declaring the final training pipeline frozen.

Do not silently mix the eight-feature and nine-feature schemas.

11. Leakage audit

Before final training, confirm:

Company identifiers are used only for grouping and joins

Reporting periods are sorted chronologically

Features are available no later than period t

The target uses only period t+1

Future-derived aggregates are excluded

Contract Model inputs are excluded

Duplicate company-period revisions are handled

Imputation is fitted on training data only

Encoding is fitted on training data only

Test periods occur after training periods

The target threshold is not selected using test labels

12. Run the process

Install dependencies:

pip install -r requirements.txt

Train from the prepared company-history CSV:

python -m src.ml_process preprocess/company_history.csv /tmp/training_rows.csv \
    --artifact models/payment_risk.joblib

The command should report:

Data preparation status

Class balance

Chronological split information

Validation metrics

Test metrics

Saved model-artifact path

The older workbook path may be used only after the data-owner confirms
its source-column mapping:

python -m src.ml_process preprocess/clean.xlsx /tmp/training_rows.csv

13. Integration with the application

The UI should continue to use the service facade:

PAYLENS_BACKEND=src.real_services streamlit run app.py

The real-data backend should:

Read the prepared company-history data.

Obtain the latest valid company profile for inference.

Call src/model_service.py.

Return the existing UI-compatible payment-risk output.

Convert payment-delay probability into payment-on-time probability.

Pass that value to src.contract_model.py.

The conversion is:

payment_probability = 1 - payment_delay_probability

The Contract Model then receives the contract-specific inputs and produces
a separate contract-risk result.

The default backend may remain the mock backend so that the demo remains
usable when the real dataset or model artifact is unavailable.

14. Limitations

The current results are baseline results on historical government
payment-times reporting data.

They are not a validated commercial credit score.

The model predicts the defined next-period payment-delay event, not
bankruptcy, insolvency, profitability, or contract affordability.

The final feature schema, target definition, leakage audit, and temporal
evaluation must be reviewed before production use.