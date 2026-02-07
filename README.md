# Green-Subsidies-Research

This project computes the Whited and Wu (WW) Index for financial constraints
and runs a linear regression of IAS 38 intangible assets on the WW Index.
It reads two Excel or CSV files:

- `company_financials.xlsx` (or `.csv`)
- `govspending.xlsx` (or `.csv`)

The output includes a scatter plot with the fitted regression line and a CSV
with the computed WW index.

## Whited and Wu (WW) Index

The script uses the Whited and Wu (2006) specification:

```
WW = -0.091 * (CashFlow / TotalAssets)
     -0.062 * DividendDummy
     +0.021 * (LongTermDebt / TotalAssets)
     -0.044 * ln(TotalAssets)
     +0.102 * IndustrySalesGrowth
     -0.035 * SalesGrowth
```

## Data requirements

### company_financials.xlsx / company_financials.csv

Required columns (default names):

- `firm`
- `year`
- `cash_flow`
- `total_assets` (must be positive for log)
- `long_term_debt`
- `dividend_dummy` (or `dividends_paid`)
- `sales_growth` (or `sales`)
- `industry_sales_growth` (or `industry_sales`)
- `industry` (required if computing industry sales growth)
- `ias38_intangible_assets`

### govspending.xlsx / govspending.csv

Required columns (default names):

- `firm`
- `year`
- `tax_credit` (optional in analysis; kept for output)

The two files are merged on `firm` and `year`. If `govspending.xlsx` contains
other columns, they will also be merged into the output CSV.

If your company Excel workbook has multiple sheets, the script merges all
sheets by default and uses the sheet name as the `firm` value when the firm
column is missing. You can also target a single sheet with `--company-sheet`.

## Install and run

```
pip install -r requirements.txt
python ww_ias38_regression.py
```

## Optional column name overrides

If your dataset uses different column names, pass them via flags. The script
also attempts common column aliases automatically.

```
python ww_ias38_regression.py \
  --company-file company_financials.xlsx \
  --gov-file govspending.xlsx \
  --cash-flow-col operating_cash_flow \
  --total-assets-col total_assets_usd \
  --ias38-col ias38_assets
```

To use specific sheets:

```
python ww_ias38_regression.py \
  --company-file company_financials.xlsx \
  --company-sheet "Sheet1" \
  --gov-file govspending.xlsx \
  --gov-sheet "TaxCredits"
```
