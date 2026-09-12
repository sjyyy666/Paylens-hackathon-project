# Payment Times Data — Preprocessing and Training Data

This folder contains the preprocessing and training-data pipeline for the Australian Government Payment Times Reports Register data used by PayLens.

The pipeline converts the original government Excel workbook into cleaned, analysis-ready data and then builds a structured training dataset for development of the PayLens payment-delay risk model.

## What This Module Does

The preprocessing pipeline converts the original government Excel workbook into a cleaner, analysis-ready workbook without throwing away potentially useful information.

The main preprocessing steps are:

* Read the original government workbook.
* Keep the relevant government report sheets.
* Convert long government column descriptions into stable `snake_case` column names.
* Remove Excel index columns and completely empty rows.
* Remove the repeated column-name row contained in the source workbook.
* Standardise ABNs as strings so identifiers are not accidentally converted to numbers.
* Parse known date fields consistently.
* Remove exact duplicate rows only.
* Keep different reporting periods and revised/historical reports.
* Add entity and reporting-period keys for downstream analysis.
* Create derived views, particularly `standard_latest` and `historical_for_analysis`.
* Create `data_dictionary` and `cleaning_summary` sheets.
* Build a separate training dataset for development of the payment-delay risk model.

## Files

```text
preprocessing/
├── data_process.py
├── build_training_data.py
├── clean.xlsx
├── training_data.xlsx
└── README.md
```

### `data_process.py`

Cleans and restructures the original Australian Government Payment Times dataset.

### `clean.xlsx`

The cleaned, analysis-ready workbook produced by `data_process.py`.

It preserves the relevant source information while also providing derived views for easier company and historical analysis.

### `build_training_data.py`

Uses the cleaned payment data to construct the dataset used for development of the PayLens payment-delay risk model.

### `training_data.xlsx`

The model-development dataset generated from the cleaned payment data.

It is kept separate from the larger cleaned workbook so model development can use a structured dataset while the complete cleaned data remains available for company lookup, historical analysis and other PayLens functionality.

The original `raw.xlsx` government dataset should normally remain outside the Git repository if it is too large. The raw source is never modified by the preprocessing script.

## How to Run

The data pipeline has two main stages.

### Step 1 — Preprocess the Government Data

Run:

```bash
python data_process.py raw.xlsx clean.xlsx
```

If the raw file is stored elsewhere, provide its path:

```bash
python data_process.py "path/to/raw.xlsx" clean.xlsx
```

The script prints progress while processing and finishes with the output path and the sheets created.

### Step 2 — Build the Training Data

Run the training-data script to generate the model-development dataset:

```bash
python build_training_data.py
```

This uses the cleaned payment data to produce `training_data.xlsx`.

Keeping these stages separate means the complete government dataset does not need to be cleaned again every time the model-development dataset is changed.

## Data Pipeline

The overall PayLens data pipeline is:

```text
Australian Government Payment Times Data
                    ↓
             data_process.py
                    ↓
               clean.xlsx
                    ↓
        build_training_data.py
                    ↓
           training_data.xlsx
                    ↓
       Payment-delay risk model
                    ↓
                 PayLens
```

`clean.xlsx` and `training_data.xlsx` have different purposes.

`clean.xlsx` is the broader analysis-ready source used for:

* Company identification
* Current payment behaviour
* Historical payment behaviour
* Payment trends
* Industry comparison
* Supporting reporting information

`training_data.xlsx` is specifically structured for development of the payment-delay risk model.

## Cleaned Dataset Structure

The cleaned workbook contains the original relevant source sheets as well as derived analysis sheets.

### 1. Standard Report

The Standard report contains current payment-time reporting information for reporting entities, including:

* Business identity (`entity_name`, `abn`, `acn_arbn`)
* Report type and reporting period
* Common payment terms
* Average and median payment time
* 80th and 95th percentile payment time
* Percentage of invoices paid within 30 days
* Percentage paid within 31–60 days
* Percentage paid after 60 days
* Percentage paid within the payment term
* Supply-chain-finance information
* Procurement-fee information
* Industry information
* Report comments and changes

This is one of the main sources for understanding a company's current observed payment behaviour.

### 2. `standard_latest`

