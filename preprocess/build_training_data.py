import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = Path(__file__).parent

INPUT_FILE = BASE_DIR / "clean.xlsx"
OUTPUT_XLSX = BASE_DIR / "training_data.xlsx"
OUTPUT_CSV = BASE_DIR / "training_data.csv"

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

# Label:
# 1 if the NEXT VALID reporting observation has >= 20%
# of invoices paid after 60 days.
HIGH_PAYMENT_DELAY_THRESHOLD = 20.0


# ============================================================
# ACTUAL SOURCE COLUMNS IN historical_for_analysis
# ============================================================

SOURCE_COLUMNS = [
    "report_id",
    "entity_name",
    "abn",
    "extra_acn",
    "report_type",
    "period_start",
    "period_end",

    "extra_standard_payment_terms",

    "extra_percentage_of_number_invoices_paid_within_20_days",
    "extra_percentage_of_number_invoices_paid_between_21_and_30_days",
    "extra_percentage_of_number_invoices_paid_between_31_and_60_days",
    "extra_percentage_of_number_invoices_paid_between_61_and_90_days",
    "extra_percentage_of_number_invoices_paid_between_91_and_120_days",
    "extra_percentage_of_number_invoices_paid_in_more_than_120_days",

    "extra_original_report_date",
    "extra_revised_report_date",
    "extra_changes_from_prior_report",

    "industry_division",

    "entity_key",
    "reporting_period_key",
    "entity_period_key",
]


# ============================================================
# HELPER: NUMERIC PAYMENT BANDS
# ============================================================

PAYMENT_BAND_COLUMNS = [
    "extra_percentage_of_number_invoices_paid_within_20_days",
    "extra_percentage_of_number_invoices_paid_between_21_and_30_days",
    "extra_percentage_of_number_invoices_paid_between_31_and_60_days",
    "extra_percentage_of_number_invoices_paid_between_61_and_90_days",
    "extra_percentage_of_number_invoices_paid_between_91_and_120_days",
    "extra_percentage_of_number_invoices_paid_in_more_than_120_days",
]


# ============================================================
# HELPER: ESTIMATED AVERAGE PAYMENT TIME
# ============================================================

def estimate_average_payment_days(row):
    """
    Estimate average payment time from the available payment bands.

    This is a proxy because the source data provides ranges rather
    than exact invoice-level payment times.

    Midpoints:
        0-20       -> 10
        21-30      -> 25.5
        31-60      -> 45.5
        61-90      -> 75.5
        91-120     -> 105.5
        >120       -> 135 (MVP proxy)

    IMPORTANT:
    The >120 bucket is open-ended, so 135 is only an approximation.
    """

    midpoint_map = {
        PAYMENT_BAND_COLUMNS[0]: 10.0,
        PAYMENT_BAND_COLUMNS[1]: 25.5,
        PAYMENT_BAND_COLUMNS[2]: 45.5,
        PAYMENT_BAND_COLUMNS[3]: 75.5,
        PAYMENT_BAND_COLUMNS[4]: 105.5,
        PAYMENT_BAND_COLUMNS[5]: 135.0,
    }

    weighted_sum = 0.0
    total_percentage = 0.0

    for column, midpoint in midpoint_map.items():
        value = row[column]

        if pd.notna(value):
            weighted_sum += float(value) * midpoint
            total_percentage += float(value)

    if total_percentage <= 0:
        return np.nan

    return weighted_sum / total_percentage


# ============================================================
# HELPER: ESTIMATED PERCENTAGE PAID WITHIN STANDARD TERM
# ============================================================

