"""
PayLens ML Training Data Builder

Input:
    preprocess/clean.xlsx
    Sheet: historical_for_analysis

Output:
    preprocess/training_data.csv
    preprocess/training_data.xlsx
    preprocess/company_history.csv
    preprocess/company_history.xlsx

ML boundary:
    The model predicts NEXT-PERIOD PAYMENT-DELAY RISK.

    It does NOT predict:
    - bankruptcy
    - insolvency
    - default
    - profitability
    - cash reserves
    - contract exposure

Important data-quality rule:
    If all six payment-time bands are zero, this is treated as
    MISSING payment information, NOT as 0% payment delay.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "clean.xlsx"

TRAINING_CSV = BASE_DIR / "training_data.csv"
TRAINING_XLSX = BASE_DIR / "training_data.xlsx"

HISTORY_CSV = BASE_DIR / "company_history.csv"
HISTORY_XLSX = BASE_DIR / "company_history.xlsx"


# ============================================================
# 2. MODEL CONFIGURATION
# ============================================================

# Initial ML contract.
#
# Keep this clean and simple for the first model.
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


# Hackathon modelling threshold.
#
# This is NOT an official Australian Government threshold.
HIGH_DELAY_THRESHOLD = 20.0


# ============================================================
# 3. SOURCE PAYMENT COLUMNS
# ============================================================

PAYMENT_COLUMNS = [
    "extra_percentage_of_number_invoices_paid_within_20_days",

    "extra_percentage_of_number_invoices_paid_between_21_and_30_days",

    "extra_percentage_of_number_invoices_paid_between_31_and_60_days",

    "extra_percentage_of_number_invoices_paid_between_61_and_90_days",

    "extra_percentage_of_number_invoices_paid_between_91_and_120_days",

    "extra_percentage_of_number_invoices_paid_in_more_than_120_days",
]


# ============================================================
# 4. REQUIRED SOURCE COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "entity_name",
    "abn",

    "report_type",

    "period_start",
    "period_end",

    "extra_standard_payment_terms",

    "extra_business_industry_code",
    "extra_business_industry_code_description",

    "industry_division",

    "extra_original_report_date",
    "extra_revised_report_date",

    *PAYMENT_COLUMNS,
]


# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================

def to_numeric(series):
    """
    Safely convert a pandas Series to numeric.
    """
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def clean_percentage(series):
    """
    Convert percentage values to numeric 0-100.

    Handles examples such as:
        25
        25.0
        "25"
        "25%"
    """

    s = (
        series
        .astype("string")
        .str.strip()
        .str.replace("%", "", regex=False)
    )

    s = pd.to_numeric(
        s,
        errors="coerce",
    )

    # Anything outside 0-100 is invalid.
    s = s.where(
        (s >= 0)
        & (s <= 100)
    )

    return s


# ============================================================
# 6. ESTIMATED PAYMENT TIME
# ============================================================

def calculate_estimated_payment_days(row):
    """
    Estimate average payment time from payment-time bands.

    Midpoints:

        <=20 days       -> 10
        21-30 days      -> 25.5
        31-60 days      -> 45.5
        61-90 days      -> 75.5
        91-120 days     -> 105.5
        >120 days       -> 135

    The >120 value is only an MVP proxy.

    Therefore this feature is called:

        estimated_avg_payment_time_days

    NOT:

        avg_days_to_pay
    """

    values = [
        row[PAYMENT_COLUMNS[0]],
        row[PAYMENT_COLUMNS[1]],
        row[PAYMENT_COLUMNS[2]],
        row[PAYMENT_COLUMNS[3]],
        row[PAYMENT_COLUMNS[4]],
        row[PAYMENT_COLUMNS[5]],
    ]

    midpoints = [
        10.0,
        25.5,
        45.5,
        75.5,
        105.5,
        135.0,
    ]

    valid_pairs = []

    for value, midpoint in zip(
        values,
        midpoints,
    ):
        if pd.notna(value):
            valid_pairs.append(
                (
                    float(value),
                    midpoint,
                )
            )

    # No payment data.
    if not valid_pairs:
        return np.nan

    total = sum(
        value
        for value, _ in valid_pairs
    )

    # All bands are zero.
    if total <= 0:
        return np.nan

    weighted_sum = sum(
        value * midpoint
        for value, midpoint in valid_pairs
    )

    return weighted_sum / total


# ============================================================
# 7. OPTIONAL PAYMENT-WITHIN-TERM FEATURE
# ============================================================

def calculate_paid_within_term(row):
    """
    Estimate percentage paid within standard payment terms.

    This is retained for analysis/history.

    It is NOT part of the initial MODEL_FEATURES.
    """

    term = row["extra_standard_payment_terms"]

    if pd.isna(term):
        return np.nan

    term = float(term)

    bands = [
        (
            0,
            20,
            row[PAYMENT_COLUMNS[0]],
        ),
        (
            21,
            30,
            row[PAYMENT_COLUMNS[1]],
        ),
        (
            31,
            60,
            row[PAYMENT_COLUMNS[2]],
        ),
        (
            61,
            90,
            row[PAYMENT_COLUMNS[3]],
        ),
        (
            91,
            120,
            row[PAYMENT_COLUMNS[4]],
        ),
        (
            121,
            np.inf,
            row[PAYMENT_COLUMNS[5]],
        ),
    ]

    cumulative = 0.0

    for lower, upper, value in bands:

        if pd.isna(value):
            return np.nan

        value = float(value)

        # Entire band is inside the payment term.
        if term >= upper:
            cumulative += value
            continue

        # Payment term ends before this band.
        if term < lower:
            return cumulative

        # Payment term ends inside this band.
        if np.isinf(upper):
            return cumulative

        fraction = (
            (term - lower)
            / (upper - lower)
        )

        fraction = max(
            0.0,
            min(1.0, fraction),
        )

        return (
            cumulative
            + value * fraction
        )

    return cumulative


# ============================================================
# 8. DUPLICATE / REVISION HANDLING
# ============================================================

def deduplicate_company_period(df):
    """
    Keep one report for each:

        ABN + period_end

    Preference:
        1. revised report date
        2. original report date
        3. original row order

    This is a deterministic MVP rule.
    """

    work = df.copy()

    work["_row_order"] = np.arange(
        len(work)
    )

    revised_date = pd.to_datetime(
        work["extra_revised_report_date"],
        errors="coerce",
    )

    original_date = pd.to_datetime(
        work["extra_original_report_date"],
        errors="coerce",
    )

    work["_best_report_date"] = (
        revised_date
        .fillna(original_date)
    )

    work = work.sort_values(
        by=[
            "abn",
            "period_end",
            "_best_report_date",
            "_row_order",
        ],
        ascending=[
            True,
            True,
            True,
            True,
        ],
        na_position="first",
    )

    work = work.drop_duplicates(
        subset=[
            "abn",
            "period_end",
        ],
        keep="last",
    )

    work = work.drop(
        columns=[
            "_row_order",
            "_best_report_date",
        ]
    )

    return work


# ============================================================
# 9. LOAD DATA
# ============================================================

def load_data():

    print("=" * 70)
    print("PAYLENS TRAINING DATA BUILDER")
    print("=" * 70)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            "\nCannot find:\n"
            f"{INPUT_FILE}\n\n"
            "Make sure clean.xlsx is inside the preprocess folder."
        )

    print(
        f"\nInput file:\n{INPUT_FILE}"
    )

    print(
        "\nReading sheet:"
        "\nhistorical_for_analysis"
    )

    df = pd.read_excel(
        INPUT_FILE,
        sheet_name="historical_for_analysis",
    )

    print(
        f"\nRaw rows: {len(df):,}"
    )

    print(
        f"Raw columns: {len(df.columns):,}"
    )

    # --------------------------------------------------------
    # Check source schema.
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:

        print(
            "\nERROR: Missing required columns:"
        )

        for column in missing_columns:
            print(
                f"  - {column}"
            )

        raise ValueError(
            "\nThe historical_for_analysis schema "
            "does not match the expected schema."
        )

    return df


# ============================================================
# 10. CLEAN SOURCE DATA
# ============================================================

def clean_data(df):

    df = df.copy()

    # --------------------------------------------------------
    # ABN
    # --------------------------------------------------------

    df["abn"] = (
        df["abn"]
        .astype("string")
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
        .str.strip()
    )

    # --------------------------------------------------------
    # Entity name
    # --------------------------------------------------------

    df["entity_name"] = (
        df["entity_name"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    date_columns = [
        "period_start",
        "period_end",
        "extra_original_report_date",
        "extra_revised_report_date",
    ]

    for column in date_columns:

        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Payment terms
    # --------------------------------------------------------

    df["extra_standard_payment_terms"] = (
        to_numeric(
            df["extra_standard_payment_terms"]
        )
    )

    # --------------------------------------------------------
    # Payment percentages
    # --------------------------------------------------------

    for column in PAYMENT_COLUMNS:

        df[column] = clean_percentage(
            df[column]
        )

    # --------------------------------------------------------
    # Remove rows without ABN / period.
    # --------------------------------------------------------

    before = len(df)

    df = df[
        df["abn"].notna()
        & (df["abn"] != "")
        & df["period_end"].notna()
    ].copy()

    removed = (
        before
        - len(df)
    )

    print(
        f"\nRows removed due to missing "
        f"ABN/period_end: {removed:,}"
    )

    # --------------------------------------------------------
    # Duplicate company-period audit.
    # --------------------------------------------------------

    duplicate_rows = df.duplicated(
        subset=[
            "abn",
            "period_end",
        ],
        keep=False,
    ).sum()

    print(
        "Duplicate ABN + period_end rows "
        f"before revision handling: {duplicate_rows:,}"
    )

    # --------------------------------------------------------
    # Handle revisions.
    # --------------------------------------------------------

    df = deduplicate_company_period(
        df
    )

    print(
        "Rows after revision/deduplication: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Sort chronologically.
    # --------------------------------------------------------

    df = df.sort_values(
        by=[
            "abn",
            "period_end",
        ]
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# 11. BUILD PAYMENT FEATURES
# ============================================================

def build_payment_features(df):
    """
    Build payment-related features.

    Data-quality rule:
    - All six payment bands equal to zero -> missing payment data.
    - If the six bands sum to more than 100% (with a small rounding
      tolerance), the whole payment observation is treated as invalid.
    - Invalid payment observations are set to NaN rather than clipped,
      because clipping would silently distort the original data.
    """

    df = df.copy()

    # --------------------------------------------------------
    # Calculate the total of the six payment bands.
    # --------------------------------------------------------

    df["payment_band_total"] = (
        df[PAYMENT_COLUMNS]
        .sum(axis=1, min_count=1)
    )

    # A small tolerance allows minor rounding differences.
    PAYMENT_TOTAL_TOLERANCE = 0.5

    df["payment_band_present"] = (
        df["payment_band_total"].notna()
        & (df["payment_band_total"] > 0)
    )

    df["payment_band_total_invalid"] = (
        df["payment_band_present"]
        & (
            df["payment_band_total"]
            > 100.0 + PAYMENT_TOTAL_TOLERANCE
        )
    )

    # Only positive and internally consistent payment-band totals
    # are considered usable payment data.
    df["payment_band_has_data"] = (
        df["payment_band_present"]
        & ~df["payment_band_total_invalid"]
    )

    unavailable = ~df["payment_band_has_data"]

    unavailable_count = int(unavailable.sum())
    invalid_count = int(
        df["payment_band_total_invalid"].sum()
    )

    percentage_denominator = max(len(df), 1)

    print(
        "\nPayment-band data unavailable/all-zero/invalid:"
        f" {unavailable_count:,}"
        f" ({unavailable_count / percentage_denominator * 100:.2f}%)"
    )

    print(
        "\nPayment-band totals above "
        f"{100.0 + PAYMENT_TOTAL_TOLERANCE:.1f}%:"
        f" {invalid_count:,}"
    )

    # --------------------------------------------------------
    # Build percentage features.
    # --------------------------------------------------------

    # Percentage paid within 30 days.
    df["pct_paid_30"] = (
        df[
            [
                PAYMENT_COLUMNS[0],
                PAYMENT_COLUMNS[1],
            ]
        ]
        .sum(axis=1, min_count=1)
    )

    # Percentage paid between 31 and 60 days.
    df["pct_paid_31_60"] = df[PAYMENT_COLUMNS[2]]

    # Percentage paid after 60 days.
    df["pct_paid_over_60"] = (
        df[
            [
                PAYMENT_COLUMNS[3],
                PAYMENT_COLUMNS[4],
                PAYMENT_COLUMNS[5],
            ]
        ]
        .sum(axis=1, min_count=1)
    )

    # --------------------------------------------------------
    # Estimated average payment time.
    # --------------------------------------------------------

    df["estimated_avg_payment_time_days"] = df.apply(
        calculate_estimated_payment_days,
        axis=1,
    )

    # --------------------------------------------------------
    # Analysis-only payment-within-term feature.
    # --------------------------------------------------------

    df["pct_paid_within_term"] = df.apply(
        calculate_paid_within_term,
        axis=1,
    )

    # --------------------------------------------------------
    # Invalid or unavailable payment observations.
    #
    # Do not convert these to zero and do not clip them.
    # --------------------------------------------------------

    payment_derived_features = [
        "pct_paid_30",
        "pct_paid_31_60",
        "pct_paid_over_60",
        "estimated_avg_payment_time_days",
        "pct_paid_within_term",
    ]

    df.loc[
        unavailable,
        payment_derived_features,
    ] = np.nan

    # --------------------------------------------------------
    # Final range validation for derived percentage features.
    #
    # If a row still produces an impossible percentage, mark the
    # entire payment observation as invalid. This avoids silently
    # clipping or distorting the source data.
    # --------------------------------------------------------

    percentage_features = [
        "pct_paid_30",
        "pct_paid_31_60",
        "pct_paid_over_60",
        "pct_paid_within_term",
    ]

    invalid_derived_percentage = pd.Series(
        False,
        index=df.index,
    )

    for column in percentage_features:
        invalid_derived_percentage |= (
            df[column].notna()
            & (
                (df[column] < 0)
                | (df[column] > 100)
            )
        )

    if invalid_derived_percentage.any():
        invalid_derived_count = int(
            invalid_derived_percentage.sum()
        )

        print(
            "\nRows with impossible derived payment percentages:"
            f" {invalid_derived_count:,}"
        )

        df["payment_band_total_invalid"] = (
            df["payment_band_total_invalid"]
            | invalid_derived_percentage
        )

        df["payment_band_has_data"] = (
            df["payment_band_has_data"]
            & ~invalid_derived_percentage
        )

        df.loc[
            invalid_derived_percentage,
            payment_derived_features,
        ] = np.nan

    return df


# ============================================================
# 12. BUILD HISTORICAL FEATURES
# ============================================================

def build_historical_features(df):

    df = df.copy()

    # --------------------------------------------------------
    # Previous observed period.
    # --------------------------------------------------------

    df["previous_pct_paid_over_60"] = (
        df.groupby("abn")[
            "pct_paid_over_60"
        ]
        .shift(1)
    )

    # --------------------------------------------------------
    # Payment trend.
    #
    # Positive = more payment delay than previous period.
    # Negative = less payment delay than previous period.
    # --------------------------------------------------------

    df["payment_trend"] = (
        df["pct_paid_over_60"]
        - df["previous_pct_paid_over_60"]
    )

    # If either period has no payment data,
    # trend cannot be calculated.
    df.loc[
        df["pct_paid_over_60"].isna()
        | df["previous_pct_paid_over_60"].isna(),
        "payment_trend",
    ] = np.nan

    # --------------------------------------------------------
    # Payment volatility.
    #
    # Expanding standard deviation of observed
    # >60-day payment percentages.
    #
    # Missing payment data is NOT treated as zero.
    # --------------------------------------------------------

    df["payment_volatility"] = (
        df.groupby("abn")[
            "pct_paid_over_60"
        ]
        .transform(
            lambda s:
            s.expanding(
                min_periods=2
            ).std()
        )
    )

    # --------------------------------------------------------
    # Number of reporting periods.
    # --------------------------------------------------------

    df["num_reporting_periods"] = (
        df.groupby("abn")
        .cumcount()
        + 1
    )

    # --------------------------------------------------------
    # Industry percentile.
    #
    # Compare companies within:
    #     same period_end
    #     same industry_division
    #
    # This does NOT use future periods.
    # --------------------------------------------------------

    df["industry_percentile"] = np.nan

    valid_industry = (
        df["industry_division"].notna()
        & df["pct_paid_over_60"].notna()
    )

    if valid_industry.any():

        ranked = (
            df.loc[
                valid_industry
            ]
            .groupby(
                [
                    "period_end",
                    "industry_division",
                ]
            )[
                "pct_paid_over_60"
            ]
            .rank(
                method="average",
                pct=True,
            )
        )

        df.loc[
            valid_industry,
            "industry_percentile",
        ] = ranked.to_numpy()

    # --------------------------------------------------------
    # Analysis-only payment-term gap.
    # --------------------------------------------------------

    df["payment_term_gap"] = (
        df["estimated_avg_payment_time_days"]
        - df["extra_standard_payment_terms"]
    )

    return df


# ============================================================
# 13. BUILD NEXT-PERIOD TARGET
# ============================================================

def build_target(df):

    df = df.copy()

    # --------------------------------------------------------
    # Next observed period for the same company.
    # --------------------------------------------------------

    df["next_period_end"] = (
        df.groupby("abn")[
            "period_end"
        ]
        .shift(-1)
    )

    # --------------------------------------------------------
    # Next-period >60-day payment percentage.
    # --------------------------------------------------------

    df["next_period_pct_paid_over_60"] = (
        df.groupby("abn")[
            "pct_paid_over_60"
        ]
        .shift(-1)
    )

    # --------------------------------------------------------
    # Valid supervised training example:
    #
    # current period t
    # +
    # observed next period t+1
    # +
    # valid target
    # --------------------------------------------------------

    df["has_next_period_target"] = (
        df["next_period_end"].notna()
        & df[
            "next_period_pct_paid_over_60"
        ].notna()
    )

    # --------------------------------------------------------
    # Target.
    #
    # 1 = next-period >60-day payment percentage >= 20%
    # 0 = below 20%
    # --------------------------------------------------------

    df["high_payment_delay"] = np.nan

    valid_target = (
        df["has_next_period_target"]
    )

    df.loc[
        valid_target,
        "high_payment_delay",
    ] = (
        df.loc[
            valid_target,
            "next_period_pct_paid_over_60",
        ]
        >= HIGH_DELAY_THRESHOLD
    ).astype(int)

    return df


# ============================================================
# 14. LEAKAGE + DATA QUALITY CHECKS
# ============================================================

def run_checks(df):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "LEAKAGE / DATA QUALITY CHECKS"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # CHECK 1
    # Duplicate DataFrame columns.
    # --------------------------------------------------------

    duplicate_columns = (
        df.columns[
            df.columns.duplicated()
        ]
        .tolist()
    )

    if duplicate_columns:

        raise ValueError(
            "Duplicate columns found:\n"
            f"{duplicate_columns}"
        )

    print(
        "OK - no duplicate DataFrame columns."
    )

    # --------------------------------------------------------
    # CHECK 2
    # All model features exist.
    # --------------------------------------------------------

    missing_features = [
        feature
        for feature in MODEL_FEATURES
        if feature not in df.columns
    ]

    if missing_features:

        raise ValueError(
            "MODEL_FEATURES missing:\n"
            f"{missing_features}"
        )

    print(
        "OK - all MODEL_FEATURES exist."
    )

    # --------------------------------------------------------
    # CHECK 3
    # No obvious future variables.
    # --------------------------------------------------------

    suspicious_words = [
        "next",
        "future",
        "target",
        "label",
        "outcome",
    ]

    suspicious_features = []

    for feature in MODEL_FEATURES:

        feature_lower = (
            feature.lower()
        )

        if any(
            word in feature_lower
            for word in suspicious_words
        ):
            suspicious_features.append(
                feature
            )

    if suspicious_features:

        raise ValueError(
            "Possible future/target features:\n"
            f"{suspicious_features}"
        )

    print(
        "OK - no obvious future variables "
        "found in MODEL_FEATURES."
    )

    # --------------------------------------------------------
    # CHECK 4
    # Duplicate company-period.
    # --------------------------------------------------------

    duplicate_periods = (
        df.duplicated(
            subset=[
                "abn",
                "period_end",
            ]
        )
        .sum()
    )

    if duplicate_periods:

        raise ValueError(
            "Duplicate ABN + period_end rows remain: "
            f"{duplicate_periods:,}"
        )

    print(
        "OK - no duplicate ABN + period_end rows."
    )

    # --------------------------------------------------------
    # CHECK 5
    # All-zero payment data is missing.
    # --------------------------------------------------------

    wrong_zero_rows = (
        (~df["payment_band_has_data"])
        & df["pct_paid_over_60"].notna()
    ).sum()

    if wrong_zero_rows:

        raise ValueError(
            "All-zero payment rows were incorrectly "
            "assigned an observed pct_paid_over_60 value."
        )

    print(
        "OK - all-zero payment bands are treated as missing."
    )

    # --------------------------------------------------------
    # CHECK 6
    # Payment percentage ranges.
    # --------------------------------------------------------

    for feature in [
        "pct_paid_30",
        "pct_paid_31_60",
        "pct_paid_over_60",
    ]:

        values = (
            df[feature]
            .dropna()
        )

        if len(values) == 0:
            continue

        if (
            (values < 0).any()
            or (values > 100).any()
        ):

            invalid_values = values[
                (values < 0)
                | (values > 100)
            ]

            print(
                f"WARNING: {feature} still contains "
                f"{len(invalid_values):,} invalid values. "
                "These rows will be excluded from the "
                "percentage-range check."
            )

            df.loc[
                invalid_values.index,
                feature,
            ] = np.nan

    print(
        "OK - payment percentages are within 0-100."
    )

    # --------------------------------------------------------
    # CHECK 7
    # Target is only 0/1.
    # --------------------------------------------------------

    target_values = (
        df["high_payment_delay"]
        .dropna()
    )

    if len(target_values):

        invalid_target = (
            ~target_values.isin([0, 1])
        )

        if invalid_target.any():

            raise ValueError(
                "Target contains values other than 0/1."
            )

    print(
        "OK - target values are valid."
    )

    print(
        "=" * 70
    )


# ============================================================
# 15. BUILD TRAINING DATASET
# ============================================================

def build_training_dataset(df):

    # --------------------------------------------------------
    # Only rows with t+1 target.
    # --------------------------------------------------------

    training_df = df[
        df["has_next_period_target"]
    ].copy()

    print(
        "\nRows with valid next-period target: "
        f"{len(training_df):,}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # MODEL_FEATURES appear exactly once.
    #
    # payment_band_has_data is a data-quality field,
    # not an additional duplicate feature.
    # --------------------------------------------------------

    output_columns = [

        # Company identifiers.
        "entity_name",
        "abn",

        # Current observation period.
        "period_end",

        # Industry.
        "industry_division",
        "extra_business_industry_code",
        "extra_business_industry_code_description",

        # Payment terms.
        "extra_standard_payment_terms",

        # Data-quality indicator.
        "payment_band_has_data",
        "payment_band_total",
        "payment_band_total_invalid",

        # The eight official model features.
        *MODEL_FEATURES,

        # Target/audit fields.
        "next_period_end",
        "next_period_pct_paid_over_60",
        "high_payment_delay",
    ]

    # --------------------------------------------------------
    # Defensive removal of duplicate names.
    #
    # This is important because the previous version could
    # accidentally add payment_band_has_data twice.
    # --------------------------------------------------------

    output_columns = list(
        dict.fromkeys(
            output_columns
        )
    )

    # --------------------------------------------------------
    # Check output columns.
    # --------------------------------------------------------

    missing_output_columns = [
        column
        for column in output_columns
        if column not in training_df.columns
    ]

    if missing_output_columns:

        raise ValueError(
            "Missing output columns:\n"
            f"{missing_output_columns}"
        )

    training_df = training_df[
        output_columns
    ].copy()

    # --------------------------------------------------------
    # FINAL duplicate-column check.
    # --------------------------------------------------------

    duplicate_columns = (
        training_df.columns[
            training_df.columns.duplicated()
        ]
        .tolist()
    )

    if duplicate_columns:

        raise ValueError(
            "Duplicate columns in final training_df:\n"
            f"{duplicate_columns}"
        )

    # --------------------------------------------------------
    # Convert MODEL_FEATURES to numeric.
    #
    # .loc[:, feature] is guaranteed to be one Series because
    # duplicate columns were checked above.
    # --------------------------------------------------------

    for feature in MODEL_FEATURES:

        series = training_df.loc[
            :,
            feature,
        ]

        if not isinstance(
            series,
            pd.Series,
        ):

            raise TypeError(
                f"Feature '{feature}' is not a single Series. "
                "There is probably a duplicate column."
            )

        training_df.loc[
            :,
            feature,
        ] = pd.to_numeric(
            series,
            errors="coerce",
        )

    # --------------------------------------------------------
    # Data-quality flag.
    # --------------------------------------------------------

    training_df.loc[
        :,
        "payment_band_has_data",
    ] = (
        training_df[
            "payment_band_has_data"
        ]
        .astype(bool)
    )

    # --------------------------------------------------------
    # Target.
    # --------------------------------------------------------

    training_df.loc[
        :,
        "high_payment_delay",
    ] = (
        pd.to_numeric(
            training_df[
                "high_payment_delay"
            ],
            errors="coerce",
        )
        .astype("Int64")
    )

    return training_df


# ============================================================
# 16. BUILD COMPANY HISTORY
# ============================================================

def build_company_history(df):

    history_columns = [

        "entity_name",
        "abn",

        "period_start",
        "period_end",

        "report_type",

        "extra_business_industry_code",
        "extra_business_industry_code_description",
        "industry_division",

        "extra_standard_payment_terms",

        *PAYMENT_COLUMNS,

        "payment_band_has_data",

        "pct_paid_30",
        "pct_paid_31_60",
        "pct_paid_over_60",

        "estimated_avg_payment_time_days",

        "pct_paid_within_term",

        "payment_trend",
        "payment_volatility",

        "payment_term_gap",

        "industry_percentile",

        "num_reporting_periods",

        "next_period_end",
        "next_period_pct_paid_over_60",

        "high_payment_delay",
    ]

    # Defensive uniqueness.
    history_columns = list(
        dict.fromkeys(
            history_columns
        )
    )

    history_columns = [
        column
        for column in history_columns
        if column in df.columns
    ]

    history_df = df[
        history_columns
    ].copy()

    return history_df


# ============================================================
# 17. PRINT SUMMARY
# ============================================================

def print_summary(
    source_df,
    training_df,
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "FINAL SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Source rows:        {len(source_df):,}"
    )

    print(
        f"Training rows:      {len(training_df):,}"
    )

    print(
        f"Training companies: "
        f"{training_df['abn'].nunique():,}"
    )

    # --------------------------------------------------------
    # Date range.
    # --------------------------------------------------------

    if len(training_df):

        print(
            "\nTraining period:"
        )

        print(
            f"  {training_df['period_end'].min().date()}"
            f" -> "
            f"{training_df['period_end'].max().date()}"
        )

    # --------------------------------------------------------
    # Model features.
    # --------------------------------------------------------

    print(
        "\nMODEL FEATURES:"
    )

    for feature in MODEL_FEATURES:

        missing_pct = (
            training_df[
                feature
            ]
            .isna()
            .mean()
            * 100
        )

        print(
            f"  {feature:<40}"
            f" missing={missing_pct:6.2f}%"
        )

    # --------------------------------------------------------
    # Target.
    # --------------------------------------------------------

    print(
        "\nHIGH PAYMENT DELAY THRESHOLD:"
        f" {HIGH_DELAY_THRESHOLD:.1f}%"
    )

    counts = (
        training_df[
            "high_payment_delay"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nLABEL COUNTS:"
    )

    print(
        counts
    )

    print(
        "\nLABEL PERCENTAGES:"
    )

    print(
        (
            counts
            / len(training_df)
            * 100
        ).round(2)
    )

    # --------------------------------------------------------
    # Positive/negative counts.
    # --------------------------------------------------------

    positive = int(
        (
            training_df[
                "high_payment_delay"
            ]
            == 1
        )
        .sum()
    )

    negative = int(
        (
            training_df[
                "high_payment_delay"
            ]
            == 0
        )
        .sum()
    )

    print(
        f"\nPositive examples: {positive:,}"
    )

    print(
        f"Negative examples: {negative:,}"
    )

    if (
        positive == 0
        or negative == 0
    ):

        print(
            "\nWARNING:"
            "\nOnly one target class exists."
            "\nROC-AUC / binary classification training "
            "will not be valid."
        )

    print(
        "=" * 70
    )


# ============================================================
# 18. SAVE OUTPUT FILES
# ============================================================

def save_outputs(
    training_df,
    history_df,
):

    print(
        "\nSaving output files..."
    )

    training_df.to_csv(
        TRAINING_CSV,
        index=False,
    )

    training_df.to_excel(
        TRAINING_XLSX,
        index=False,
    )

    history_df.to_csv(
        HISTORY_CSV,
        index=False,
    )

    history_df.to_excel(
        HISTORY_XLSX,
        index=False,
    )

    print(
        "\nCreated:"
    )

    print(
        f"  {TRAINING_CSV}"
    )

    print(
        f"  {TRAINING_XLSX}"
    )

    print(
        f"  {HISTORY_CSV}"
    )

    print(
        f"  {HISTORY_XLSX}"
    )


# ============================================================
# 19. MAIN
# ============================================================

def main():

    # 1. Load.
    df = load_data()

    # 2. Clean.
    df = clean_data(
        df
    )

    # 3. Payment features.
    df = build_payment_features(
        df
    )

    # 4. Historical features.
    df = build_historical_features(
        df
    )

    # 5. Next-period target.
    df = build_target(
        df
    )

    # 6. Leakage/data-quality checks.
    run_checks(
        df
    )

    # 7. Training dataset.
    training_df = build_training_dataset(
        df
    )

    # 8. Company history.
    history_df = build_company_history(
        df
    )

    # 9. Summary.
    print_summary(
        df,
        training_df,
    )

    # 10. Save.
    save_outputs(
        training_df,
        history_df,
    )

    print(
        "\nSUCCESS."
    )

    print(
        "Training data is ready for the ML pipeline."
    )


# ============================================================
# 20. RUN
# ============================================================

if __name__ == "__main__":
    main()