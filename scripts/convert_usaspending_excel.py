import argparse
import datetime as dt
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from green_subsidies.usaspending import compute_fiscal_year

OUTPUT_FIELDS = [
    "award_id",
    "recipient_name",
    "award_amount",
    "awarding_agency",
    "action_date",
    "award_type",
    "cfda_number",
    "naics_code",
    "award_description",
    "business_categories",
    "pop_zip",
    "fiscal_year",
]

COLUMN_CANDIDATES: Dict[str, List[str]] = {
    "award_id": [
        "Award ID",
        "Award Identifier",
        "Generated Unique Award ID",
        "Award ID (FAIN)",
    ],
    "recipient_name": [
        "Recipient Name",
        "Recipient",
        "Legal Business Name",
    ],
    "award_amount": [
        "Award Amount",
        "Total Award Amount",
        "Total Obligated Amount",
        "Federal Action Obligation",
        "Action Obligation",
    ],
    "awarding_agency": [
        "Awarding Agency",
        "Awarding Agency Name",
        "Awarding Agency Code",
        "Funding Agency",
    ],
    "action_date": [
        "Action Date",
        "Last Action Date",
        "Date Signed",
    ],
    "award_type": [
        "Award Type",
        "Award Type Code",
    ],
    "cfda_number": [
        "CFDA Number",
        "CFDA",
        "CFDA Numbers",
    ],
    "naics_code": [
        "NAICS Code",
        "NAICS",
    ],
    "award_description": [
        "Award Description",
        "Description",
    ],
    "business_categories": [
        "Business Categories",
        "Business Category",
    ],
    "pop_zip": [
        "Place of Performance ZIP Code",
        "Place of Performance ZIP",
        "Place of Performance ZIP5",
        "POP ZIP",
    ],
    "fiscal_year": [
        "Fiscal Year",
        "FY",
        "Action Date Fiscal Year",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert USAspending Excel/CSV downloads into the pipeline CSV schema."
    )
    parser.add_argument("--input-dir", default="data/raw")
    parser.add_argument("--pattern", default="FY*.xlsx")
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument("--sheet", default=None)
    parser.add_argument(
        "--out-csv",
        default="data/raw/usaspending_awards_2015_2020.csv",
    )
    parser.add_argument("--award-id-col", dest="award_id_col")
    parser.add_argument("--recipient-name-col", dest="recipient_name_col")
    parser.add_argument("--award-amount-col", dest="award_amount_col")
    parser.add_argument("--awarding-agency-col", dest="awarding_agency_col")
    parser.add_argument("--action-date-col", dest="action_date_col")
    parser.add_argument("--award-type-col", dest="award_type_col")
    parser.add_argument("--cfda-number-col", dest="cfda_number_col")
    parser.add_argument("--naics-code-col", dest="naics_code_col")
    parser.add_argument("--award-description-col", dest="award_description_col")
    parser.add_argument("--business-categories-col", dest="business_categories_col")
    parser.add_argument("--pop-zip-col", dest="pop_zip_col")
    parser.add_argument("--fiscal-year-col", dest="fiscal_year_col")
    parser.add_argument(
        "--year-from-filename",
        action="store_true",
        help="Use FY#### in filename when fiscal year is missing.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=None,
        help="Rows per chunk when reading large CSV files.",
    )
    return parser.parse_args()


def normalize_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9 ]", "", str(value).upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def resolve_columns(
    columns: Sequence[str],
    overrides: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    normalized_map = {normalize_label(column): column for column in columns}
    resolved: Dict[str, Optional[str]] = {}

    for field, candidates in COLUMN_CANDIDATES.items():
        override = overrides.get(field)
        if override:
            if override not in columns:
                raise ValueError(f"Override column '{override}' not found.")
            resolved[field] = override
            continue

        resolved[field] = None
        for candidate in candidates:
            normalized = normalize_label(candidate)
            if normalized in normalized_map:
                resolved[field] = normalized_map[normalized]
                break

    missing_required = [
        field
        for field in ("award_id", "recipient_name", "award_amount")
        if not resolved[field]
    ]
    if not resolved["action_date"] and not resolved["fiscal_year"]:
        missing_required.append("action_date or fiscal_year")

    if missing_required:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_required)
            + ". Available columns: "
            + ", ".join(columns)
        )

    return resolved


def extract_year_from_filename(path: Path) -> Optional[int]:
    match = re.search(r"FY(\d{4})", path.stem.upper())
    if match:
        return int(match.group(1))
    return None