def estimate_paid_within_term(row):
    """
    Estimate the percentage of invoices paid within the company's
    reported standard payment term.

    The source does NOT provide an exact pct_paid_within_payment_term.

    We therefore estimate it from the payment-time bands.

    For a term that falls inside a band, linear interpolation is used.

    Examples:
        term <= 20:
            proportion of the 0-20 bucket is estimated linearly.

        term = 30:
            100% of 0-20 + 100% of 21-30.

        term = 45:
            100% of <=30 + 50% of the 31-60 bucket.

    This remains a proxy because the underlying distribution inside
    each band is unknown.
    """

    term = row["extra_standard_payment_terms"]

    if pd.isna(term):
        return np.nan

    term = float(term)

    if term < 0:
        return np.nan

    b0_20 = row[PAYMENT_BAND_COLUMNS[0]]
    b21_30 = row[PAYMENT_BAND_COLUMNS[1]]
    b31_60 = row[PAYMENT_BAND_COLUMNS[2]]
    b61_90 = row[PAYMENT_BAND_COLUMNS[3]]
    b91_120 = row[PAYMENT_BAND_COLUMNS[4]]
    b120 = row[PAYMENT_BAND_COLUMNS[5]]

    values = [
        b0_20,
        b21_30,
        b31_60,
        b61_90,
        b91_120,
        b120,
    ]

    if any(pd.isna(v) for v in values):
        return np.nan

    if term <= 20:
        return b0_20 * (term / 20.0)

    if term <= 30:
        return b0_20 + b21_30 * ((term - 20.0) / 10.0)

    if term <= 60:
        return b0_20 + b21_30 + b31_60 * ((term - 30.0) / 30.0)

    if term <= 90:
        return (
            b0_20
            + b21_30
            + b31_60
            + b61_90 * ((term - 60.0) / 30.0)
        )

    if term <= 120:
        return (
            b0_20
            + b21_30
            + b31_60
            + b61_90
            + b91_120 * ((term - 90.0) / 30.0)
        )

    # For >120-day terms, all explicitly measured buckets are
    # considered within term. The >120 bucket is open-ended, so
    # we cannot know how much of it is within the exact term.
    return (
        b0_20
        + b21_30
        + b31_60
        + b61_90
        + b91_120
    )


# ============================================================
# 1. LOAD HISTORICAL DATA
# ============================================================

print("Reading clean.xlsx...")
print("Sheet: historical_for_analysis")

df = pd.read_excel(
    INPUT_FILE,
    sheet_name="historical_for_analysis",
)

print(f"Original rows: {len(df)}")


# ============================================================
# 2. VERIFY SOURCE SCHEMA
# ============================================================

missing_source_columns = [
    column
    for column in SOURCE_COLUMNS
    if column not in df.columns
]

if missing_source_columns:
    raise ValueError(
        "The following required source columns are missing:\n"
        + "\n".join(
            f"  - {column}"
            for column in missing_source_columns
        )
    )

df = df[SOURCE_COLUMNS].copy()


# ============================================================
# 3. CLEAN IDENTIFIERS AND DATES
# ============================================================

for column in [
    "abn",
    "entity_name",
    "industry_division",
    "report_type",
    "entity_key",
    "reporting_period_key",
    "entity_period_key",
]:
    df[column] = (
        df[column]
        .astype("string")
        .str.strip()
    )

df["period_start"] = pd.to_datetime(
    df["period_start"],
    errors="coerce",
)

df["period_end"] = pd.to_datetime(
    df["period_end"],
    errors="coerce",
)

df["extra_original_report_date"] = pd.to_datetime(
    df["extra_original_report_date"],
    errors="coerce",
)

df["extra_revised_report_date"] = pd.to_datetime(
    df["extra_revised_report_date"],
    errors="coerce",
)

df = df.dropna(
    subset=["abn", "period_end"]
).copy()


# ============================================================
# 4. CONVERT NUMERIC SOURCE FIELDS
# ============================================================

for column in PAYMENT_BAND_COLUMNS + [
    "extra_standard_payment_terms",
]:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce",
    )


# ============================================================
# 5. DUPLICATE / REVISION HANDLING
# ============================================================

print()
print("Checking duplicate ABN + period_end rows...")

duplicate_mask = df.duplicated(
    subset=["abn", "period_end"],
    keep=False,
)

print(
    "Duplicate company-period rows: "
    f"{int(duplicate_mask.sum())}"
)

print(
    "Duplicate company-period groups: "
    f"{int(df.loc[duplicate_mask, ['abn', 'period_end']].drop_duplicates().shape[0])}"
)


# We do NOT have report_submitted_date in this sheet.
#
# Instead, use the explicit revised report date when available.
# If revised date is missing, use original report date.
# If both are missing, preserve deterministic input order.
#
# This is a practical MVP revision rule. It does NOT claim that
# every duplicate has been perfectly resolved by an official
# revision-status field.

df["_original_row_order"] = np.arange(len(df))

df["_revision_sort_date"] = (
    df["extra_revised_report_date"]
    .combine_first(df["extra_original_report_date"])
)

df = df.sort_values(
    [
        "abn",
        "period_end",
        "_revision_sort_date",
        "_original_row_order",
    ],
    na_position="first",
    kind="mergesort",
)

df = df.drop_duplicates(
    subset=["abn", "period_end"],
    keep="last",
).copy()

df = df.drop(
    columns=[
        "_original_row_order",
        "_revision_sort_date",
    ]
)

print(
    "Rows after keeping one observation per "
    f"ABN + period_end: {len(df)}"
)


