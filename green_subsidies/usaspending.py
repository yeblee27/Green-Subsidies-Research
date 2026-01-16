import datetime as dt
import time
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests

BASE_URL = "https://api.usaspending.gov/api/v2"

DEFAULT_FIELDS = [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Awarding Agency",
    "Action Date",
    "Award Type",
    "CFDA Number",
    "NAICS Code",
    "Award Description",
    "Business Categories",
    "Place of Performance ZIP Code",
]

FIELD_MAP = {
    "Award ID": "award_id",
    "Recipient Name": "recipient_name",
    "Award Amount": "award_amount",
    "Awarding Agency": "awarding_agency",
    "Action Date": "action_date",
    "Award Type": "award_type",
    "CFDA Number": "cfda_number",
    "NAICS Code": "naics_code",
    "Award Description": "award_description",
    "Business Categories": "business_categories",
    "Place of Performance ZIP Code": "pop_zip",
}


class USASpendingClient:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def search_awards(
        self,
        start_date: str,
        end_date: str,
        keywords: Iterable[str],
        limit: int = 100,
        max_pages: int = 200,
        award_type_codes: Optional[List[str]] = None,
        sleep_seconds: float = 0.2,
    ) -> List[Dict]:
        results: List[Dict] = []
        page = 1

        filters: Dict[str, object] = {
            "time_period": [{"start_date": start_date, "end_date": end_date}],
            "keywords": list(keywords),
        }
        if award_type_codes:
            filters["award_type_codes"] = award_type_codes

        while page <= max_pages:
            payload = {
                "filters": filters,
                "fields": DEFAULT_FIELDS,
                "page": page,
                "limit": limit,
                "sort": "Award Amount",
                "order": "desc",
            }

            response = self.session.post(
                f"{BASE_URL}/awards/search/",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            page_results = data.get("results", [])
            if not page_results:
                break

            results.extend(page_results)

            page_metadata = data.get("page_metadata", {})
            if not page_metadata.get("has_next", False):
                break

            page += 1
            time.sleep(sleep_seconds)

        return results


def compute_fiscal_year(action_date: dt.date) -> int:
    if action_date.month >= 10:
        return action_date.year + 1
    return action_date.year


def normalize_awards(awards: List[Dict]) -> pd.DataFrame:
    if not awards:
        return pd.DataFrame(columns=list(FIELD_MAP.values()) + ["fiscal_year"])

    df = pd.DataFrame(awards)
    df = df.rename(columns=FIELD_MAP)
    df["award_amount"] = pd.to_numeric(df.get("award_amount"), errors="coerce")
    df["action_date"] = pd.to_datetime(df.get("action_date"), errors="coerce").dt.date
    df["fiscal_year"] = df["action_date"].apply(
        lambda date_value: compute_fiscal_year(date_value)
        if isinstance(date_value, dt.date)
        else pd.NA
    )
    return df


def write_awards_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)
