from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

BALANCE_KEYS = {
    "total_assets": ["Total Assets"],
    "total_equity": [
        "Total Stockholder Equity",
        "Total Equity Gross Minority Interest",
    ],
    "total_debt": ["Total Debt"],
    "short_term_debt": ["Short Long Term Debt", "Short Term Debt"],
    "long_term_debt": ["Long Term Debt", "Long Term Debt Noncurrent"],
}

INCOME_KEYS = {
    "interest_expense": [
        "Interest Expense",
        "Interest Expense Non Operating",
    ],
    "ebit": ["Ebit", "EBIT"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "total_revenue": ["Total Revenue"],
}

ESG_KEYS = {
    "environment_score": "environmentScore",
    "social_score": "socialScore",
    "governance_score": "governanceScore",
    "esg_score": "totalEsg",
}


def _extract_series(statement: pd.DataFrame, keys: Iterable[str]) -> pd.Series:
    if statement is None or statement.empty:
        return pd.Series(dtype="float64")

    statement = statement.copy()
    statement.index = statement.index.astype(str)
    for key in keys:
        if key in statement.index:
            return statement.loc[key]

    return pd.Series(dtype="float64")


def _series_to_year_map(series: pd.Series) -> Dict[int, float]:
    if series is None or series.empty:
        return {}

    output: Dict[int, float] = {}
    for period, value in series.items():
        if pd.isna(value):
            continue
        year = pd.to_datetime(period, errors="coerce").year
        if pd.isna(year):
            continue
        output[int(year)] = float(value)
    return output


def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0, np.nan):
        return None
    if pd.isna(numerator) or pd.isna(denominator):
        return None
    return float(numerator) / float(denominator)


def _extract_esg_scores(ticker: yf.Ticker) -> Dict[str, Optional[float]]:
    scores: Dict[str, Optional[float]] = {key: None for key in ESG_KEYS}
    sustainability = ticker.sustainability
    if sustainability is None or sustainability.empty:
        return scores

    if "Value" in sustainability.columns:
        values = sustainability["Value"]
    else:
        values = sustainability.iloc[:, 0]

    for target_key, source_key in ESG_KEYS.items():
        value = values.get(source_key)
        scores[target_key] = float(value) if value is not None else None

    return scores


def fetch_company_financials(
    ticker: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    yf_ticker = yf.Ticker(ticker)

    balance_sheet = yf_ticker.balance_sheet
    income_stmt = yf_ticker.financials

    balance_values: Dict[str, Dict[int, float]] = {}
    for metric, keys in BALANCE_KEYS.items():
        series = _extract_series(balance_sheet, keys)
        balance_values[metric] = _series_to_year_map(series)

    income_values: Dict[str, Dict[int, float]] = {}
    for metric, keys in INCOME_KEYS.items():
        series = _extract_series(income_stmt, keys)
        income_values[metric] = _series_to_year_map(series)

    esg_scores = _extract_esg_scores(yf_ticker)

    rows: List[Dict[str, Optional[float]]] = []
    for year in range(start_year, end_year + 1):
        total_debt = balance_values["total_debt"].get(year)
        if total_debt is None:
            short_debt = balance_values["short_term_debt"].get(year)
            long_debt = balance_values["long_term_debt"].get(year)
            if short_debt is not None or long_debt is not None:
                total_debt = (short_debt or 0.0) + (long_debt or 0.0)

        total_assets = balance_values["total_assets"].get(year)
        total_equity = balance_values["total_equity"].get(year)

        interest_expense = income_values["interest_expense"].get(year)
        ebit = income_values["ebit"].get(year)
        net_income = income_values["net_income"].get(year)
        total_revenue = income_values["total_revenue"].get(year)

        rows.append(
            {
                "ticker": ticker,
                "year": year,
                "total_debt": total_debt,
                "total_assets": total_assets,
                "total_equity": total_equity,
                "interest_expense": interest_expense,
                "ebit": ebit,
                "net_income": net_income,
                "total_revenue": total_revenue,
                "debt_to_equity": _safe_divide(total_debt, total_equity),
                "debt_to_assets": _safe_divide(total_debt, total_assets),
                "interest_coverage": _safe_divide(ebit, abs(interest_expense))
                if interest_expense
                else None,
                "roa": _safe_divide(net_income, total_assets),
                "roe": _safe_divide(net_income, total_equity),
                "net_margin": _safe_divide(net_income, total_revenue),
                **esg_scores,
            }
        )

    return pd.DataFrame(rows)


def build_financials_dataset(
    mapping_df: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    if mapping_df.empty:
        raise ValueError("Company mapping file is empty. Provide at least one ticker.")

    rows: List[pd.DataFrame] = []
    for ticker in mapping_df["ticker"].dropna().unique():
        ticker = str(ticker).strip()
        if not ticker:
            continue
        company_df = fetch_company_financials(ticker, start_year, end_year)
        rows.append(company_df)

    if not rows:
        raise ValueError("No tickers found in mapping file.")

    return pd.concat(rows, ignore_index=True)