def build_standard_frame(
    df: pd.DataFrame,
    resolved: Dict[str, Optional[str]],
    filename_year: Optional[int],
) -> pd.DataFrame:
    action_date_col = resolved.get("action_date")
    fiscal_year_col = resolved.get("fiscal_year")

    if action_date_col:
        action_date = pd.to_datetime(df[action_date_col], errors="coerce").dt.date
    else:
        action_date = pd.Series([pd.NA] * len(df))

    if fiscal_year_col:
        fiscal_year = pd.to_numeric(df[fiscal_year_col], errors="coerce").astype("Int64")
    elif action_date_col:
        fiscal_year = action_date.apply(
            lambda date_value: compute_fiscal_year(date_value)
            if isinstance(date_value, dt.date)
            else pd.NA
        ).astype("Int64")
    elif filename_year is not None:
        fiscal_year = pd.Series([filename_year] * len(df), dtype="Int64")
    else:
        fiscal_year = pd.Series([pd.NA] * len(df), dtype="Int64")

    output = pd.DataFrame(
        {
            "award_id": df[resolved["award_id"]],
            "recipient_name": df[resolved["recipient_name"]],
            "award_amount": pd.to_numeric(
                df[resolved["award_amount"]], errors="coerce"
            ),
            "awarding_agency": df[resolved["awarding_agency"]]
            if resolved["awarding_agency"]
            else pd.NA,
            "action_date": action_date,
            "award_type": df[resolved["award_type"]] if resolved["award_type"] else pd.NA,
            "cfda_number": df[resolved["cfda_number"]]
            if resolved["cfda_number"]
            else pd.NA,
            "naics_code": df[resolved["naics_code"]]
            if resolved["naics_code"]
            else pd.NA,
            "award_description": df[resolved["award_description"]]
            if resolved["award_description"]
            else pd.NA,
            "business_categories": df[resolved["business_categories"]]
            if resolved["business_categories"]
            else pd.NA,
            "pop_zip": df[resolved["pop_zip"]] if resolved["pop_zip"] else pd.NA,
            "fiscal_year": fiscal_year,
        }
    )
    return output


def read_excel_source(path: Path, sheet: Optional[str]) -> pd.DataFrame:
    if sheet:
        return pd.read_excel(path, sheet_name=sheet)
    return pd.read_excel(path, sheet_name=0)


def resolve_chunksize(path: Path, requested: Optional[int]) -> Optional[int]:
    if requested is not None:
        return requested if requested > 0 else None
    try:
        size_bytes = path.stat().st_size
    except OSError:
        return None
    if size_bytes >= 200 * 1024 * 1024:
        return 200_000
    return None


def build_usecols(resolved: Dict[str, Optional[str]]) -> List[str]:
    cols = [value for value in resolved.values() if value]
    return sorted(set(cols))


def resolve_input_files(input_dir: str, pattern: str, files: Optional[List[str]]) -> List[Path]:
    if files:
        return [Path(file_path) for file_path in files]
    return sorted(Path(input_dir).glob(pattern))


def main() -> None:
    args = parse_args()
    input_files = resolve_input_files(args.input_dir, args.pattern, args.files)
    if not input_files:
        raise ValueError("No input files found. Check --input-dir/--pattern.")

    column_overrides = {
        "award_id": args.award_id_col,
        "recipient_name": args.recipient_name_col,
        "award_amount": args.award_amount_col,
        "awarding_agency": args.awarding_agency_col,
        "action_date": args.action_date_col,
        "award_type": args.award_type_col,
        "cfda_number": args.cfda_number_col,
        "naics_code": args.naics_code_col,
        "award_description": args.award_description_col,
        "business_categories": args.business_categories_col,
        "pop_zip": args.pop_zip_col,
        "fiscal_year": args.fiscal_year_col,
    }

    wrote_header = False
    total_rows = 0
    for path in input_files:
        suffix = path.suffix.lower()
        filename_year = extract_year_from_filename(path) if args.year_from_filename else None

        if suffix in {".xlsx", ".xls"}:
            df = read_excel_source(path, args.sheet)
            df.columns = [str(col).strip() for col in df.columns]
            resolved = resolve_columns(df.columns, column_overrides)
            standard = build_standard_frame(df, resolved, filename_year)
            os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
            standard.to_csv(
                args.out_csv,
                index=False,
                mode="a" if wrote_header else "w",
                header=not wrote_header,
            )
            wrote_header = True
            total_rows += len(standard)
            continue

        if suffix == ".csv":
            header_df = pd.read_csv(path, nrows=0)
            header_df.columns = [str(col).strip() for col in header_df.columns]
            resolved = resolve_columns(header_df.columns, column_overrides)
            usecols = build_usecols(resolved)
            chunk_size = resolve_chunksize(path, args.chunksize)
            os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)

            if chunk_size:
                for chunk in pd.read_csv(
                    path,
                    usecols=usecols,
                    chunksize=chunk_size,
                    low_memory=False,
                ):
                    chunk.columns = [str(col).strip() for col in chunk.columns]
                    standard = build_standard_frame(chunk, resolved, filename_year)
                    standard.to_csv(
                        args.out_csv,
                        index=False,
                        mode="a" if wrote_header else "w",
                        header=not wrote_header,
                    )
                    wrote_header = True
                    total_rows += len(standard)
            else:
                df = pd.read_csv(path, usecols=usecols, low_memory=False)
                df.columns = [str(col).strip() for col in df.columns]
                standard = build_standard_frame(df, resolved, filename_year)
                standard.to_csv(
                    args.out_csv,
                    index=False,
                    mode="a" if wrote_header else "w",
                    header=not wrote_header,
                )
                wrote_header = True
                total_rows += len(standard)
            continue

        raise ValueError(f"Unsupported file type: {path.suffix}")

    print(f"Wrote {total_rows} rows to {args.out_csv}")
    print(f"Processed {len(input_files)} files.")


if __name__ == "__main__":
    main()
