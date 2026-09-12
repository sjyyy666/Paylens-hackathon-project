import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# SETTINGS
# ============================================================

INPUT_FILE = Path(__file__).parent / "clean.xlsx"
OUTPUT_FILE = Path(__file__).parent / "training_data.xlsx"

# Your required model features
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

# Change this if your team chooses a different threshold.
# 20 means:
# high_payment_delay = 1 if next period has >= 20%
# of invoices paid after 60 days.
HIGH_PAYMENT_DELAY_THRESHOLD = 20.0


# ============================================================
# 1. LOAD THE CORRECT SHEET
# ============================================================

print("Reading clean.xlsx...")

df = pd.read_excel(
    INPUT_FILE,
    sheet_name="Standard report"
)

print(f"Original rows: {len(df)}")


# ============================================================
# 2. CLEAN IDENTIFIERS AND DATES
# ============================================================

# ABN identifies the company.
df["abn"] = (
    df["abn"]
    .astype("string")
    .str.strip()
)

# Convert dates properly.
df["period_start"] = pd.to_datetime(
    df["period_start"],
    errors="coerce"
)

df["period_end"] = pd.to_datetime(
    df["period_end"],
    errors="coerce"
)

df["report_submitted_date"] = pd.to_datetime(
    df["report_submitted_date"],
    errors="coerce"
)

# Cannot construct company-period observations without these.
df = df.dropna(
    subset=["abn", "period_end"]
).copy()


# ============================================================
# 3. DEAL WITH REVISED REPORTS
# ============================================================

# There can be more than one report for the same ABN and
# reporting period.
#
# We sort by submission date so that if there are revised
# versions, the latest submitted version is retained.

df = df.sort_values(
    [
        "abn",
        "period_end",
        "report_submitted_date",
    ]
)

df = df.drop_duplicates(
    subset=["abn", "period_end"],
    keep="last"
).copy()


# ============================================================
# 4. SORT COMPANY HISTORY
# ============================================================

df = df.sort_values(
    ["abn", "period_end"]
).reset_index(drop=True)

print(
    f"Rows after keeping one report per company-period: "
    f"{len(df)}"
)


# ============================================================
# 5. CONVERT REQUIRED RAW COLUMNS TO NUMERIC
# ============================================================

raw_numeric_columns = [
    "pct_invoices_0_30_days",
    "pct_invoices_31_60_days",
    "pct_invoices_60_plus_days",
    "pct_paid_within_payment_term",
    "avg_payment_time_days",
    "common_payment_term_days",
]

for column in raw_numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )


# ============================================================
# 6. CREATE THE FOUR DIRECT PAYMENT FEATURES
# ============================================================

df["pct_paid_30"] = (
    df["pct_invoices_0_30_days"]
)

df["pct_paid_31_60"] = (
    df["pct_invoices_31_60_days"]
)

df["pct_paid_over_60"] = (
    df["pct_invoices_60_plus_days"]
)

df["pct_paid_within_term"] = (
    df["pct_paid_within_payment_term"]
)


# ============================================================
# 7. PAYMENT TREND
# ============================================================

# Measures how the >60-day percentage changed relative
# to the company's previous reporting period.
#
# Positive = getting worse
# Negative = getting better
#
# Example:
#
# previous = 10%
# current  = 18%
#
# trend = 18 - 10 = +8

df["payment_trend"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .diff()
)

# First observation has no previous period.
df["payment_trend"] = (
    df["payment_trend"]
    .fillna(0)
)


# ============================================================
# 8. PAYMENT VOLATILITY
# ============================================================

# Standard deviation of the company's >60-day payment
# percentage using ONLY observations up to period t.
#
# expanding() is important:
#
# period 1 -> uses period 1
# period 2 -> uses periods 1-2
# period 3 -> uses periods 1-3
#
# It NEVER looks into the future.

df["payment_volatility"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .expanding()
    .std()
    .reset_index(level=0, drop=True)
)

# One observation cannot have a standard deviation.
df["payment_volatility"] = (
    df["payment_volatility"]
    .fillna(0)
)


# ============================================================
# 9. NUMBER OF REPORTING PERIODS
# ============================================================

# Number of periods available for the company up to
# and including period t.

df["num_reporting_periods"] = (
    df.groupby("abn")
    .cumcount()
    + 1
)


# ============================================================
# 10. PAYMENT TERM GAP
# ============================================================

# Actual average payment time minus common payment term.
#
# Example:
#
# average payment time = 47 days
# common payment term  = 30 days
#
# gap = +17 days
#
# Positive = paying later than its stated/common term.

df["payment_term_gap"] = (
    df["avg_payment_time_days"]
    - df["common_payment_term_days"]
)


# ============================================================
# 11. INDUSTRY PERCENTILE
# ============================================================

# Compare the company with other businesses in:
#
#     same industry
#     AND
#     same reporting period
#
# using pct_paid_over_60.
#
# Higher percentile = worse relative late-payment behaviour.

