PayLens — Processing Pipeline

This folder contains the data-processing pipeline for PayLens.

The pipeline converts the cleaned Australian Government Payment Times data into:

A model-training dataset for the payment-delay ML Risk Engine.

A company-history dataset for company lookup, historical analysis, and application use.

The processing pipeline is separate from the ML model itself, the Contract Model, and the frontend application.

Final Outputs

The training-data builder generates four final files:

preprocess/
├── training_data.csv
├── training_data.xlsx
├── company_history.csv
└── company_history.xlsx

1. training_data.csv

CSV version of the supervised ML training dataset.

It contains observations with a valid next-period target and includes:

Company identifiers.

Current reporting period.

Industry information.

Standard payment terms.

Payment-data quality indicators.

The eight initial model features.

Next-period audit fields.

The binary target high_payment_delay.

This file is intended for use by the ML training pipeline.

2. training_data.xlsx

Excel version of training_data.csv.

It contains the same training records and columns, but is easier to inspect manually during development, debugging, and data-quality review.

3. company_history.csv

CSV version of the company-history dataset.

It contains the processed historical observations for companies, including derived payment features and historical indicators.

This file is intended to support:

Company lookup.

Historical payment-behaviour analysis.

Trend and volatility analysis.

Industry comparison.

Application-level explanations.

Future feature preparation.

4. company_history.xlsx

Excel version of company_history.csv.

It contains the same company-history information in a format that is convenient for manual inspection and presentation.

Input

The training-data builder reads:

preprocess/clean.xlsx

Specifically, it uses the following worksheet:

historical_for_analysis

The original raw government workbook is not read directly by the training-data builder. The data must first be processed into clean.xlsx.

Overall Pipeline

Raw Australian Government Payment Times Data
                    │
                    ▼
             Data cleaning
                    │
                    ▼
                clean.xlsx
                    │
                    ▼
          historical_for_analysis
                    │
                    ▼
       build_training_data.py
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   training_data.csv   company_history.csv
   training_data.xlsx  company_history.xlsx
          │                   │
          ▼                   ▼
    ML model training   Company lookup,
    and evaluation      historical analysis,
                        explanations

Main Scripts

data_process.py

This script processes the original government data and creates the cleaned workbook:

clean.xlsx

Its responsibilities include:

Loading the source government workbook.

Cleaning column names and values.

Standardising identifiers.

Parsing dates.

Removing invalid or unusable records.

Handling empty rows and duplicate records.

Creating the historical_for_analysis worksheet.

Preserving the information required for downstream analysis.

build_training_data.py

This script reads:

clean.xlsx

from the historical_for_analysis worksheet and generates the four final output files:

training_data.csv
training_data.xlsx
company_history.csv
company_history.xlsx

Its responsibilities include:

Validating the required source columns.

Cleaning ABNs, company names, dates, payment terms, and percentages.

Handling duplicate company-period records and report revisions.

Detecting missing or invalid payment-band data.

Building payment-related features.

Building historical features.

Building the next-period supervised-learning target.

Running data-quality and leakage checks.

Writing the final CSV and Excel outputs.

How to Run

Run the training-data builder from the preprocess directory:

python build_training_data.py

The script expects:

preprocess/clean.xlsx

to exist.

After successful execution, the following files should be created or updated:

preprocess/training_data.csv
preprocess/training_data.xlsx
preprocess/company_history.csv
preprocess/company_history.xlsx

The script prints information about:

Input rows and columns.

Missing required columns.

Payment-band data quality.

Duplicate company-period records.

Rows with valid next-period targets.

Leakage and data-quality checks.

Final output paths.

Initial ML Feature Schema

The current initial model uses eight features:

MODEL_FEATURES = [
    "pct_paid_30",
    "pct_paid_31_60",
    "pct_paid_over_60",
    "estimated_avg_payment_time_days",
    "payment_trend",
    "payment_volatility",
    "industry_percentile",
    "num_reporting_periods",
]

Feature descriptions

Feature

Description

pct_paid_30

