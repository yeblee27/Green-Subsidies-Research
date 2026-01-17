import argparse
import os
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


BASE_COLUMNS = [
    "ticker",
    "year",
    "total_debt",
    "total_assets",
    "total_equity",
    "interest_expense",
    "ebit",
    "net_income",
    "total_revenue",
]

COLUMN_CANDIDATES: Dict[str, list[str]] = {
    "total_debt": [
        "total_debt",
        "total debt",
        "tot_debt",
        "debt_total",
        "bs_total_debt",
    ],
    "total_assets": [
        "total_assets",
        "total assets",
        "tot_assets",
        "bs_total_assets",
        "total asset",
    ],
    "total_equity": [
        "total_equity",
        "total equity",
        "tot_equity",
        "total stockholder equity",
        "total shareholders equity",
        "bs_total_equity",
    ],
    "interest_expense": [
        "interest_expense",
        "interest expense",
        "int_expense",
        "interest expense net",
    ],
    "ebit": [
        "ebit",
        "operating income",
        "operating_income",
        "operating profit",
    ],
    "net_income": [
        "net_income",
        "net income",
        "net income common",
        "net income applicable to common",
    ],
    "total_revenue": [
        "total_revenue",
        "total revenue",
        "revenue",
        "net revenue",
        "sales",
        "net sales",
    ],
    "environment_score": ["environment_score", "environment score"],
    "social_score": ["social_score", "social score"],
    "governance_score": ["governance_score", "governance score"],
    "esg_score": ["esg_score", "esg score", "total esg"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Bloomberg-exported financials into the pipeline schema."
    )
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--ticker-col", default="ticker")
    parser.add_argument("--year-col", default="year")
    parser.add_argument("--out-csv", default="data/processed/financials.csv")

    parser.add_argument("--total-debt-col", dest="total_debt_col")
    parser.add_argument("--total-assets-col", dest="total_assets_col")
    parser.add_argument("--total-equity-col", dest="total_equity_col")
    parser.add_argument("--interest-expense-col", dest="interest_expense_col")
    parser.add_argument("--ebit-col", dest="ebit_col")
    parser.add_argument("--net-income-col", dest="net_income_col")
    parser.add_argument("--total-revenue-col", dest="total_revenue_col")
    parser.add_argument("--environment-score-col", dest="environment_score_col")
    parser.add_argument("--social-score-col", dest="social_score_col")
    parser.add_argument("--governance-score-col", dest="governance_score_col")
    parser.add_argument("--esg-score-col", dest="esg_score_col")
    return parser.parse_args()


def read_input(path: Path, sheet: Optional[str]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        if sheet:
            return pd.read_excel(path, sheet_name=sheet)
        return pd.read_excel(path, sheet_name=0)
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def normalize_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9 ]", "", str(value).upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def match_column(
    columns: list[str],
    override: Optional[str],
    candidates: list[str],
) -> Optional[str]:
    if override:
        if override not in columns:
            raise ValueError(f"Override column '{override}' not found.")
        return override
    normalized_map = {normalize_label(col): col for col in columns}
    for candidate in candidates:
        normalized = normalize_label(candidate)
        if normalized in normalized_map:
            return normalized_map[normalized]
    return None


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    if pd.isna(numerator) or pd.isna(denominator):
        return None
    return float(numerator) / float(denominator)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_file)
    df = read_input(input_path, args.sheet)
    df.columns = [str(col).strip() for col in df.columns]

    if args.ticker_col not in df.columns:
        raise ValueError(f"Missing ticker column: {args.ticker_col}")
    if args.year_col not in df.columns:
        raise ValueError(f"Missing year column: {args.year_col}")

    resolved = {
        "total_debt": match_column(
            df.columns, args.total_debt_col, COLUMN_CANDIDATES["total_debt"]
        ),
        "total_assets": match_column(
            df.columns, args.total_assets_col, COLUMN_CANDIDATES["total_assets"]
        ),
        "total_equity": match_column(
            df.columns, args.total_equity_col, COLUMN_CANDIDATES["total_equity"]
        ),
        "interest_expense": match_column(
            df.columns,
            args.interest_expense_col,
            COLUMN_CANDIDATES["interest_expense"],
        ),
        "ebit": match_column(df.columns, args.ebit_col, COLUMN_CANDIDATES["ebit"]),
        "net_income": match_column(
            df.columns, args.net_income_col, COLUMN_CANDIDATES["net_income"]
        ),
        "total_revenue": match_column(
            df.columns, args.total_revenue_col, COLUMN_CANDIDATES["total_revenue"]
        ),
        "environment_score": match_column(
            df.columns,
            args.environment_score_col,
            COLUMN_CANDIDATES["environment_score"],
        ),
        "social_score": match_column(
            df.columns, args.social_score_col, COLUMN_CANDIDATES["social_score"]
        ),
        "governance_score": match_column(
            df.columns,
            args.governance_score_col,
            COLUMN_CANDIDATES["governance_score"],
        ),
        "esg_score": match_column(
            df.columns, args.esg_score_col, COLUMN_CANDIDATES["esg_score"]
        ),
    }

    output = pd.DataFrame(
        {
            "ticker": df[args.ticker_col],
            "year": pd.to_numeric(df[args.year_col], errors="coerce").astype("Int64"),
        }
    )

    for key in BASE_COLUMNS[2:]:
        column = resolved.get(key)
        output[key] = pd.to_numeric(df[column], errors="coerce") if column else pd.NA

    output["debt_to_equity"] = output.apply(
        lambda row: safe_divide(row["total_debt"], row["total_equity"]), axis=1
    )
    output["debt_to_assets"] = output.apply(
        lambda row: safe_divide(row["total_debt"], row["total_assets"]), axis=1
    )
    output["interest_coverage"] = output.apply(
        lambda row: safe_divide(row["ebit"], abs(row["interest_expense"]))
        if pd.notna(row["interest_expense"])
        else None,
        axis=1,
    )
    output["roa"] = output.apply(
        lambda row: safe_divide(row["net_income"], row["total_assets"]), axis=1
    )
    output["roe"] = output.apply(
        lambda row: safe_divide(row["net_income"], row["total_equity"]), axis=1
    )
    output["net_margin"] = output.apply(
        lambda row: safe_divide(row["net_income"], row["total_revenue"]), axis=1
    )

    for score_key in ("environment_score", "social_score", "governance_score", "esg_score"):
        column = resolved.get(score_key)
        if column:
            output[score_key] = pd.to_numeric(df[column], errors="coerce")

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    output.to_csv(args.out_csv, index=False)
    print(f"Wrote {len(output)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()
