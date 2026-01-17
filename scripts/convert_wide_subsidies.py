import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a firm-year subsidy table into the pipeline CSV schema."
    )
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--recipient-col", default="recipient_name")
    parser.add_argument("--ticker-col", default="ticker")
    parser.add_argument("--company-col", default="company_name")
    parser.add_argument(
        "--year-cols",
        nargs="*",
        default=None,
        help="Optional list of year columns (e.g., 2015 2016 2017).",
    )
    parser.add_argument(
        "--out-csv",
        default="data/raw/usaspending_awards_2015_2020.csv",
    )
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


def normalize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "-", str(value).upper()).strip("-")
    return cleaned or "UNKNOWN"


def detect_year_columns(columns: List[str]) -> Dict[str, int]:
    year_map: Dict[str, int] = {}
    for column in columns:
        value = str(column).strip()
        match = re.fullmatch(r"(?:FY)?(\d{4})", value, flags=re.IGNORECASE)
        if match:
            year_map[column] = int(match.group(1))
    return year_map


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_file)
    df = read_input(input_path, args.sheet)
    df.columns = [str(col).strip() for col in df.columns]

    recipient_col = args.recipient_col
    ticker_col = args.ticker_col
    company_col = args.company_col

    if recipient_col not in df.columns:
        raise ValueError(f"Missing recipient column: {recipient_col}")

    if args.year_cols:
        year_columns = args.year_cols
        year_map = {col: int(re.sub(r"\D", "", col)) for col in year_columns}
    else:
        year_map = detect_year_columns(df.columns)
        year_columns = list(year_map.keys())

    if not year_columns:
        raise ValueError("No year columns detected. Provide --year-cols explicitly.")

    id_columns = [recipient_col]
    for optional_col in (ticker_col, company_col):
        if optional_col in df.columns:
            id_columns.append(optional_col)

    melted = df.melt(
        id_vars=id_columns,
        value_vars=year_columns,
        var_name="fiscal_year",
        value_name="award_amount",
    )
    melted["fiscal_year"] = melted["fiscal_year"].map(year_map).astype("Int64")
    melted["award_amount"] = pd.to_numeric(melted["award_amount"], errors="coerce")

    if ticker_col in melted.columns:
        id_source = melted[ticker_col].fillna(melted[recipient_col])
    else:
        id_source = melted[recipient_col]

    melted["award_id"] = id_source.apply(normalize_identifier) + "_" + melted[
        "fiscal_year"
    ].astype(str)
    output = melted[["award_id", recipient_col, "award_amount", "fiscal_year"]].rename(
        columns={recipient_col: "recipient_name"}
    )
    output = output.dropna(subset=["recipient_name", "award_amount", "fiscal_year"])

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    output.to_csv(args.out_csv, index=False)
    print(f"Wrote {len(output)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()
