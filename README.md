# Green-Subsidies-Research

This repo includes a small utility to categorize companies by debt level from
an Excel file and generate summary reports.

## Debt level categorization

The script expects your final Excel file at:

```
data/raw/final_list.xlsx
```

Run the analysis:

```
python3 -m pip install -r requirements.txt
python3 scripts/debt_level_analysis.py
```

### Outputs

The script writes:

- `data/processed/final_list_with_debt_level.xlsx`
- `data/processed/final_list_with_debt_level.csv`
- `reports/debt_level_summary.xlsx`
- `reports/debt_level_summary.md`

### Notes

- The script auto-detects a debt-to-assets column (e.g. `debt_to_a`).
- If the ratio column is missing, you can provide one with `--ratio-column`.
- Default debt level thresholds are:
  - Low: < 20
  - Moderate: 20 to < 40
  - High: >= 40