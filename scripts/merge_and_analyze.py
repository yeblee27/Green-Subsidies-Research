import argparse
import os

import pandas as pd

from green_subsidies.analysis import (
    aggregate_awards,
    assign_debt_group,
    compute_correlation,
    load_company_mapping,
    merge_datasets,
    plot_regression,
    write_correlation_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and analyze subsidy data.")
    parser.add_argument(
        "--awards-csv",
        default="data/raw/usaspending_awards_2015_2020.csv",
    )
    parser.add_argument("--financials-csv", default="data/processed/financials.csv")
    parser.add_argument("--mapping-csv", default="data/company_mapping.csv")
    parser.add_argument("--out-dir", default="reports")
    parser.add_argument("--debt-quantile", type=float, default=0.5)
    parser.add_argument(
        "--profitability-metric",
        default="roa",
        choices=["roa", "roe", "net_margin"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    awards_df = pd.read_csv(args.awards_csv)
    financials_df = pd.read_csv(args.financials_csv)
    mapping_df = load_company_mapping(args.mapping_csv)

    awards_grouped = aggregate_awards(awards_df)
    merged = merge_datasets(awards_grouped, financials_df, mapping_df)
    merged["subsidy_ratio_assets"] = merged["subsidy_amount"] / merged["total_assets"]
    merged = assign_debt_group(
        merged,
        ratio_col="debt_to_equity",
        quantile=args.debt_quantile,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    summary_path = os.path.join(args.out_dir, "summary_metrics.csv")
    merged.to_csv(summary_path, index=False)

    correlation_summary = compute_correlation(
        merged,
        debt_col="debt_to_equity",
        responsiveness_col="subsidy_ratio_assets",
    )
    correlation_path = os.path.join(args.out_dir, "correlation_summary.json")
    write_correlation_summary(correlation_path, correlation_summary)

    figures_dir = os.path.join(args.out_dir, "figures")
    plot_regression(
        merged[merged["debt_group"] == "low_debt"],
        x_col="subsidy_amount",
        y_col=args.profitability_metric,
        title="Low-debt: Subsidies vs Profitability",
        out_path=os.path.join(
            figures_dir,
            "low_debt_subsidy_vs_profitability.png",
        ),
    )
    plot_regression(
        merged[merged["debt_group"] == "high_debt"],
        x_col="subsidy_amount",
        y_col=args.profitability_metric,
        title="High-debt: Subsidies vs Profitability",
        out_path=os.path.join(
            figures_dir,
            "high_debt_subsidy_vs_profitability.png",
        ),
    )

    print(f"Wrote summary metrics to {summary_path}")
    print(f"Wrote correlation summary to {correlation_path}")


if __name__ == "__main__":
    main()
