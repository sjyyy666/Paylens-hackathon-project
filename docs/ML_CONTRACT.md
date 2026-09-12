PayLens ML Data Contract

Status: Draft — aligned with the current ML pipeline and Contract Model

This document defines the interface between the data pipeline, the ML Risk
Engine, the Contract Model, and the application UI.

The system separates two different types of risk:

Customer payment-delay risk, estimated by the ML Risk Engine.

Contract-related cash-flow risk, calculated by the Contract Model.

1. Product boundary

The ML Risk Engine estimates the probability that a prospective customer
will experience high payment-delay behaviour in the next valid reporting
period, using historical customer payment data.

The ML Risk Engine does not estimate:

Bankruptcy

Insolvency

Default

Profitability

Company cash reserves

Contract exposure

Contract affordability

Contract profitability

The following inputs belong exclusively to the Contract Model:

CONTRACT_MODEL_INPUTS = [
    "contract_value",
    "cash_reserve",
    "monthly_cost",
    "upfront_pct",
    "delivery_time_days",
    "payment_terms_days",
]

The ML model's payment-risk output is passed into the Contract Model.
These two risk calculations must remain separate.

2. System responsibilities

ML Risk Engine

The ML Risk Engine is responsible for:

Reading the prepared company-history dataset

Creating or consuming historical payment-behaviour features

Training the binary Logistic Regression model

Predicting next-period high payment-delay risk

Returning a probability, risk level, explanatory factors, confidence,
and model identifier

Contract Model

The Contract Model is responsible for:

Receiving the customer's payment probability from the ML layer

Combining that probability with contract and business cash-flow inputs

Calculating contract exposure and waiting-period risk

Calculating the overall contract risk score

Assigning LOW, MODERATE, HIGH, or CRITICAL

Recommending an upfront payment percentage

Generating contract negotiation recommendations

The Contract Model is deterministic and rule-based. It does not train an
ML model.

3. Current ML feature schema

The current ML pipeline uses the following nine canonical features:

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

These are the currently locked feature names used by the ML process.

The following alternative eight-feature preprocessing schema exists in the
repository but is not the current locked ML schema:

ALTERNATIVE_FEATURE = "estimated_avg_payment_time_days"

The team must resolve the remaining preprocessing divergence before
treating the data contract as final.

4. Features that must not enter the ML model

The following fields must not be used as ML training features:

CONTRACT_MODEL_INPUTS = [
    "contract_value",
    "cash_reserve",
    "monthly_cost",
    "upfront_pct",
    "delivery_time_days",
    "payment_terms_days",
]

The following fields are also excluded from the ML feature matrix:

Company identifiers such as abn

Company names

Raw reporting-period identifiers

Manually entered risk labels

Future-period values

Post-outcome information

Any information unavailable at the end of period t

The company identifier and reporting period may be used for grouping,
sorting, joining, and temporal splitting, but not as numeric predictors.

5. Required data-owner handoff

The data owner must provide:

The processed CSV or DataFrame and its file path

A data dictionary for every source column

The company identifier column

The reporting-period columns and ordering rule

The source columns for payment behaviour

Row count

Company count

Reporting-period coverage

Missing-value summary

Duplicate-row summary

Known future or post-period fields

Any known data-quality limitations

The current prepared input file is:

preprocess/company_history.csv

The prepared dataset is expected to contain the canonical features and the
next-period target information.

6. Training row definition

One row represents one company report for one reporting period.

For a row at period t:

Features are calculated using information available at or before t.

The target is based on the same company's next valid reporting period
t+1.

Rows without a next valid period do not have a training label.

The latest period for each company may still be used for inference.

Repeated company-period observations are treated as revisions. When
report_submitted_date is available, the latest submitted revision is kept.

Rows with no payment-behaviour data are excluded from training because
imputing them would create an artificial company history.

7. Current feature definitions

Feature

Definition

pct_paid_30

Percentage of invoices paid within 30 days, normalized to 0–1

pct_paid_31_60

Percentage of invoices paid within 31–60 days, normalized to 0–1

pct_paid_over_60

Percentage of invoices paid after more than 60 days, normalized to 0–1

pct_paid_within_term

Percentage of payments made within the applicable payment term, normalized to 0–1

payment_trend

Current average payment time minus the previous valid period's average payment time

payment_volatility

Population standard deviation of current and prior average payment days

industry_percentile

Percentile rank of current average payment days within the same reporting period and industry