`standard_latest` is a derived table containing the latest usable Standard report for each ABN.

The original Standard report sheet is preserved. This sheet is a convenient analysis view rather than a replacement for the source data.

A typical PayLens workflow is:

```text
Company name / ABN
        ↓
Find company in standard_latest
        ↓
Read latest payment behaviour
        ↓
Use historical_for_analysis
        ↓
Analyse payment trend
        ↓
Compare with industry
        ↓
Assess payment-delay risk
```

Repeated ABNs in the original data should not automatically be treated as duplicates. Different reporting periods and revised reports can contain meaningful information.

### 3. Historical Reports

The Historical Reports sheet contains payment reporting information across different reporting periods.

This includes:

* Standard payment terms
* Changes to standard terms
* Shortest and longest standard terms
* Invoice-count payment-time distributions
* Invoice-value payment-time distributions
* Invoice and payment practices
* Procurement fees
* Supply-chain-finance information
* Small-business procurement percentages
* Business-name and reporting changes
* Historical report and revision information
* Industry information

This data allows PayLens to examine how a company's payment behaviour has changed over time.

For example, a company whose payment time has recently increased may present a different payment-delay pattern from a company whose payment behaviour has remained stable.

### 4. `historical_for_analysis`

`historical_for_analysis` is a derived analysis view of the Historical Reports data, ordered by entity and reporting period.

It is designed to make it easier to construct historical features such as:

* Payment-time trend
* Improving or worsening payment behaviour
* Stability and volatility
* Changes in payment terms
* Changes in late-payment proportions

The original Historical Reports sheet remains available when the complete source information is required.

### 5. Records of Non-compliance

This sheet contains records relating to reported non-compliance, including the entity, ABN, type of non-compliance and related reporting information.

This may provide an additional regulatory signal.

However, non-compliance should not automatically determine a company's payment-delay risk by itself. It should be treated as supporting evidence.

### 6. External Administration Report

This contains information about external administration appointments associated with reporting entities, including appointment type, administrator firm and appointment date.

This may provide additional context or a potential financial-distress signal.

It is not required to be a primary feature of the PayLens payment-delay risk assessment.

### 7. Has Nominee Report

This contains information about reporting nominees, including nominee names and identifying information.

This is primarily structural and reporting information rather than a core payment-delay risk feature.

### 8. AASB8 Report

This contains supplementary reporting information associated with AASB 8, including payment metrics and operating-segment information where available.

It may support more detailed analysis of complex organisations but is not required for the first PayLens MVP.

### 9. No SB Procurement Report

This contains reports associated with entities that do not have the relevant small-business procurement reporting activity.

This is mainly a context and data-availability signal.

It should not automatically be interpreted as evidence of high payment-delay risk.

### 10. Applications

This contains accepted applications associated with reporting obligations, including extensions, modified reporting arrangements, volunteering or subsidiary entities, nominees and exempt entities where applicable.

This information may help explain reporting status and exceptions but is secondary to actual payment behaviour for the MVP.

### 11. Notices

This contains accepted regulatory notices relating to reporting entities.

These may provide additional context but should be interpreted alongside actual payment behaviour.

### 12. `data_dictionary`

The `data_dictionary` sheet provides a machine-readable summary of the columns contained in the cleaned and derived sheets.

It includes:

* Sheet name
* Column name
* Data type
* Non-null count
* Null percentage
* Number of unique values

This helps developers and AI systems understand what information is actually available without guessing the dataset structure.

### 13. `cleaning_summary`

The `cleaning_summary` provides a data-quality and preprocessing audit trail.

For each source sheet, it records information such as:

* Number of rows before cleaning
* Number of rows after cleaning
* Number of empty rows removed
* Number of exact duplicate rows removed

## Training Dataset

`training_data.xlsx` is derived from the cleaned Australian Government Payment Times data and is intended for development of the PayLens payment-delay risk model.

It is kept separate from `clean.xlsx`.

The cleaned workbook remains the broader source for customer search, current payment information and historical analysis, while the training dataset provides a structured input for model development and evaluation.

The creation of a training dataset does **not** mean that the underlying government data contains a direct default or bankruptcy label.

The model should therefore be developed and described as estimating **payment-delay risk based on observed payment behaviour**, rather than predicting bankruptcy, insolvency or credit default.