# ============================================================
# 6. SORT COMPANY HISTORY
# ============================================================

df = df.sort_values(
    [
        "abn",
        "period_end",
        "period_start",
    ],
    kind="mergesort",
).reset_index(drop=True)


# ============================================================
# 7. CREATE PAYMENT FEATURES
# ============================================================

# 0-30 days
df["pct_paid_30"] = (
    df[
        "extra_percentage_of_number_invoices_paid_within_20_days"
    ]
    + df[
        "extra_percentage_of_number_invoices_paid_between_21_and_30_days"
    ]
)

# 31-60 days
df["pct_paid_31_60"] = (
    df[
        "extra_percentage_of_number_invoices_paid_between_31_and_60_days"
    ]
)

# >60 days
df["pct_paid_over_60"] = (
    df[
        "extra_percentage_of_number_invoices_paid_between_61_and_90_days"
    ]
    + df[
        "extra_percentage_of_number_invoices_paid_between_91_and_120_days"
    ]
    + df[
        "extra_percentage_of_number_invoices_paid_in_more_than_120_days"
    ]
)


# ============================================================
# 8. ESTIMATE AVERAGE PAYMENT TIME
# ============================================================

df["estimated_avg_payment_time_days"] = (
    df.apply(
        estimate_average_payment_days,
        axis=1,
    )
)


# ============================================================
# 9. ESTIMATE PCT PAID WITHIN PAYMENT TERM
# ============================================================

df["pct_paid_within_term"] = (
    df.apply(
        estimate_paid_within_term,
        axis=1,
    )
)


# ============================================================
# 10. PAYMENT TREND
# ============================================================

# Positive = worsening
# Negative = improving
#
# Current >60-day percentage minus previous observed period.

df["payment_trend"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .diff()
    .fillna(0)
)


# ============================================================
# 11. PAYMENT VOLATILITY
# ============================================================

# Expanding standard deviation:
# each row only uses observations at or before that row.

df["payment_volatility"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .expanding()
    .std()
    .reset_index(level=0, drop=True)
    .fillna(0)
)


# ============================================================
# 12. NUMBER OF REPORTING PERIODS
# ============================================================

df["num_reporting_periods"] = (
    df.groupby("abn")
    .cumcount()
    + 1
)


# ============================================================
# 13. PAYMENT TERM GAP
# ============================================================

df["payment_term_gap"] = (
    df["estimated_avg_payment_time_days"]
    - df["extra_standard_payment_terms"]
)


# ============================================================
# 14. INDUSTRY PERCENTILE
# ============================================================

# Same period_end + same industry.
# Higher percentile = worse relative >60-day behaviour.

df["industry_percentile"] = (
    df.groupby(
        [
            "period_end",
            "industry_division",
        ],
        dropna=False,
    )["pct_paid_over_60"]
    .rank(
        method="average",
        pct=True,
    )
    * 100
)


# ============================================================
# 15. CREATE NEXT VALID OBSERVATION
# ============================================================

# We deliberately use the next available observation for the
# same ABN after sorting by period_end.
#
# We do NOT pretend that every calendar period exists for every
# company.

df["next_period_end"] = (
    df.groupby("abn")["period_end"]
    .shift(-1)
)

df["next_period_pct_paid_over_60"] = (
    df.groupby("abn")["pct_paid_over_60"]
    .shift(-1)
)


# ============================================================
# 16. VALID NEXT PERIOD
# ============================================================

valid_next_period = (
    df["next_period_end"].notna()
    & (
        df["next_period_end"]
        > df["period_end"]
    )
)

print()
print(
    "Rows with a valid next reporting observation: "
    f"{int(valid_next_period.sum())}"
)


# ============================================================
# 17. CREATE BINARY LABEL
# ============================================================

df["high_payment_delay"] = np.nan

df.loc[
    valid_next_period,
    "high_payment_delay",
] = (
    df.loc[
        valid_next_period,
        "next_period_pct_paid_over_60",
    ]
    >= HIGH_PAYMENT_DELAY_THRESHOLD
).astype(int)


# ============================================================
# 18. KEEP TRAINING ROWS
# ============================================================

training_df = df[
    valid_next_period
].copy()

training_df = training_df.dropna(
    subset=[
        "next_period_pct_paid_over_60"
    ]
).copy()


# ============================================================
# 19. FEATURE AVAILABILITY CHECK
# ============================================================

print()
print("Missing model feature values:")

for feature in MODEL_FEATURES:
    missing = int(
        training_df[feature]
        .isna()
        .sum()
    )

    print(
        f"  {feature}: {missing}"
    )


