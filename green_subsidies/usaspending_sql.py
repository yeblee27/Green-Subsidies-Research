import datetime as dt
import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2

OUTPUT_FIELDS = [
    "award_id",
    "recipient_name",
    "award_amount",
    "awarding_agency",
    "action_date",
    "award_type",
    "cfda_number",
    "naics_code",
    "award_description",
    "business_categories",
    "pop_zip",
    "fiscal_year",
]

COLUMN_CANDIDATES: Dict[str, List[str]] = {
    "award_id": [
        "award_id",
        "generated_unique_award_id",
        "award_id_fain",
        "award_identifier",
    ],
    "recipient_name": [
        "recipient_name",
        "recipient_name_raw",
        "recipient_name_unformatted",
    ],
    "award_amount": [
        "award_amount",
        "total_obligation",
        "federal_action_obligation",
        "action_obligation",
        "total_outlay",
    ],
    "awarding_agency": [
        "awarding_agency_name",
        "awarding_agency",
        "awarding_agency_code",
    ],
    "action_date": ["action_date", "last_action_date", "date_signed"],
    "award_type": ["award_type", "award_type_code"],
    "cfda_number": ["cfda_number", "cfda_numbers", "cfda"],
    "naics_code": ["naics_code", "naics"],
    "award_description": [
        "award_description",
        "description",
        "award_description_text",
    ],
    "business_categories": [
        "business_categories",
        "business_category",
        "business_categories_description",
    ],
    "pop_zip": [
        "pop_zip",
        "place_of_performance_zip",
        "place_of_performance_zip5",
        "place_of_perform_zip5",
    ],
    "fiscal_year": ["fiscal_year", "fy"],
}

DEFAULT_KEYWORD_TARGETS = [
    "award_description",
    "recipient_name",
    "awarding_agency",
    "business_categories",
]

SCHEMA_PRIORITY = ["rpt", "public", "raw", "int", "temp"]


@dataclass(frozen=True)
class TableRef:
    schema: str
    name: str

    @property
    def qualified(self) -> str:
        return f"{quote_identifier(self.schema)}.{quote_identifier(self.name)}"


def quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def load_keywords(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return [str(keyword).strip() for keyword in raw if str(keyword).strip()]


def _fetch_table_candidates(conn, table_name: str) -> List[TableRef]:
    candidates: List[TableRef] = []
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT schemaname, matviewname FROM pg_matviews WHERE matviewname = %s",
            (table_name,),
        )
        candidates.extend(TableRef(row[0], row[1]) for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name = %s
            """,
            (table_name,),
        )
        candidates.extend(TableRef(row[0], row[1]) for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.views
            WHERE table_name = %s
            """,
            (table_name,),
        )
        candidates.extend(TableRef(row[0], row[1]) for row in cursor.fetchall())

    unique: Dict[Tuple[str, str], TableRef] = {(t.schema, t.name): t for t in candidates}
    return list(unique.values())


def _select_preferred_table(candidates: List[TableRef]) -> Optional[TableRef]:
    if not candidates:
        return None
    for schema in SCHEMA_PRIORITY:
        for candidate in candidates:
            if candidate.schema == schema:
                return candidate
    return candidates[0]


def _resolve_table(conn, table_name: str) -> Optional[TableRef]:
    if "." in table_name:
        schema, name = table_name.split(".", 1)
        candidates = _fetch_table_candidates(conn, name)
        for candidate in candidates:
            if candidate.schema == schema:
                return candidate
        return None
    candidates = _fetch_table_candidates(conn, table_name)
    return _select_preferred_table(candidates)


def discover_table(conn, override: Optional[str] = None) -> TableRef:
    if override:
        table_ref = _resolve_table(conn, override)
        if table_ref is None:
            raise ValueError(f"Could not find table or view '{override}'.")
        return table_ref

    for candidate in ("award_search", "transaction_search"):
        table_ref = _select_preferred_table(_fetch_table_candidates(conn, candidate))
        if table_ref:
            return table_ref

    raise ValueError(
        "Could not find award_search or transaction_search. "
        "Provide --table with a fully-qualified name."
    )


def fetch_columns(conn, table_ref: TableRef) -> List[str]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (table_ref.schema, table_ref.name),
        )
        return [row[0] for row in cursor.fetchall()]


def resolve_columns(
    available: Sequence[str],
    overrides: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    available_set = set(available)
    resolved: Dict[str, Optional[str]] = {}

    for field, candidates in COLUMN_CANDIDATES.items():
        override = overrides.get(field)
        if override:
            if override not in available_set:
                raise ValueError(
                    f"Override column '{override}' for '{field}' not found."
                )
            resolved[field] = override
            continue

        resolved[field] = next((c for c in candidates if c in available_set), None)

    missing_required = [
        field
        for field in ("award_id", "recipient_name", "award_amount")
        if not resolved[field]
    ]
    if not resolved["action_date"] and not resolved["fiscal_year"]:
        missing_required.append("action_date or fiscal_year")

    if missing_required:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_required)
            + ". Available columns: "
            + ", ".join(sorted(available_set))
        )

    return resolved


