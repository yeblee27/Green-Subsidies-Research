# Green-Subsidies-Research

This repository contains a small analysis utility to compute the
Whited & Wu (WW) Index for financial constraints and to regress
IAS 38 intangible assets on the WW Index with a scatter plot.

## Whited & Wu Index formula

The script uses the Whited & Wu (2006) specification:

```
WW = -0.091 * (CashFlow / TotalAssets)
     -0.062 * DividendDummy
     +0.021 * (LongTermDebt / TotalAssets)
     -0.044 * ln(TotalAssets)
     +0.102 * IndustrySalesGrowth
     -0.035 * SalesGrowth
```

Where `DividendDummy` is 1 if dividends were paid in that year and 0
otherwise. Sales growth inputs are expressed as decimals (e.g., 5% = 0.05).

## Data requirements

Your input CSV should include at least the following columns (or provide
the column names via CLI options):

| Column | Description |
| --- | --- |
| `cash_flow` | Operating cash flow |
| `total_assets` | Total assets (must be positive for log) |
| `long_term_debt` | Long-term debt |
| `dividend_dummy` | 1 if dividends paid, else 0 (or provide `dividends_paid`) |
| `sales_growth` | Company sales growth (decimal), or provide `sales` |
| `industry_sales_growth` | Industry sales growth (decimal), or provide `industry_sales` |
| `ias38_intangible_assets` | IAS 38 intangible assets |

If `sales_growth` is missing and you provide `sales`, the script will
compute year-over-year growth using `firm` and `year` (if present).
If `industry_sales_growth` is missing and you provide `industry_sales`,
the script will compute industry growth using `industry` and `year`.

See `financials_template.csv` for a minimal example.

## Run the analysis

```
pip install -r requirements.txt
python ww_ias38_analysis.py --input financials.csv
```

Outputs:

- `ww_ias38_regression.png`: scatter plot with regression line
- `ww_ias38_with_index.csv`: input data with `ww_index` column added

## Column name overrides (optional)

If your dataset uses different column names, pass them via CLI flags:

```
python ww_ias38_analysis.py \
  --input financials.csv \
  --cash-flow-col ocf \
  --total-assets-col total_assets_usd \
  --ias38-col ias38_assets
```