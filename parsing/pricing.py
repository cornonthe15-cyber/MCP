"""
Load procurement logs and compute vendor pricing analysis with variance flags.
Read-only; supports varying column names via heuristics.
"""
from typing import Optional

import pandas as pd

from parsing.inventory import load_spreadsheet_raw, _find_column

# NetSuite exports: "Item", "Company Name", "Preferred Vendor", "Expected Receipt Date", etc.
PART_ALIASES = ("part", "item", "sku", "product", "number", "item id", "part number", "material", "display name", "description")
PRICE_ALIASES = ("price", "unit price", "cost", "amount", "total", "unit cost")
DATE_ALIASES = (
    "date", "order date", "transaction date", "created", "modified", "posting date",
    "expected receipt date", "wo start date", "ship date", "start date",
)
VENDOR_ALIASES = ("vendor", "supplier", "vendor name", "payee", "company", "company name", "preferred vendor")


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("$", ""), errors="coerce")


def _safe_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def get_pricing_analysis_table(
    data: bytes,
    filename: str,
    part_identifier: str,
    date_range: str = "all history",
) -> str:
    """
    Analyze historical pricing for a part and flag variance > 10%.
    Returns markdown table with part, dates, prices, variance %, and flags.
    """
    df = load_spreadsheet_raw(data, filename)
    if df.empty or len(df) == 0:
        return "No data found or unable to parse the file."

    part_col = _find_column(df, PART_ALIASES) or df.columns[0]
    price_col = _find_column(df, PRICE_ALIASES)
    date_col = _find_column(df, DATE_ALIASES)
    vendor_col = _find_column(df, VENDOR_ALIASES)

    if not price_col:
        for c in df.columns:
            if "price" in str(c).lower() or "cost" in str(c).lower() or "amount" in str(c).lower():
                price_col = c
                break
        if not price_col:
            # First numeric column that isn't the part
            for c in df.columns:
                if c != part_col and (_safe_numeric(df[c]).notna().any()):
                    price_col = c
                    break
        if not price_col:
            price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    df = df.copy()
    df["_part"] = df[part_col].astype(str).str.strip()
    df["_price"] = _safe_numeric(df[price_col])
    df = df[df["_price"].notna() & (df["_price"] > 0)]
    if part_identifier:
        part_identifier = str(part_identifier).strip()
        df = df[df["_part"].str.contains(part_identifier, case=False, na=False)]
    if df.empty:
        return f"No pricing records found for part '{part_identifier}'."

    if date_col:
        df["_date"] = _safe_date(df[date_col])
        df = df[df["_date"].notna()]
        if date_range and date_range.lower() != "all history":
            # Simple heuristic: "last 12 months" etc. could be parsed here
            df = df.sort_values("_date")

    group_cols = ["_part", "_price"]
    if vendor_col:
        df["_vendor"] = df[vendor_col].astype(str)
        group_cols.append("_vendor")
    if date_col:
        group_cols.append("_date")

    # Dedupe by part (+ vendor) + date, take one price per combination
    df = df.drop_duplicates(subset=[c for c in group_cols if c in df.columns])
    df = df.sort_values("_date" if date_col else part_col)

    prices = df["_price"].tolist()
    if len(prices) < 2:
        return (
            f"Only one price point found for part '{part_identifier}': {prices[0]}. "
            "Need at least two to compute variance."
        )

    # Variance from previous price
    df = df.reset_index(drop=True)
    df["_prev_price"] = df["_price"].shift(1)
    df["_variance_pct"] = ((df["_price"] - df["_prev_price"]) / df["_prev_price"] * 100).round(1)
    df["_flag"] = df["_variance_pct"].abs().gt(10).map({True: "YES", False: ""})

    out = df[["_part", "_price", "_variance_pct", "_flag"]].copy()
    out.columns = ["Part", "Price", "Variance %", ">10%?"]
    if date_col:
        out.insert(1, "Date", df["_date"].dt.strftime("%Y-%m-%d"))
    if vendor_col:
        out.insert(2, "Vendor", df["_vendor"])

    return out.to_markdown(index=False)


def get_pricing_analysis_from_paths(
    get_content_fn,
    repo_paths: list[str],
    part_identifier: str,
    date_range: str = "all history",
) -> str:
    """
    Load one or more files and merge for pricing analysis.
    get_content_fn: callable that returns bytes given path.
    """
    all_data: list[tuple[bytes, str]] = []
    for path in repo_paths:
        try:
            data = get_content_fn(path)
            all_data.append((data, path))
        except Exception:
            continue
    if not all_data:
        return "No files could be read from the repo."
    # Combine: concatenate raw bytes doesn't work for Excel; run analysis per file and combine
    results = []
    for data, path in all_data:
        table = get_pricing_analysis_table(data, path, part_identifier, date_range)
        if "No data" not in table and "No pricing records" not in table:
            results.append(f"**From {path}:**\n\n{table}")
    if not results:
        return f"No pricing records found for part '{part_identifier}' in the given files."
    return "\n\n---\n\n".join(results)
