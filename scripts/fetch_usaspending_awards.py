import argparse
import json
import os

from green_subsidies.usaspending import (
    USASpendingClient,
    normalize_awards,
    write_awards_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch USAspending award data.")
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date", default="2020-12-31")
    parser.add_argument("--keywords", default="config/keywords.json")
    parser.add_argument(
        "--out-csv",
        default="data/raw/usaspending_awards_2015_2020.csv",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument(
        "--award-type-codes",
        nargs="*",
        default=None,
        help="Optional award type codes to filter on.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.keywords, "r", encoding="utf-8") as handle:
        keywords = json.load(handle)

    client = USASpendingClient()
    awards = client.search_awards(
        start_date=args.start_date,
        end_date=args.end_date,
        keywords=keywords,
        limit=args.limit,
        max_pages=args.max_pages,
        award_type_codes=args.award_type_codes,
    )

    awards_df = normalize_awards(awards)
    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    write_awards_csv(awards_df, args.out_csv)
    print(f"Saved {len(awards_df)} awards to {args.out_csv}")


if __name__ == "__main__":
    main()
