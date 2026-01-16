import argparse
import os

from green_subsidies.usaspending_sql import export_awards_to_csv, load_keywords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export USAspending awards from a PostgreSQL archive."
    )
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date", default="2020-12-31")
    parser.add_argument("--keywords", default="config/keywords.json")
    parser.add_argument("--no-keywords", action="store_true")
    parser.add_argument(
        "--out-csv",
        default="data/raw/usaspending_awards_2015_2020.csv",
    )
    parser.add_argument("--table", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--keyword-cols",
        default=None,
        help="Comma-separated list of keyword columns or target fields.",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    keywords = [] if args.no_keywords else load_keywords(args.keywords)

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)

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

    result = export_awards_to_csv(
        db_url=args.db_url,
        start_date=args.start_date,
        end_date=args.end_date,
        keywords=keywords,
        output_path=args.out_csv,
        table_override=args.table,
        column_overrides=column_overrides,
        keyword_cols_override=args.keyword_cols,
        limit=args.limit,
    )

    print(f"Exported awards to {args.out_csv}")
    print(f"Source table: {result['table']}")
    print("Resolved columns:")
    for key, value in result["resolved_columns"].items():
        print(f"  {key}: {value}")
    if keywords and not result["keyword_columns"]:
        print(
            "Warning: no keyword columns resolved; keyword filter was not applied."
        )


if __name__ == "__main__":
    main()
