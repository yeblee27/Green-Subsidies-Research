import argparse
import os

import pandas as pd

from green_subsidies.finance import build_financials_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Yahoo Finance metrics.")
    parser.add_argument("--mapping-csv", default="data/company_mapping.csv")
    parser.add_argument("--out-csv", default="data/processed/financials.csv")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2020)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapping_df = pd.read_csv(args.mapping_csv)
    financials_df = build_financials_dataset(
        mapping_df,
        start_year=args.start_year,
        end_year=args.end_year,
    )

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    financials_df.to_csv(args.out_csv, index=False)
    print(f"Saved financials to {args.out_csv}")


if __name__ == "__main__":
    main()
