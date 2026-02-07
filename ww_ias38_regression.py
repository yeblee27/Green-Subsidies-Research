#!/usr/bin/env python3
"""
Compute Whited and Wu (WW) Index, merge tax credits data,
run a linear regression against IAS 38 intangible assets,
and save a scatter plot with the regression line.
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


WW_COEFFICIENTS = {
    "cash_flow_over_assets": -0.091,
    "dividend_dummy": -0.062,
    "long_term_debt_over_assets": 0.021,
    "log_total_assets": -0.044,
    "industry_sales_growth": 0.102,
    "sales_growth": -0.035,
}

COLUMN_ALIASES = {
    "firm": [
        "firm",
        "company",
        "company_name",
        "companyname",
        "issuer",
        "entity",
        "corp",
        "corporation",
        "ticker",
        "symbol",
        "name",
    ],
    "year": [
        "year",
        "fiscalyear",
        "fiscal_year",
        "fy",
        "fyear",
        "reportyear",
        "period",
        "fiscalperiod",
    ],
    "cash_flow": [
        "cash_flow",
        "cashflow",
        "operating_cash_flow",
        "operatingcashflow",
        "ocf",
        "cfo",
        "cashflowfromoperations",
        "netcashfromoperatingactivities",
    ],
    "total_assets": [
        "total_assets",
        "totalassets",
        "totalasset",
        "assets",
    ],
    "long_term_debt": [
        "long_term_debt",
        "longtermdebt",
        "ltdebt",
        "longtermborrowings",
        "longtermliabilities",
    ],
    "dividend_dummy": [
        "dividend_dummy",
        "dividenddummy",
        "dividendpaid",
        "dividendpaidflag",
        "dividend_flag",
    ],
    "dividends_paid": [
        "dividends_paid",
        "dividends",
        "dividendspaid",
        "cashdividends",
        "dividend",
    ],
    "sales": [
        "sales",
        "revenue",
        "net_sales",
        "revenues",
        "totalrevenue",
    ],
    "sales_growth": [
        "sales_growth",
        "salesgrowth",
        "revenue_growth",
        "revenuegrowth",
        "salesgr",
    ],
    "industry": [
        "industry",
        "sector",
        "sic",
        "naics",
    ],
    "industry_sales": [
        "industry_sales",
        "industrysales",
        "industryrevenue",
    ],
    "industry_sales_growth": [
        "industry_sales_growth",
        "industrysalesgrowth",
        "industryrevenuegrowth",
    ],
    "ias38_intangible_assets": [
        "ias38_intangible_assets",
        "ias38intangibleassets",
        "intangible_assets",
        "intangibleassets",
        "intangibleasset",
        "ias38assets",
        "capitalizedrd",
        "capitalisedrd",
        "capitalizedr&d",
        "capitalisedr&d",
    ],
    "tax_credit": [
        "tax_credit",
        "taxcredit",
        "taxcredits",
        "rdtaxcredit",
        "subsidy",
        "subsidies",
        "government_grant",
        "governmentgrant",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute WW index, merge tax credits data, "
            "and regress IAS 38 intangible assets on WW index."
        )
    )
    parser.add_argument(
        "--company-file",
        default="company_financials.xlsx",
        help="Company financials Excel file.",
    )
    parser.add_argument(
        "--company-sheet",
        default=None,
        help="Company file sheet name (optional). If omitted, all sheets are merged.",
    )
    parser.add_argument(
        "--gov-file",
        default="govspending.xlsx",
        help="Government spending (tax credits) Excel file.",
    )
    parser.add_argument(
        "--gov-sheet",
        default=None,
        help="Government spending sheet name (optional).",
    )
    parser.add_argument(
        "--output-plot",
        default="ww_ias38_regression.png",
        help="Output plot filename (PNG).",
    )
    parser.add_argument(
        "--output-csv",
        default="ww_ias38_with_index.csv",
        help="Output CSV filename with computed WW index.",
    )
    parser.add_argument("--firm-col", default="firm")
    parser.add_argument("--year-col", default="year")
    parser.add_argument("--cash-flow-col", default="cash_flow")
    parser.add_argument("--total-assets-col", default="total_assets")
    parser.add_argument("--long-term-debt-col", default="long_term_debt")
    parser.add_argument("--dividend-dummy-col", default="dividend_dummy")
    parser.add_argument("--dividends-col", default="dividends_paid")
    parser.add_argument("--sales-col", default="sales")
    parser.add_argument("--sales-growth-col", default="sales_growth")
    parser.add_argument("--industry-col", default="industry")
    parser.add_argument("--industry-sales-col", default="industry_sales")
    parser.add_argument("--industry-sales-growth-col", default="industry_sales_growth")
    parser.add_argument("--ias38-col", default="ias38_intangible_assets")
    parser.add_argument("--tax-credit-col", default="tax_credit")
    return parser.parse_args()


def _normalize_col_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _build_column_map(columns: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for col in columns:
        normalized = _normalize_col_name(col)
        if normalized and normalized not in mapping:
            mapping[normalized] = col
    return mapping


def _find_column(df: pd.DataFrame, candidates: List[str]) -> str | None:
    column_map = _build_column_map(df.columns.tolist())
    for candidate in candidates:
        normalized = _normalize_col_name(candidate)
        if normalized in column_map:
            return column_map[normalized]
    return None


def _standardize_column(
    df: pd.DataFrame,
    canonical_name: str,
    aliases: List[str],
    label: str,
    required: bool = True,
) -> pd.DataFrame:
    if canonical_name in df.columns:
        return df
    found = _find_column(df, [canonical_name] + aliases)
    if found:
        df[canonical_name] = df[found]
        return df
    if required:
        available = ", ".join(df.columns)
        raise ValueError(
            f"Missing required column for {label}. Tried: "
            f"{', '.join([canonical_name] + aliases)}. "
            f"Available columns: {available}"
        )
    return df


def _ensure_key_columns(
    df: pd.DataFrame,
    firm_col: str,
    year_col: str,
    firm_fallback: str | None = None,
) -> pd.DataFrame:
    df = df.copy()
    firm_found = _find_column(df, [firm_col] + COLUMN_ALIASES["firm"])
    if firm_found:
        if firm_col not in df.columns:
            df[firm_col] = df[firm_found]
    elif firm_fallback is not None:
        df[firm_col] = firm_fallback
    else:
        available = ", ".join(df.columns)
        raise ValueError(
            f"Missing required firm column. Available columns: {available}"
        )

    year_found = _find_column(df, [year_col] + COLUMN_ALIASES["year"])
    if year_found:
        if year_col not in df.columns:
            df[year_col] = df[year_found]
    else:
        available = ", ".join(df.columns)
        raise ValueError(
            f"Missing required year column. Available columns: {available}"
        )

    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")
    return df


def _read_company_data(
    path: str,
    sheet: str | None,
    firm_col: str,
    year_col: str,
) -> pd.DataFrame:
    sheet_name = sheet if sheet else 0
    df = pd.read_excel(path, sheet_name=sheet_name)
    return _ensure_key_columns(df, firm_col, year_col)


def _read_gov_data(
    path: str,
    sheet: str | None,
    firm_col: str,
    year_col: str,
) -> pd.DataFrame:
    sheet_name = sheet if sheet else 0
    df = pd.read_excel(path, sheet_name=sheet_name)
    return _ensure_key_columns(df, firm_col, year_col)


def _maybe_compute_dividend_dummy(
    df: pd.DataFrame, dividend_dummy_col: str, dividends_col: str
) -> pd.DataFrame:
    if dividend_dummy_col in df.columns:
        return df
    if dividends_col in df.columns:
        df[dividend_dummy_col] = (df[dividends_col].fillna(0) > 0).astype(int)
        return df
    raise ValueError(
        "Missing dividend dummy. Provide either "
        f"'{dividend_dummy_col}' or '{dividends_col}'."
    )


def _maybe_compute_sales_growth(
    df: pd.DataFrame,
    sales_growth_col: str,
    sales_col: str,
    firm_col: str,
    year_col: str,
) -> pd.DataFrame:
    if sales_growth_col in df.columns:
        return df
    if sales_col not in df.columns:
        raise ValueError(
            f"Missing '{sales_growth_col}' and '{sales_col}'. "
            "Provide sales growth directly or provide sales."
        )
    if year_col not in df.columns:
        raise ValueError(f"Missing '{year_col}' for sales growth computation.")
    sort_cols = [year_col]
    if firm_col in df.columns:
        sort_cols = [firm_col, year_col]
    df = df.sort_values(sort_cols)
    if firm_col in df.columns:
        df[sales_growth_col] = df.groupby(firm_col)[sales_col].pct_change()
    else:
        df[sales_growth_col] = df[sales_col].pct_change()
    return df


def _maybe_compute_industry_sales_growth(
    df: pd.DataFrame,
    industry_sales_growth_col: str,
    industry_sales_col: str,
    industry_col: str,
    year_col: str,
) -> pd.DataFrame:
    if industry_sales_growth_col in df.columns:
        return df
    missing_cols = [
        col
        for col in (industry_sales_col, industry_col, year_col)
        if col not in df.columns
    ]
    if missing_cols:
        raise ValueError(
            "Missing industry sales growth. Provide "
            f"'{industry_sales_growth_col}' or add columns: "
            f"{', '.join(missing_cols)}."
        )
    df = df.sort_values([industry_col, year_col])
    df[industry_sales_growth_col] = (
        df.groupby(industry_col)[industry_sales_col].pct_change()
    )
    return df


def compute_ww_index(
    df: pd.DataFrame,
    cash_flow_col: str,
    total_assets_col: str,
    long_term_debt_col: str,
    dividend_dummy_col: str,
    industry_sales_growth_col: str,
    sales_growth_col: str,
) -> pd.Series:
    total_assets = df[total_assets_col].astype(float)
    total_assets = total_assets.where(total_assets > 0)

    cash_flow_over_assets = df[cash_flow_col].astype(float) / total_assets
    long_term_debt_over_assets = df[long_term_debt_col].astype(float) / total_assets
    log_total_assets = np.log(total_assets)

    ww_index = (
        WW_COEFFICIENTS["cash_flow_over_assets"] * cash_flow_over_assets
        + WW_COEFFICIENTS["dividend_dummy"] * df[dividend_dummy_col].astype(float)
        + WW_COEFFICIENTS["long_term_debt_over_assets"] * long_term_debt_over_assets
        + WW_COEFFICIENTS["log_total_assets"] * log_total_assets
        + WW_COEFFICIENTS["industry_sales_growth"]
        * df[industry_sales_growth_col].astype(float)
        + WW_COEFFICIENTS["sales_growth"] * df[sales_growth_col].astype(float)
    )
    return ww_index


def _linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    if np.allclose(x.min(), x.max()):
        raise ValueError(
            "Whited and Wu Index has no variation; regression is undefined."
        )
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot != 0 else float("nan")
    return slope, intercept, r_squared


def _merge_gov_data(
    company_df: pd.DataFrame,
    gov_df: pd.DataFrame,
    firm_col: str,
    year_col: str,
) -> pd.DataFrame:
    for col in (firm_col, year_col):
        if col not in gov_df.columns:
            raise ValueError(
                f"Government spending file missing required column '{col}'."
            )
    merged = company_df.merge(
        gov_df,
        on=[firm_col, year_col],
        how="left",
        suffixes=("", "_gov"),
    )
    return merged


def main() -> int:
    args = parse_args()

    company_df = _read_company_data(
        args.company_file, args.company_sheet, args.firm_col, args.year_col
    )
    gov_df = _read_gov_data(
        args.gov_file, args.gov_sheet, args.firm_col, args.year_col
    )

    df = _merge_gov_data(company_df, gov_df, args.firm_col, args.year_col)

    df = _standardize_column(
        df,
        args.cash_flow_col,
        COLUMN_ALIASES["cash_flow"],
        "cash flow",
    )
    df = _standardize_column(
        df,
        args.total_assets_col,
        COLUMN_ALIASES["total_assets"],
        "total assets",
    )
    df = _standardize_column(
        df,
        args.long_term_debt_col,
        COLUMN_ALIASES["long_term_debt"],
        "long-term debt",
    )
    df = _standardize_column(
        df,
        args.ias38_col,
        COLUMN_ALIASES["ias38_intangible_assets"],
        "IAS 38 intangible assets",
    )

    df = _standardize_column(
        df,
        args.dividend_dummy_col,
        COLUMN_ALIASES["dividend_dummy"],
        "dividend dummy",
        required=False,
    )
    if args.dividend_dummy_col not in df.columns:
        df = _standardize_column(
            df,
            args.dividends_col,
            COLUMN_ALIASES["dividends_paid"],
            "dividends paid",
        )
        df = _maybe_compute_dividend_dummy(
            df, args.dividend_dummy_col, args.dividends_col
        )

    df = _standardize_column(
        df,
        args.sales_growth_col,
        COLUMN_ALIASES["sales_growth"],
        "sales growth",
        required=False,
    )
    if args.sales_growth_col not in df.columns:
        df = _standardize_column(
            df,
            args.sales_col,
            COLUMN_ALIASES["sales"],
            "sales",
        )
        df = _maybe_compute_sales_growth(
            df,
            args.sales_growth_col,
            args.sales_col,
            args.firm_col,
            args.year_col,
        )

    df = _standardize_column(
        df,
        args.industry_sales_growth_col,
        COLUMN_ALIASES["industry_sales_growth"],
        "industry sales growth",
        required=False,
    )
    if args.industry_sales_growth_col not in df.columns:
        df = _standardize_column(
            df,
            args.industry_sales_col,
            COLUMN_ALIASES["industry_sales"],
            "industry sales",
        )
        df = _standardize_column(
            df,
            args.industry_col,
            COLUMN_ALIASES["industry"],
            "industry",
        )
        df = _maybe_compute_industry_sales_growth(
            df,
            args.industry_sales_growth_col,
            args.industry_sales_col,
            args.industry_col,
            args.year_col,
        )

    total_assets = df[args.total_assets_col].astype(float)
    invalid_assets = (total_assets <= 0).sum()
    if invalid_assets:
        print(
            f"Warning: {invalid_assets} rows have non-positive total_assets "
            "and will be excluded from the WW index calculation.",
            file=sys.stderr,
        )

    df["ww_index"] = compute_ww_index(
        df,
        cash_flow_col=args.cash_flow_col,
        total_assets_col=args.total_assets_col,
        long_term_debt_col=args.long_term_debt_col,
        dividend_dummy_col=args.dividend_dummy_col,
        industry_sales_growth_col=args.industry_sales_growth_col,
        sales_growth_col=args.sales_growth_col,
    )

    analysis_df = df.dropna(
        subset=[
            "ww_index",
            args.ias38_col,
            args.cash_flow_col,
            args.total_assets_col,
            args.long_term_debt_col,
            args.dividend_dummy_col,
            args.sales_growth_col,
            args.industry_sales_growth_col,
        ]
    )

    if analysis_df.empty or len(analysis_df) < 2:
        raise ValueError(
            "Not enough valid rows to run regression. "
            "Check for missing values and data coverage."
        )

    x = analysis_df["ww_index"].astype(float).to_numpy()
    y = analysis_df[args.ias38_col].astype(float).to_numpy()
    slope, intercept, r_squared = _linear_regression(x, y)

    x_line = np.linspace(x.min(), x.max(), 200)
    y_line = slope * x_line + intercept

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(x, y, alpha=0.7, edgecolors="black", linewidths=0.3)
    ax.plot(
        x_line,
        y_line,
        color="red",
        label=(
            f"y = {slope:.4f}x + {intercept:.4f}\n"
            f"R^2 = {r_squared:.4f}"
        ),
    )
    ax.set_xlabel("Whited and Wu Index")
    ax.set_ylabel("IAS 38 Intangible Assets")
    ax.set_title("IAS 38 Intangible Assets vs Whited and Wu Index")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.output_plot, dpi=300)

    df.to_csv(args.output_csv, index=False)

    print(
        "Regression results\n"
        f"Rows in input: {len(df)}\n"
        f"Rows used: {len(analysis_df)}\n"
        f"Slope: {slope:.6f}\n"
        f"Intercept: {intercept:.6f}\n"
        f"R^2: {r_squared:.6f}\n"
        f"Saved plot: {args.output_plot}\n"
        f"Saved data: {args.output_csv}"
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # CLI safeguard
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
