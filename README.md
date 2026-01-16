# Green-Subsidies-Research

## Research goal
Answer:
1) How do firms with different debt levels respond to the government’s green subsidies?
2) What behavioral factors contribute to corporate decision-making when allocating discretionary funds?

This repo provides a reproducible pipeline to:
- Pull 2015–2020 green-subsidy award data from USAspending.gov.
- Fetch 2015–2020 financials from Yahoo Finance to compute debt metrics.
- Categorize firms by debt level, compare profitability and environmental performance, and
  estimate correlations and linear regressions for low- vs high-debt groups.

## Data sources
- **USAspending.gov API**: Award-level data filtered by keywords and time range.
- **Yahoo Finance (yfinance)**: Balance sheet, income statement, and ESG data.

If you have access to the full USAspending PostgreSQL archive, you can swap in a SQL
extract using the same output schema as the scripts below.

## Quick start
1. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`

2. Create the company mapping file:
   - `data/company_mapping.csv`
   - Required columns: `recipient_name`, `ticker`, `company_name`
   - `recipient_name` should match the USAspending recipient string as closely as possible.

3. Fetch USAspending awards (2015–2020 by default):
   - API path (default):
     - `python -m scripts.fetch_usaspending_awards --start-date 2015-01-01 --end-date 2020-12-31 --keywords config/keywords.json`
   - Excel downloads path (if you exported FY files from USAspending.gov):
     - Place `FY2015.xlsx` ... `FY2020.xlsx` in `data/raw/`
     - `python -m scripts.convert_usaspending_excel --input-dir data/raw --pattern "FY*.xlsx" --out-csv data/raw/usaspending_awards_2015_2020.csv`
     - If your downloads are CSV, use `--pattern "FY*.csv"` instead.
   - PostgreSQL archive path (if API is blocked or you restored the full DB):
     - Restore the USAspending archive per their guide (requires large disk and time).
     - `python -m scripts.export_usaspending_sql --db-url postgresql://root:password@127.0.0.1:5432/data_store_api --start-date 2015-01-01 --end-date 2020-12-31 --keywords config/keywords.json --out-csv data/raw/usaspending_awards_2015_2020.csv`
     - If the script cannot find the `award_search` view, pass `--table` and column overrides to match your schema.

4. Fetch Yahoo Finance financials:
   - `python scripts/fetch_financials.py --mapping-csv data/company_mapping.csv --out-csv data/processed/financials.csv --start-year 2015 --end-year 2020`

5. Merge and analyze:
   - `python scripts/merge_and_analyze.py --awards-csv data/raw/usaspending_awards_2015_2020.csv --financials-csv data/processed/financials.csv --out-dir reports`

Outputs:
- `reports/summary_metrics.csv`: Debt metrics, profitability, ESG scores, subsidy totals.
- `reports/correlation_summary.json`: Correlation between debt level and subsidy responsiveness.
- `reports/figures/low_debt_subsidy_vs_profitability.png`
- `reports/figures/high_debt_subsidy_vs_profitability.png`

## Method notes
- **Debt level**: Defaults to the median `debt_to_equity` across the merged dataset. You can
  change the threshold via `--debt-quantile` in `scripts/merge_and_analyze.py`.
- **Profitability**: Defaults to `roa` (net income / total assets). You can switch to `roe`
  or `net_margin` via `--profitability-metric`.
- **Environmental performance**: Uses Yahoo Finance ESG scores when available. You can
  replace this with EPA/CDP metrics if you have access.
- **USAspending SQL export**: Defaults to pulling from `award_search` and uses the closest
  available columns for `award_amount` and other fields. Override column mappings if needed.

## Behavioral factors (qualitative layer)
For behavioral drivers, the quantitative pipeline can be augmented with:
- Investor pressure (e.g., ESG fund ownership).
- Regulatory exposure (industry NAICS codes, policy changes).
- Managerial incentives (proxy statements, compensation structures).
- Capital constraints (credit ratings, refinancing events).

These can be added as additional covariates in `scripts/merge_and_analyze.py` once
your data sources are identified.