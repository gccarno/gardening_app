"""
Database column audit: missing values and summary statistics.

Connects directly to the SQLite database (no Flask context needed) and
produces a per-column report across all tables.

Run from the project root:
    uv run python ml/eda/missing_values.py

Output:
  - Prints a formatted table to the console
  - Writes ml/eda/missing_values.csv
  - Prints a summary: worst tables + top 20 highest-missing columns
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DB_PATH  = _ROOT / "apps" / "api" / "instance" / "garden.db"
_EDA_DIR = Path(__file__).parent
OUT_CSV  = _EDA_DIR / "missing_values.csv"
_TS      = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_CSV_TS = _EDA_DIR / f"missing_values_{_TS}.csv"

# TEXT columns that store JSON arrays/objects
JSON_COLUMNS = {
    "good_neighbors",
    "bad_neighbors",
    "how_to_grow",
    "faqs",
    "nutrition",
    "bloom_months",
    "fruit_months",
    "growth_months",
    "pruning_months",
    "attracts",
    "propagation_methods",
}


def _is_boolean_col(col_name: str, series: pd.Series) -> bool:
    """Heuristic: INTEGER column whose non-null values are a subset of {0, 1}."""
    distinct = set(series.dropna().unique())
    return distinct.issubset({0, 1, True, False})


def _safe_json(val) -> tuple[bool, bool]:
    """Return (parseable, non_empty) for a single value."""
    if pd.isna(val):
        return False, False
    try:
        obj = json.loads(val)
        return True, bool(obj)
    except Exception:
        return False, False


def _truncate(val, max_len: int = 30) -> str:
    s = str(val)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def analyze_table(conn: sqlite3.Connection, table: str) -> list[dict]:
    pragma = pd.read_sql(f"PRAGMA table_info({table})", conn)
    df = pd.read_sql(f"SELECT * FROM [{table}]", conn)
    total_rows = len(df)

    rows = []
    for _, col_info in pragma.iterrows():
        col = col_info["name"]
        raw_type = str(col_info["type"]).upper()
        is_pk = bool(col_info["pk"])

        series = df[col]
        non_null = int(series.notna().sum())
        missing = total_rows - non_null
        missing_pct = round(100.0 * missing / total_rows, 1) if total_rows > 0 else 0.0
        unique = int(series.dropna().nunique())

        # Classify column kind
        base_type = raw_type.split("(")[0].strip()
        is_numeric = base_type in ("INTEGER", "REAL", "FLOAT", "NUMERIC", "DOUBLE")
        is_text = base_type in ("TEXT", "VARCHAR", "CHAR", "CLOB", "BLOB")
        is_bool = is_numeric and _is_boolean_col(col, series)
        is_json = col in JSON_COLUMNS and is_text

        row: dict = {
            "table": table,
            "column": col,
            "sqlite_type": raw_type,
            "is_pk": is_pk,
            "total_rows": total_rows,
            "non_null": non_null,
            "missing": missing,
            "missing_pct": missing_pct,
            "unique": unique,
            # numeric stats
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            # text stats
            "avg_len": None,
            # categorical
            "most_common": None,
            "most_common_pct": None,
            # boolean
            "pct_true": None,
            # json
            "json_parseable_pct": None,
            "json_nonempty_pct": None,
        }

        if non_null == 0:
            rows.append(row)
            continue

        nn = series.dropna()

        if is_bool:
            row["pct_true"] = round(100.0 * float(nn.astype(float).mean()), 1)

        elif is_numeric:
            numeric = pd.to_numeric(nn, errors="coerce").dropna()
            if len(numeric) > 0:
                row["min"] = round(float(numeric.min()), 2)
                row["max"] = round(float(numeric.max()), 2)
                row["mean"] = round(float(numeric.mean()), 2)
                row["std"] = round(float(numeric.std()), 2) if len(numeric) > 1 else 0.0

        if is_text:
            lengths = nn.astype(str).str.len()
            row["avg_len"] = round(float(lengths.mean()), 1)

        if is_json:
            results = [_safe_json(v) for v in nn]
            parseable = sum(1 for p, _ in results if p)
            nonempty = sum(1 for _, e in results if e)
            row["json_parseable_pct"] = round(100.0 * parseable / non_null, 1)
            row["json_nonempty_pct"] = round(100.0 * nonempty / non_null, 1)

        # Most common value for categorical/text (skip high-cardinality numeric PKs)
        if not is_pk and unique <= max(total_rows, 1):
            vc = nn.value_counts()
            if len(vc) > 0:
                top_val = vc.index[0]
                row["most_common"] = _truncate(top_val)
                row["most_common_pct"] = round(100.0 * vc.iloc[0] / non_null, 1)

        rows.append(row)

    return rows


def main() -> None:
    if not DB_PATH.exists():
        print(f"[error] Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        conn,
    )["name"].tolist()

    print(f"Analyzing {len(tables)} tables in {DB_PATH.name} ...\n")

    all_rows: list[dict] = []
    for table in tables:
        all_rows.extend(analyze_table(conn, table))

    conn.close()

    df = pd.DataFrame(all_rows)

    # ── Console output ──────────────────────────────────────────────────────────
    try:
        from tabulate import tabulate

        console_cols = [
            "table", "column", "sqlite_type", "is_pk",
            "total_rows", "non_null", "missing", "missing_pct",
            "unique", "min", "max", "mean", "std",
            "avg_len", "pct_true", "most_common", "most_common_pct",
            "json_parseable_pct", "json_nonempty_pct",
        ]
        print(tabulate(df[console_cols], headers="keys", tablefmt="simple", showindex=False))
    except ImportError:
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        print(df.to_string(index=False))

    # ── CSV export ──────────────────────────────────────────────────────────────
    df.to_csv(OUT_CSV, index=False)
    df.to_csv(OUT_CSV_TS, index=False)
    print(f"\n[OK] Saved to {OUT_CSV}")
    print(f"[OK] Timestamped copy: {OUT_CSV_TS}")

    # ── Summary ─────────────────────────────────────────────────────────────────
    print("\n-- Tables by average missing rate (non-PK columns) --")
    table_summary = (
        df[~df["is_pk"]]
        .groupby("table")["missing_pct"]
        .mean()
        .round(1)
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"missing_pct": "avg_missing_pct"})
    )
    try:
        from tabulate import tabulate
        print(tabulate(table_summary, headers="keys", tablefmt="simple", showindex=False))
    except ImportError:
        print(table_summary.to_string(index=False))

    print("\n-- Top 20 columns by missing rate --")
    top_missing = (
        df[~df["is_pk"]][["table", "column", "total_rows", "missing", "missing_pct"]]
        .sort_values("missing_pct", ascending=False)
        .head(20)
    )
    try:
        from tabulate import tabulate
        print(tabulate(top_missing, headers="keys", tablefmt="simple", showindex=False))
    except ImportError:
        print(top_missing.to_string(index=False))


if __name__ == "__main__":
    main()