df["industry_percentile"] = (
    df.groupby(
        ["period_end", "industry_division"],
        dropna=False
    )["pct_paid_over_60"]
    .rank(
        method="average",
        pct=True
    )
    * 100
)


# ============================================================
# 12. CREATE NEXT-PERIOD TARGET
# ============================================================

# THIS IS THE IMPORTANT PART.
#
# For each company:
#
# period t             period t+1
# --------             ----------
# model features  ---> pct_paid_over_60
#
# shift(-1) gets the value from the NEXT observation
# belonging to the SAME ABN.

df["next_period_pct_paid_over_60"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .shift(-1)
)


# Also store the next reporting period.
# This makes it easier to audit the result.

df["next_period_end"] = (
    df.groupby("abn")["period_end"]
    .shift(-1)
)


# ============================================================
# 13. MAKE SURE t+1 IS ACTUALLY LATER THAN t
# ============================================================

valid_next_period = (
    df["next_period_end"].notna()
    & (df["next_period_end"] > df["period_end"])
)


# ============================================================
# 14. CREATE BINARY LABEL
# ============================================================

# Do not make a label when no valid t+1 exists.

df["high_payment_delay"] = np.nan

df.loc[
    valid_next_period,
    "high_payment_delay"
] = (
    df.loc[
        valid_next_period,
        "next_period_pct_paid_over_60"
    ]
    >= HIGH_PAYMENT_DELAY_THRESHOLD
).astype(int)


# ============================================================
# 15. REMOVE ROWS WITHOUT A VALID NEXT PERIOD
# ============================================================

training_df = df[
    valid_next_period
].copy()

print(
    f"Rows with a valid future reporting period: "
    f"{len(training_df)}"
)


# ============================================================
# 16. REMOVE ROWS WHERE THE FUTURE TARGET ITSELF IS MISSING
# ============================================================

training_df = training_df.dropna(
    subset=["next_period_pct_paid_over_60"]
).copy()


# ============================================================
# 17. CHECK FEATURE AVAILABILITY
# ============================================================

print()
print("Missing feature values BEFORE filtering:")

for feature in MODEL_FEATURES:

    missing = (
        training_df[feature]
        .isna()
        .sum()
    )

    print(
        f"{feature}: {missing}"
    )


# ============================================================
# 18. REMOVE ROWS WITH MISSING MODEL FEATURES
# ============================================================

before = len(training_df)

training_df = training_df.dropna(
    subset=MODEL_FEATURES
).copy()

after = len(training_df)

print()
print(
    f"Rows removed because of missing features: "
    f"{before - after}"
)


# ============================================================
# 19. SAFETY CHECK: NO FUTURE INFORMATION IN FEATURES
# ============================================================

for feature in MODEL_FEATURES:

    assert not feature.startswith(
        "next_"
    ), f"Future variable found in features: {feature}"

assert (
    "high_payment_delay"
    not in MODEL_FEATURES
)

assert (
    "next_period_pct_paid_over_60"
    not in MODEL_FEATURES
)


# ============================================================
# 20. FINAL OUTPUT COLUMNS
# ============================================================

output_columns = [
    # Identification only — NOT model features
    "abn",
    "entity_name",

    # Current reporting period t
    "period_start",
    "period_end",

    "industry_division",

    # Model features at t
    *MODEL_FEATURES,

    # Future period, included for auditing
    "next_period_end",

    # Future raw target
    "next_period_pct_paid_over_60",

    # Final machine-learning label
    "high_payment_delay",
]

training_df = training_df[
    output_columns
].copy()


# ============================================================
# 21. MAKE LABEL AN INTEGER
# ============================================================

training_df["high_payment_delay"] = (
    training_df["high_payment_delay"]
    .astype(int)
)


# ============================================================
# 22. SAVE TRAINING DATA
# ============================================================

training_df.to_excel(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# 23. PRINT SUMMARY
# ============================================================

print()
print("=" * 55)
print("TRAINING DATA CREATED SUCCESSFULLY")
print("=" * 55)

print()
print(f"Saved to:")
print(OUTPUT_FILE)

print()
print(
    f"Final training rows: "
    f"{len(training_df)}"
)

print()
print("MODEL FEATURES:")

for feature in MODEL_FEATURES:
    print(f"  - {feature}")

print()
print(
    f"HIGH PAYMENT DELAY THRESHOLD: "
    f"{HIGH_PAYMENT_DELAY_THRESHOLD}%"
)

print()
print("LABEL COUNTS:")

print(
    training_df[
        "high_payment_delay"
    ]
    .value_counts()
    .sort_index()
)

print()
print("LABEL PERCENTAGES:")

print(
    training_df[
        "high_payment_delay"
    ]
    .value_counts(
        normalize=True
    )
    .sort_index()
    * 100
)

print()
print("Preview:")

print(
    training_df.head()
)