Percentage of invoices paid within 30 days. This combines the within 20 days and 21–30 days bands.

pct_paid_31_60

Percentage of invoices paid between 31 and 60 days.

pct_paid_over_60

Percentage of invoices paid after 60 days. This combines the 61–90, 91–120, and more than 120 days bands.

estimated_avg_payment_time_days

Estimated average payment time calculated using the midpoint of each payment-time band.

payment_trend

Change in the percentage paid after 60 days compared with the previous observed period for the same company. Positive values indicate more payment delay.

payment_volatility

Expanding standard deviation of observed pct_paid_over_60 values for the company.

industry_percentile

Relative position of the company’s pct_paid_over_60 value among companies in the same industry and reporting period.

num_reporting_periods

Number of observed reporting periods for the company up to the current row.

Estimated payment time

The estimated average payment time uses the following midpoints:

Payment-time band

Midpoint used

Within 20 days

10.0

21–30 days

25.5

31–60 days

45.5

61–90 days

75.5

91–120 days

105.5

More than 120 days

135.0

The value 135.0 for payments taking more than 120 days is an MVP approximation. Therefore, the feature is named:

estimated_avg_payment_time_days

It should not be interpreted as an exact observed average payment time.

Payment-Time Source Columns

The six source payment-time bands are:

extra_percentage_of_number_invoices_paid_within_20_days
extra_percentage_of_number_invoices_paid_between_21_and_30_days
extra_percentage_of_number_invoices_paid_between_31_and_60_days
extra_percentage_of_number_invoices_paid_between_61_and_90_days
extra_percentage_of_number_invoices_paid_between_91_and_120_days
extra_percentage_of_number_invoices_paid_in_more_than_120_days

The processing script converts these values into numeric percentages on a 0–100 scale.

Values such as the following are supported:

25
25.0
"25"
"25%"

Values outside the range 0–100 are treated as invalid.

Important Data-Quality Rules

1. All-zero payment bands mean missing data

If all six payment-time bands are zero, the record is treated as having missing payment information.

It is not interpreted as:

0% payment delay

This distinction is important because zero-filled records may represent unavailable or unreported payment information.

2. Payment-band totals above 100% are invalid

The six payment-time bands should normally add up to approximately 100%.

A small tolerance of 0.5 is allowed for rounding differences.

If the total is greater than:

100.5%

the payment observation is treated as invalid.

The script does not silently clip the values to 100%. Instead, the derived payment features are set to missing.

3. Missing payment information is not converted to zero

Missing or invalid payment observations are represented using missing values rather than artificial zeros.

This prevents the model from interpreting unavailable payment information as good payment performance.

4. ABNs are treated as identifiers

ABNs are converted to strings and cleaned of accidental .0 suffixes caused by spreadsheet formatting.

ABNs should not be treated as numeric measurements.

Duplicate and Revision Handling

The processing script keeps one record for each:

ABN + period_end

When multiple records exist for the same company and reporting period, the script uses a deterministic rule:

Prefer the latest revised report date.

If no revised report date exists, use the original report date.

If dates are tied or unavailable, use the original row order.

This is an MVP revision-handling rule.

Repeated ABNs across different reporting periods are not automatically duplicates. They are necessary for constructing historical payment features.

Historical Features

The script builds historical features after sorting records by:

abn
period_end

payment_trend

The trend is calculated as:

current pct_paid_over_60
-
previous pct_paid_over_60

Interpretation:

Positive value: a larger proportion of payments took more than 60 days.

Negative value: a smaller proportion of payments took more than 60 days.

Missing value: either the current or previous payment observation is unavailable.

payment_volatility

This is the expanding standard deviation of the company’s observed:

pct_paid_over_60

values.

Missing payment information is not treated as zero.

num_reporting_periods

This counts the company’s observed reporting periods up to the current row.

industry_percentile

The company is compared with other companies sharing:

period_end
industry_division

The percentile is based on:

pct_paid_over_60

The calculation is designed not to use future reporting periods.

Optional Analysis Features