def resolve_keyword_columns(
    available: Sequence[str],
    resolved: Dict[str, Optional[str]],
    override: Optional[str],
) -> List[str]:
    if override:
        requested = [item.strip() for item in override.split(",") if item.strip()]
        keyword_columns: List[str] = []
        available_set = set(available)
        for target in requested:
            if target in resolved and resolved[target]:
                keyword_columns.append(resolved[target])
            elif target in available_set:
                keyword_columns.append(target)
            else:
                raise ValueError(f"Keyword column '{target}' not found.")
        return list(dict.fromkeys(keyword_columns))

    keyword_columns = [
        resolved[target]
        for target in DEFAULT_KEYWORD_TARGETS
        if resolved.get(target)
    ]
    return list(dict.fromkeys(keyword_columns))


def build_query(
    table_ref: TableRef,
    resolved: Dict[str, Optional[str]],
    start_date: str,
    end_date: str,
    keywords: Sequence[str],
    keyword_columns: Sequence[str],
    limit: Optional[int],
) -> Tuple[str, List[object]]:
    params: List[object] = []

    action_date_col = resolved.get("action_date")
    fiscal_year_col = resolved.get("fiscal_year")

    select_parts: List[str] = []
    for field in OUTPUT_FIELDS:
        column = resolved.get(field)
        if field == "fiscal_year":
            if fiscal_year_col:
                expr = quote_identifier(fiscal_year_col)
            else:
                action_expr = quote_identifier(action_date_col)
                expr = (
                    "CASE WHEN EXTRACT(MONTH FROM {action}) >= 10 "
                    "THEN EXTRACT(YEAR FROM {action}) + 1 "
                    "ELSE EXTRACT(YEAR FROM {action}) END"
                ).format(action=action_expr)
        elif column:
            expr = quote_identifier(column)
        elif field == "action_date" and action_date_col:
            expr = quote_identifier(action_date_col)
        else:
            expr = "NULL"
        select_parts.append(f"{expr} AS {field}")

    if action_date_col:
        date_expr = quote_identifier(action_date_col)
        params.extend([start_date, end_date])
        date_clause = f"{date_expr} BETWEEN %s AND %s"
    else:
        start_year = parse_date(start_date).year
        end_year = parse_date(end_date).year
        year_expr = quote_identifier(fiscal_year_col)
        params.extend([start_year, end_year])
        date_clause = f"{year_expr} BETWEEN %s AND %s"

    where_clauses = [date_clause]

    keywords = [keyword for keyword in keywords if keyword]
    keyword_columns = list(keyword_columns)
    if keywords and keyword_columns:
        keyword_conditions = []
        for keyword in keywords:
            col_conditions = []
            for column in keyword_columns:
                column_expr = f"COALESCE(CAST({quote_identifier(column)} AS TEXT), '')"
                col_conditions.append(f"{column_expr} ILIKE %s")
                params.append(f"%{keyword}%")
            keyword_conditions.append("(" + " OR ".join(col_conditions) + ")")
        where_clauses.append("(" + " OR ".join(keyword_conditions) + ")")

    query = (
        "SELECT\n  "
        + ",\n  ".join(select_parts)
        + f"\nFROM {table_ref.qualified}\nWHERE "
        + " AND ".join(where_clauses)
    )
    if limit:
        query += f"\nLIMIT {int(limit)}"

    return query, params


def export_awards_to_csv(
    db_url: str,
    start_date: str,
    end_date: str,
    keywords: Sequence[str],
    output_path: str,
    table_override: Optional[str] = None,
    column_overrides: Optional[Dict[str, Optional[str]]] = None,
    keyword_cols_override: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, object]:
    column_overrides = column_overrides or {}
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    try:
        table_ref = discover_table(conn, table_override)
        available = fetch_columns(conn, table_ref)
        resolved = resolve_columns(available, column_overrides)
        keyword_columns = resolve_keyword_columns(
            available, resolved, keyword_cols_override
        )
        query, params = build_query(
            table_ref,
            resolved,
            start_date,
            end_date,
            keywords,
            keyword_columns,
            limit,
        )
        copy_sql = f"COPY ({query}) TO STDOUT WITH CSV HEADER"
        with conn.cursor() as cursor, open(output_path, "w", encoding="utf-8") as handle:
            rendered = cursor.mogrify(copy_sql, params).decode("utf-8")
            cursor.copy_expert(rendered, handle)
        return {
            "table": f"{table_ref.schema}.{table_ref.name}",
            "resolved_columns": resolved,
            "keyword_columns": keyword_columns,
        }
    finally:
        conn.close()
