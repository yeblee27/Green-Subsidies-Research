import json
import os
import re
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9 ]", "", str(value).upper())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def load_company_mapping(path: str) -> pd.DataFrame:
    mapping = pd.read_csv(path)
    required = {"recipient_name", "ticker", "company_name"}
    missing = required - set(mapping.columns)
    if missing:
        raise ValueError(f"Missing required columns in mapping file: {sorted(missing)}")
    mapping["recipient_name_clean"] = mapping["recipient_name"].apply(normalize_name)
    return mapping


def aggregate_awards(awards_df: pd.DataFrame) -> pd.DataFrame:
    if awards_df.empty:
        return pd.DataFrame(
            columns=["recipient_name", "fiscal_year", "subsidy_amount", "award_count"]
        )

    grouped = (
        awards_df.groupby(["recipient_name", "fiscal_year"], dropna=False)
        .agg(subsidy_amount=("award_amount", "sum"), award_count=("award_id", "count"))
        .reset_index()
    )
    return grouped


def merge_datasets(
    awards_df: pd.DataFrame,
    financials_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    awards_df = awards_df.copy()
    awards_df["recipient_name_clean"] = awards_df["recipient_name"].apply(normalize_name)
    mapping_df = mapping_df.copy()
    merged_awards = awards_df.merge(
        mapping_df,
        on="recipient_name_clean",
        how="left",
        suffixes=("", "_mapping"),
    )
    merged_awards["year"] = merged_awards["fiscal_year"].astype("Int64")

    merged = merged_awards.merge(
        financials_df,
        on=["ticker", "year"],
        how="left",
    )
    return merged


def assign_debt_group(
    df: pd.DataFrame,
    ratio_col: str = "debt_to_equity",
    quantile: float = 0.5,
) -> pd.DataFrame:
    df = df.copy()
    ratio_series = df[ratio_col].dropna()
    if ratio_series.empty:
        df["debt_group"] = pd.NA
        df["debt_threshold"] = pd.NA
        return df

    threshold = ratio_series.quantile(quantile)
    df["debt_threshold"] = threshold
    df["debt_group"] = np.where(
        df[ratio_col] <= threshold,
        "low_debt",
        "high_debt",
    )
    return df


def compute_correlation(
    df: pd.DataFrame,
    debt_col: str = "debt_to_equity",
    responsiveness_col: str = "subsidy_ratio_assets",
) -> Dict[str, Optional[float]]:
    filtered = df[[debt_col, responsiveness_col]].dropna()
    if filtered.empty:
        return {"correlation": None}
    correlation = filtered[debt_col].corr(filtered[responsiveness_col])
    return {"correlation": float(correlation)}


def plot_regression(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    out_path: str,
) -> None:
    df = df[[x_col, y_col]].dropna()
    if df.empty:
        return

    x = df[[x_col]].values
    y = df[y_col].values
    model = LinearRegression()
    model.fit(x, y)
    y_pred = model.predict(x)

    plt.figure(figsize=(8, 6))
    plt.scatter(x, y, alpha=0.7, label="Observations")
    plt.plot(x, y_pred, color="red", label="Linear fit")
    plt.title(title)
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.legend()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def write_correlation_summary(path: str, summary: Dict[str, Optional[float]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