The processing script also calculates features that are useful for analysis or future modelling but are not part of the initial eight-feature model contract.

pct_paid_within_term

This estimates the percentage of invoices paid within the company’s standard payment term.

It is retained for analysis and history.

It is not included in the current MODEL_FEATURES list.

payment_term_gap

This is calculated as:

estimated_avg_payment_time_days
-
extra_standard_payment_terms

It provides an estimate of how far observed payment behaviour differs from the stated standard payment term.

It is currently an analysis-oriented feature rather than one of the eight initial model features.

Target Construction

The ML target is based on the next observed reporting period for the same company.

For a current observation at period t, the script finds the next available observation at period t+1 and reads:

next_period_pct_paid_over_60

The binary target is:

high_payment_delay

The target is defined as:

1 = next-period pct_paid_over_60 >= 20%
0 = next-period pct_paid_over_60 < 20%

The threshold is:

HIGH_DELAY_THRESHOLD = 20.0

This is a hackathon modelling threshold. It is not an official Australian Government classification.

Rows without a valid next-period observation cannot produce a supervised target and are excluded from the training dataset.

Difference Between the Two Main Outputs

training_data

training_data.csv and training_data.xlsx are designed for supervised machine-learning development.

They contain:

Current-period input features.

Company and industry identifiers.

Data-quality fields.

Next-period target information.

The binary target high_payment_delay.

Only rows with a valid next-period target are included.

company_history

company_history.csv and company_history.xlsx are designed for broader historical use.

They preserve processed company-period observations and derived features, including rows that may not have a next-period target.

They can be used for:

Company search.

Historical payment charts.

Payment trend explanations.

Volatility analysis.

Industry comparisons.

Supporting the PayLens application.

Future model feature construction.

Relationship to the ML Risk Engine

The processing pipeline prepares data for the Payment-delay ML Risk Engine.

The ML Risk Engine estimates:

the risk that a company will experience high payment delay in the next observed reporting period.

It does not directly predict:

Bankruptcy.

Insolvency.

Default.

Profitability.

Cash reserves.

Contract exposure.

Exact future payment dates.

Whether a particular invoice will definitely be late.

The processing pipeline only prepares the data. The trained ML model is responsible for producing the payment-delay risk estimate.

Relationship to the Contract Model

The Contract Model is a separate deterministic risk engine.

The processing pipeline and ML Risk Engine focus on company payment behaviour.

The Contract Model focuses on a proposed contract and considers inputs such as:

Customer payment probability.

Contract value.

Cash reserve.

Monthly operating cost.

Upfront payment percentage.

Delivery time.

Payment terms.

The ML output can be used to estimate customer payment probability, but the Contract Model then evaluates the effect of the proposed contract on the supplier’s cash flow and exposure.

Therefore:

Processing
    → prepares payment-history data

ML Risk Engine
    → estimates next-period payment-delay risk

Contract Model
    → evaluates contract-specific financial exposure

PayLens application
    → presents the combined decision-support result

Data Leakage Considerations

The training-data builder includes checks intended to reduce obvious leakage risks.

Important rules:

Historical records must be ordered by company and reporting period.

Current-period features must not use future reporting periods.

The next-period payment percentage is used only to construct the target.

Target fields must not be included as model input features.

Missing payment information must not be converted into zero.

Industry comparisons should be restricted to the relevant reporting period and industry.

Revised reports should be handled consistently.

The temporal train/validation/test split must be performed after the training data has been constructed.

The presence of a leakage check does not guarantee that every possible source of leakage has been eliminated. The modelling pipeline must still review the final feature matrix and split strategy.

Product Interpretation

PayLens is a payment-delay decision-support tool for small businesses.

The source data describes observed payment behaviour. It does not directly establish:

A company’s probability of bankruptcy.

A company’s probability of insolvency.

A company’s probability of default.

A guaranteed future payment date.

The exact probability that a particular contract will be paid late.

The appropriate interpretation is:

PayLens uses historical payment behaviour to estimate payment-delay risk and help small businesses assess potential contract cash-flow exposure.