num_reporting_periods

Cumulative count of valid reporting periods for the same company

payment_term_gap

Current average payment days minus the current common payment-term days

All model features must be available no later than period t.

Contract value, cash reserves, monthly operating costs, upfront payment,
delivery time, and payment terms are not ML features.

8. Target definition

The current target is:

TARGET_COLUMN = "high_payment_delay"
NEXT_OUTCOME_COLUMN = "next_period_pct_paid_over_60"
TARGET_THRESHOLD = 0.20

The prepared CSV stores payment percentages on a 0–100 scale. Therefore,
the target is constructed as:

high_payment_delay = 1
when next_period_pct_paid_over_60 >= 20

Otherwise:

high_payment_delay = 0

The target represents high payment-delay behaviour in the next valid
reporting period. It does not represent bankruptcy, insolvency, or default.

9. Leakage audit checklist

Before training or reporting final results, record PASS or FAIL with
supporting evidence for each item:

Company identifiers are used only for grouping, joins, and display

Company identifiers are not numeric predictors

Reporting periods are parsed and sorted chronologically

Every feature is available no later than period t

The target is based only on period t+1

No future-period aggregates enter the feature matrix

No post-outcome fields are included

No Contract Model inputs enter the ML model

No duplicate company-period rows remain

Imputation is fitted on training data only

Encoding is fitted on training data only

Scaling is fitted on training data only, if required

Test periods occur after training periods

The target threshold is not selected using test labels

10. Temporal split

The current process uses chronological reporting-period splits:

Oldest 60% of periods -> training
Next 20% of periods   -> validation
Latest 20% of periods -> test

Splitting is performed by reporting period, not by random rows.

The test set must contain both positive and negative labels before ROC-AUC
is reported.

Always report:

Number of rows

Positive count

Negative count

ROC-AUC

Precision

Recall

F1-score

Classification threshold

11. ML model output contract

The ML adapter must return a UI-compatible object:

{
    "probability": 0.0,
    "level": "LOW",
    "factors": [
        {
            "text": "...",
            "tone": "negative",
        }
    ],
    "confidence": "standard",
    "model": "logistic-v1",
    "is_mock": False,
}

Output definitions

Field

Meaning

probability

Probability of the defined high payment-delay event, in [0, 1]

level

Presentation band: LOW, MODERATE, HIGH, or CRITICAL

factors

At most three human-readable explanatory factors

confidence

standard or limited

model

Model identifier

is_mock

True for mock or fallback results

The ML probability represents payment-delay risk, not payment-on-time
probability.

12. Interface with the Contract Model

The current Contract Model expects:

payment_probability

to mean the probability that the customer pays on time.

Therefore, if the ML model returns:

payment_delay_probability

the integration layer must convert it:

payment_probability = 1 - payment_delay_probability

Then call the Contract Model:

contract_result = contract_model.predict(
    payment_probability=payment_probability,
    contract_value=contract_value,
    cash_reserve=cash_reserve,
    monthly_cost=monthly_cost,
    upfront_pct=upfront_pct,
    delivery_time_days=delivery_time_days,
    payment_terms_days=payment_terms_days,
)

The Contract Model returns a separate contract-risk result:

{
    "risk_score": 0.0,
    "risk_level": "LOW",
    "metrics": {},
    "component_scores": {},
    "recommended_upfront_pct": 0.0,
    "recommendations": [],
}

The ML payment-delay probability and the Contract Model risk score must not
be treated as the same metric.

13. Fallback behaviour

If the trained ML model or required features are unavailable, the
application must remain usable.

The adapter may return a documented historical-risk fallback:

{
    "probability": 0.5,
    "level": "MODERATE",
    "factors": [
        {
            "text": "Historical payment-risk estimate is being used.",
            "tone": "neutral",
        }
    ],
    "confidence": "limited",
    "model": "historical-fallback-v1",
    "is_mock": True,
}

The fallback must not be presented as a trained model prediction.

14. Pending decisions

Resolve the eight-feature versus nine-feature preprocessing divergence

Confirm the final processed input file

Confirm the final source-column mapping

Confirm the company identifier

Confirm reporting-period ordering

Complete the leakage audit

Confirm the final target definition and threshold

Confirm class balance after the final preprocessing decision

Confirm train/validation/test periods

Record final baseline and trained-model metrics

Test ML-to-Contract-Model integration

Confirm the frontend displays the two risk measures separately