## Key Payment-Risk Features

Some of the most useful current-period variables available in the cleaned data include:

| Column                         | Meaning                                         | Potential Risk Use                      |
| ------------------------------ | ----------------------------------------------- | --------------------------------------- |
| `avg_payment_time_days`        | Average number of days taken to pay             | Core payment-speed signal               |
| `median_payment_time_days`     | Median payment time                             | Typical payment behaviour               |
| `p80_payment_time_days`        | Payment time by which 80% of payments were made | Captures slower payment tail            |
| `p95_payment_time_days`        | Payment time by which 95% of payments were made | Captures extreme late-payment behaviour |
| `pct_invoices_0_30_days`       | Percentage paid within 30 days                  | Payment-speed signal                    |
| `pct_invoices_31_60_days`      | Percentage paid within 31–60 days               | Delayed-payment signal                  |
| `pct_invoices_60_plus_days`    | Percentage paid after 60 days                   | Strong late-payment signal              |
| `pct_paid_within_payment_term` | Percentage paid within the stated payment term  | Payment-performance signal              |
| `common_payment_term_days`     | Most common payment term                        | Contractual timing context              |
| `standard_vs_common_term`      | Relationship between standard and common terms  | Payment-terms context                   |
| `industry_division`            | Main industry                                   | Industry benchmarking                   |
| `period_end`                   | End of reporting period                         | Recency and trend analysis              |

Historical variables can also be used to construct trend and stability features.

## Important Interpretation Rules

### 1. ABN Is the Main Entity Identifier

Use `abn` or `entity_key` to identify a company across reports whenever possible.

Company names can change, so company name alone should not be used as the entity key when an ABN is available.

### 2. Do Not Treat Repeated ABNs as Duplicates

The same ABN may legitimately appear in multiple reporting periods or revised reports.

Only exact duplicate rows should be automatically removed.

### 3. `standard_latest` Does Not Replace Historical Data

Use:

```text
standard_latest
→ latest/current payment assessment

historical_for_analysis
→ payment behaviour over time

Standard Report / Historical Reports
→ full source information
```

### 4. This Is Not a Default-Prediction Dataset

The Australian Government Payment Times data records observed payment behaviour.

It does not provide a direct target variable showing that a company defaulted on a contract.

PayLens should therefore not make unsupported statements such as:

> "This company has a 73% probability of default."

The product instead focuses on **payment-delay risk** and the potential cash-flow exposure created for a small-business supplier.

## Recommended PayLens Analysis Workflow

For a prospective customer:

1. Identify the entity using ABN where possible.
2. Retrieve the latest record from `standard_latest`.
3. Examine average and median payment times.
4. Examine P80 and P95 payment times.
5. Examine the proportions paid within 30 days, 31–60 days and after 60 days.
6. Compare actual payment behaviour with the stated or common payment term.
7. Compare the company with its industry where an appropriate benchmark is available.
8. Use `historical_for_analysis` to determine whether payment behaviour is improving, worsening or stable.
9. Optionally examine supporting regulatory information.
10. Combine the available evidence into an explainable payment-delay risk assessment.
11. Combine this customer assessment with the small business's proposed contract to calculate contract-specific exposure.
12. Recommend practical changes to the contract structure where supported by the calculations.

## Role in PayLens

This preprocessing module forms the data foundation of PayLens.

```text
Government Payment Data
        ↓
Data Cleaning
        ↓
Historical + Current Analysis
        ↓
Training Data
        ↓
Payment-Delay Risk
        ↓
Contract Exposure
        ↓
Deal Restructuring
        ↓
PayLens Recommendation
```

The preprocessing layer should remain separate from the website and model logic so changes to the source data do not require redesigning the PayLens user interface.

## Product Boundaries

PayLens uses historical payment behaviour as evidence for payment-delay risk.

The dataset does **not** directly support claims about:

* Probability of bankruptcy
* Probability of insolvency
* Probability of credit default
* Exact future payment dates
* Whether a specific invoice will definitely be late
* Whether a particular contract will definitely be paid

PayLens is designed as a **pre-contract decision-support tool for small businesses**, not a validated commercial credit-rating system.