# ============================================================
# 20. REMOVE MISSING FEATURE ROWS
# ============================================================

before = len(training_df)

training_df = training_df.dropna(
    subset=MODEL_FEATURES
).copy()

after = len(training_df)

print()
print(
    "Rows removed because of missing model features: "
    f"{before - after}"
)


# ============================================================
# 21. DATA QUALITY CHECKS
# ============================================================

# Payment percentages should normally be between 0 and 100.
for feature in [
    "pct_paid_30",
    "pct_paid_31_60",
    "pct_paid_over_60",
    "pct_paid_within_term",
]:
    invalid = (
        training_df[feature].notna()
        & (
            (training_df[feature] < 0)
            | (training_df[feature] > 100)
        )
    )

    if invalid.any():
        print(
            f"WARNING: {feature} contains "
            f"{int(invalid.sum())} values outside 0-100."
        )


# Flag unusual standard terms rather than silently clipping them.
unusual_terms = (
    training_df["payment_term_gap"].notna()
    & (
        training_df["payment_term_gap"].abs() > 365
    )
)

print()
print(
    "Rows with payment-term gap > 365 days in absolute value: "
    f"{int(unusual_terms.sum())}"
)


# ============================================================
# 22. FUTURE LEAKAGE CHECKS
# ============================================================

for feature in MODEL_FEATURES:
    assert not feature.startswith("next_"), (
        f"Future variable found in MODEL_FEATURES: {feature}"
    )

assert "high_payment_delay" not in MODEL_FEATURES
assert "next_period_pct_paid_over_60" not in MODEL_FEATURES
assert "next_period_end" not in MODEL_FEATURES


# All model features must be numeric.
for feature in MODEL_FEATURES:
    assert pd.api.types.is_numeric_dtype(
        training_df[feature]
    ), (
        f"MODEL FEATURE IS NOT NUMERIC: {feature}"
    )


# Label must be binary.
assert set(
    training_df["high_payment_delay"].unique()
).issubset({0, 1})


# ============================================================
# 23. FINAL OUTPUT COLUMNS
# ============================================================

output_columns = [
    # Identification / audit information
    "abn",
    "entity_name",

    # Current period t
    "period_start",
    "period_end",
    "industry_division",

    # Model features at t
    *MODEL_FEATURES,

    # Future information ONLY for auditing the label
    "next_period_end",
    "next_period_pct_paid_over_60",

    # ML label
    "high_payment_delay",
]

training_df = training_df[
    output_columns
].copy()


# ============================================================
# 24. FINAL DATA TYPES
# ============================================================

training_df["abn"] = (
    training_df["abn"]
    .astype("string")
)

training_df["entity_name"] = (
    training_df["entity_name"]
    .astype("string")
)

training_df["industry_division"] = (
    training_df["industry_division"]
    .astype("string")
)

training_df["high_payment_delay"] = (
    training_df["high_payment_delay"]
    .astype(int)
)

for feature in MODEL_FEATURES:
    training_df[feature] = pd.to_numeric(
        training_df[feature],
        errors="coerce",
    )


# ============================================================
# 25. SAVE OUTPUT
# ============================================================

training_df.to_excel(
    OUTPUT_XLSX,
    index=False,
)

training_df.to_csv(
    OUTPUT_CSV,
    index=False,
)


# ============================================================
# 26. SUMMARY
# ============================================================

print()
print("=" * 60)
print("TRAINING DATA CREATED SUCCESSFULLY")
print("=" * 60)

print()
print(f"Excel saved to: {OUTPUT_XLSX}")
print(f"CSV saved to:   {OUTPUT_CSV}")

print()
print(f"Final training rows: {len(training_df)}")
print(
    f"Final companies:     {training_df['abn'].nunique()}"
)

print()
print("MODEL FEATURES:")

for feature in MODEL_FEATURES:
    print(f"  - {feature}")

print()
print(
    "HIGH PAYMENT DELAY THRESHOLD: "
    f"{HIGH_PAYMENT_DELAY_THRESHOLD}%"
)

print()
print("LABEL COUNTS:")

print(
    training_df["high_payment_delay"]
    .value_counts()
    .sort_index()
)

print()
print("LABEL PERCENTAGES:")

print(
    training_df["high_payment_delay"]
    .value_counts(normalize=True)
    .sort_index()
    * 100
)

print()
print("MODEL FEATURE DATA TYPES:")

print(
    training_df[MODEL_FEATURES]
    .dtypes
)

print()
print("Preview:")

print(
    training_df.head()
)
