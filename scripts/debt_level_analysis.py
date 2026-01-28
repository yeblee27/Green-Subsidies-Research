#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_LOW_MAX = 20.0
DEFAULT_MEDIUM_MAX = 40.0


def normalize_column_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return normalized.strip("_")


def build_column_index(columns: Iterable[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for column in columns:
        index[normalize_column_name(column)] = column
    return index


def find_ratio_column(columns: Iterable[str]) -> str | None:
    index = build_column_index(columns)
    preferred = [
        "debt_to_a",
        "debt_to_assets",
        "debt_to_asset",
        "debt_to_total_assets",
        "debt_to_total_asset",
        "debt_to_assets_ratio",
        "debt_to_asset_ratio",
    ]
    for key in preferred:
        if key in index:
            return index[key]

    for normalized, original in index.items():
        if "debt_to" in normalized and ("asset" in normalized or normalized.endswith("_a")):
            return original
    return None


def find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    index = build_column_index(columns)
    for candidate in candidates:
        normalized = normalize_column_name(candidate)
        if normalized in index:
            return index[normalized]
    return None


def coerce_numeric(series: pd.Series) -> pd.Series:
    if series.dtype.kind in "biufc":
        return series

    cleaned = (
        series.astype(str)
        .str.strip()
        .replace({"": pd.NA, "-": pd.NA, "nan": pd.NA, "None": pd.NA})
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace(r"\(([^)]*)\)", r"-\1", regex=True)
        .str.replace("%", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def pick_company_group_columns(columns: Iterable[str]) -> list[str]:
    column_set = set(columns)
    if "ticker" in column_set and "company_name" in column_set:
        return ["ticker", "company_name"]
    if "ticker" in column_set:
        return ["ticker"]
    if "company_name" in column_set:
        return ["company_name"]
    if "recipient_name" in column_set:
        return ["recipient_name"]
    return []


def format_value(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 15) -> str:
    if df.empty:
        return "_No rows available._"

    preview = df.head(max_rows).copy()
    columns = list(preview.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in preview.itertuples(index=False):
        lines.append("| " + " | ".join(format_value(value) for value in row) + " |")
    if len(df) > max_rows:
        lines.append(f"_Showing first {max_rows} rows of {len(df)}._")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Categorize companies by debt level from an Excel file."
    )
    parser.add_argument(
        "--input",
        default="data/raw/final_list.xlsx",
        help="Path to input Excel file (default: data/raw/final_list.xlsx).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for processed outputs (default: data/processed).",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory for summary reports (default: reports).",
    )
    parser.add_argument(
        "--ratio-column",
        default=None,
        help="Override the debt-to-assets ratio column if auto-detection fails.",
    )
    parser.add_argument(
        "--low-max",
        type=float,
        default=DEFAULT_LOW_MAX,
        help="Upper threshold for Low debt level (default: 20).",
    )
    parser.add_argument(
        "--medium-max",
        type=float,
        default=DEFAULT_MEDIUM_MAX,
        help="Upper threshold for Moderate debt level (default: 40).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(
            f"Input file not found: {input_path}. "
            "Place your Excel file at data/raw/final_list.xlsx or pass --input."
        )

    df = pd.read_excel(input_path)
    df.columns = [column.strip() for column in df.columns]

    ratio_column = args.ratio_column
    if ratio_column:
        if ratio_column not in df.columns:
            normalized_index = build_column_index(df.columns)
            normalized = normalize_column_name(ratio_column)
            ratio_column = normalized_index.get(normalized)
        if ratio_column is None:
            raise SystemExit(
                f"Ratio column '{args.ratio_column}' not found in input file."
            )
    else:
        ratio_column = find_ratio_column(df.columns)

    ratio_series: pd.Series | None = None
    ratio_source = "provided"
    if ratio_column:
        ratio_series = coerce_numeric(df[ratio_column])
    else:
        long_term_col = find_column(df.columns, ["long_term_debt", "long-term debt"])
        short_term_col = find_column(df.columns, ["short_term_debt", "short-term debt"])
        assets_col = find_column(df.columns, ["total_assets", "total_asset", "assets"])
        if long_term_col and short_term_col and assets_col:
            long_term = coerce_numeric(df[long_term_col])
            short_term = coerce_numeric(df[short_term_col])
            assets = coerce_numeric(df[assets_col])
            ratio_series = (long_term.fillna(0) + short_term.fillna(0)) / assets
            ratio_source = "calculated"
            ratio_column = "debt_to_assets_calculated"
        else:
            available = ", ".join(df.columns)
            raise SystemExit(
                "Could not detect a debt-to-assets ratio column. "
                "Provide --ratio-column or include long/short-term debt and assets columns. "
                f"Available columns: {available}"
            )

    ratio_series = ratio_series.copy()
    ratio_scale = "percent"
    if ratio_series.dropna().max() <= 1.5:
        ratio_series = ratio_series * 100
        ratio_scale = "fraction_to_percent"

    df["debt_to_assets_pct"] = ratio_series
    if ratio_source == "calculated":
        df[ratio_column] = ratio_series

    def categorize(value: float) -> str:
        if pd.isna(value):
            return "Unknown"
        if value < args.low_max:
            return "Low"
        if value < args.medium_max:
            return "Moderate"
        return "High"

    df["debt_level"] = df["debt_to_assets_pct"].apply(categorize)

    summary_overall = pd.DataFrame(
        [
            {
                "rows": len(df),
                "ratio_column": ratio_column,
                "ratio_scale": ratio_scale,
                "low_max": args.low_max,
                "medium_max": args.medium_max,
                "debt_to_assets_pct_mean": df["debt_to_assets_pct"].mean(),
                "debt_to_assets_pct_median": df["debt_to_assets_pct"].median(),
            }
        ]
    )

    debt_level_summary = (
        df.groupby("debt_level", dropna=False)["debt_to_assets_pct"]
        .agg(["count", "mean", "median", "min", "max"])
        .reset_index()
        .sort_values("count", ascending=False)
    )

    company_summary = pd.DataFrame()
    company_level_counts = pd.DataFrame()
    company_group_cols = pick_company_group_columns(df.columns)
    if company_group_cols:
        company_summary = (
            df.groupby(company_group_cols)["debt_to_assets_pct"]
            .agg(["count", "mean", "median"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )
        company_level_counts = (
            df.pivot_table(
                index=company_group_cols,
                columns="debt_level",
                values="debt_to_assets_pct",
                aggfunc="size",
                fill_value=0,
            )
            .reset_index()
            .sort_values(company_group_cols)
        )

    year_summary = pd.DataFrame()
    year_level_counts = pd.DataFrame()
    if "year" in df.columns:
        year_summary = (
            df.groupby("year")["debt_to_assets_pct"]
            .agg(["count", "mean", "median"])
            .reset_index()
            .sort_values("year")
        )
        year_level_counts = (
            df.pivot_table(
                index="year",
                columns="debt_level",
                values="debt_to_assets_pct",
                aggfunc="size",
                fill_value=0,
            )
            .reset_index()
            .sort_values("year")
        )

    preview_columns = [
        column
        for column in [
            "recipient_name",
            "ticker",
            "company_name",
            "year",
            "debt_to_assets_pct",
            "debt_level",
        ]
        if column in df.columns
    ]
    highest_debt = (
        df[preview_columns]
        .sort_values("debt_to_assets_pct", ascending=False)
        .head(10)
        if preview_columns
        else pd.DataFrame()
    )
    lowest_debt = (
        df[preview_columns]
        .sort_values("debt_to_assets_pct", ascending=True)
        .head(10)
        if preview_columns
        else pd.DataFrame()
    )

    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    output_excel = output_dir / f"{input_path.stem}_with_debt_level.xlsx"
    output_csv = output_dir / f"{input_path.stem}_with_debt_level.csv"
    df.to_excel(output_excel, index=False)
    df.to_csv(output_csv, index=False)

    summary_excel = report_dir / "debt_level_summary.xlsx"
    with pd.ExcelWriter(summary_excel, engine="openpyxl") as writer:
        summary_overall.to_excel(writer, sheet_name="overall", index=False)
        debt_level_summary.to_excel(writer, sheet_name="debt_level", index=False)
        if not company_summary.empty:
            company_summary.to_excel(writer, sheet_name="company_summary", index=False)
        if not company_level_counts.empty:
            company_level_counts.to_excel(
                writer, sheet_name="company_level_counts", index=False
            )
        if not year_summary.empty:
            year_summary.to_excel(writer, sheet_name="year_summary", index=False)
        if not year_level_counts.empty:
            year_level_counts.to_excel(
                writer, sheet_name="year_level_counts", index=False
            )
        if not highest_debt.empty:
            highest_debt.to_excel(writer, sheet_name="highest_debt", index=False)
        if not lowest_debt.empty:
            lowest_debt.to_excel(writer, sheet_name="lowest_debt", index=False)

    summary_md = report_dir / "debt_level_summary.md"
    with summary_md.open("w", encoding="utf-8") as handle:
        handle.write("# Debt level summary\n\n")
        handle.write("## Overall\n")
        handle.write(dataframe_to_markdown(summary_overall))
        handle.write("\n\n## Debt level distribution\n")
        handle.write(dataframe_to_markdown(debt_level_summary))
        if not company_summary.empty:
            handle.write("\n\n## Company summary (avg debt ratio)\n")
            handle.write(dataframe_to_markdown(company_summary))
        if not company_level_counts.empty:
            handle.write("\n\n## Company counts by debt level\n")
            handle.write(dataframe_to_markdown(company_level_counts))
        if not year_summary.empty:
            handle.write("\n\n## Year summary\n")
            handle.write(dataframe_to_markdown(year_summary))
        if not year_level_counts.empty:
            handle.write("\n\n## Year counts by debt level\n")
            handle.write(dataframe_to_markdown(year_level_counts))
        if not highest_debt.empty:
            handle.write("\n\n## Highest debt-to-assets entries\n")
            handle.write(dataframe_to_markdown(highest_debt))
        if not lowest_debt.empty:
            handle.write("\n\n## Lowest debt-to-assets entries\n")
            handle.write(dataframe_to_markdown(lowest_debt))

    print("Saved processed data to:")
    print(f"- {output_excel}")
    print(f"- {output_csv}")
    print("Saved summary reports to:")
    print(f"- {summary_excel}")
    print(f"- {summary_md}")


if __name__ == "__main__":
    main()
