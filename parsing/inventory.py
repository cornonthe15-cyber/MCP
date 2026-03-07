"""
Load Excel/CSV/NetSuite .xls (XML) and normalize for inventory summary.
Read-only; supports varying column names via heuristics.
"""
import io
import re
from typing import Optional

import pandas as pd


# Heuristic column name patterns (case-insensitive substring match)
# NetSuite exports: "Sum of On Hand", "Sum of Available", "Item", "Location", "Bin Number", etc.
QUANTITY_ALIASES = (
    "qty", "quantity", "on hand", "onhand", "stock", "balance", "amount", "total qty",
    "sum of on hand", "sum of available", "maximum of on hand", "wo quantity", "quantity issued",
    "committed quantity", "fulfilled quantity", "maximum of order quantity",
)
PART_ALIASES = ("part", "item", "sku", "product", "number", "item id", "part number", "material", "display name", "description")
LOCATION_ALIASES = ("location", "warehouse", "site", "bin", "warehouse name", "subsidiary", "bin number")


def _find_column(df: pd.DataFrame, aliases: tuple) -> Optional[str]:
    """Return first column name whose lowercased value contains any of the aliases."""
    for col in df.columns:
        if not isinstance(col, str):
            continue
        c = col.lower().strip()
        for a in aliases:
            if a in c:
                return col
    return None


def _safe_numeric(s: pd.Series) -> pd.Series:
    """Coerce series to numeric, non-numeric become NaN."""
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


def load_spreadsheet_raw(data: bytes, filename: str = "") -> pd.DataFrame:
    """
    Load spreadsheet from raw bytes. Handles .xls (binary), .xlsx, and NetSuite-style .xls (XML).
    Returns a single DataFrame; for multi-sheet files, concatenates all sheets with flexible columns.
    """
    path_lower = (filename or "").lower()
    is_xls = path_lower.endswith(".xls") and not path_lower.endswith(".xlsx")
    is_csv = path_lower.endswith(".csv")
    bio = io.BytesIO(data)

    if is_csv:
        return pd.read_csv(bio)

    # Try standard Excel first
    try:
        if is_xls:
            xl = pd.ExcelFile(bio, engine="xlrd")
        else:
            xl = pd.ExcelFile(bio, engine="openpyxl")
        dfs = []
        for name in xl.sheet_names:
            df = xl.parse(name, header=0)
            if df is not None and not df.empty:
                dfs.append(df)
        if dfs:
            return pd.concat(dfs, ignore_index=True)
    except Exception:
        pass

    # If .xls and failed, try as XML (NetSuite SpreadsheetML)
    if is_xls and data.strip().startswith(b"<"):
        return _load_xml_spreadsheet(data)

    # Fallback: try openpyxl for .xls (some variants)
    try:
        bio.seek(0)
        xl = pd.ExcelFile(bio, engine="openpyxl")
        dfs = [xl.parse(n, header=0) for n in xl.sheet_names]
        return pd.concat([d for d in dfs if d is not None and not d.empty], ignore_index=True)
    except Exception:
        pass

    return pd.DataFrame()


def _load_xml_spreadsheet(data: bytes) -> pd.DataFrame:
    """Parse XML Spreadsheet (NetSuite-style) into a single DataFrame."""
    try:
        import defusedxml.ElementTree as ET
    except ImportError:
        import xml.etree.ElementTree as ET

    root = ET.fromstring(data)
    # Common namespaces in SpreadsheetML
    ns = {
        "ss": "urn:schemas-microsoft-com:office:spreadsheet",
        "": "urn:schemas-microsoft-com:office:spreadsheet",
    }
    rows = root.findall(".//ss:Row", ns) or root.findall(".//Row", ns)
    if not rows:
        rows = root.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Row")
    cells_list = []
    for row in rows:
        cells = row.findall("ss:Cell", ns) or row.findall("Cell", ns) or row.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Cell")
        row_data = []
        for cell in cells:
            data_elem = cell.find("ss:Data", ns) or cell.find("Data", ns)
            if data_elem is not None and data_elem.text:
                row_data.append(data_elem.text.strip())
            else:
                row_data.append("")
        if row_data:
            cells_list.append(row_data)
    if not cells_list:
        return pd.DataFrame()
    # First row as header, rest as data
    return pd.DataFrame(cells_list[1:], columns=cells_list[0] if cells_list else None)


def get_inventory_summary_table(data: bytes, filename: str = "") -> str:
    """
    Parse procurement log and return a markdown table of current stock levels.
    Uses heuristics to find part, quantity, and optional location columns.
    """
    df = load_spreadsheet_raw(data, filename)
    if df.empty or len(df) == 0:
        return "No data found or unable to parse the file."

    part_col = _find_column(df, PART_ALIASES)
    qty_col = _find_column(df, QUANTITY_ALIASES)
    loc_col = _find_column(df, LOCATION_ALIASES)

    if not part_col:
        part_col = df.columns[0]
    if not qty_col:
        # First numeric column
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]) or _safe_numeric(df[c]).notna().any():
                qty_col = c
                break
        if not qty_col:
            qty_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    df = df.copy()
    df["_qty"] = _safe_numeric(df[qty_col]).fillna(0)
    group_cols = [part_col]
    if loc_col:
        group_cols.append(loc_col)
    agg = df.groupby(group_cols, dropna=False)["_qty"].sum().reset_index()
    agg.columns = ["Part", "Quantity"] if len(agg.columns) == 2 else ["Part", "Location", "Quantity"]
    agg["Quantity"] = agg["Quantity"].astype(int)
    return agg.to_markdown(index=False)


def get_inventory_summary_from_path(get_content_fn, repo_path: str) -> str:
    """
    Load file from repo via get_content_fn(repo_path) and return inventory summary table.
    get_content_fn: callable that returns bytes given path.
    """
    try:
        data = get_content_fn(repo_path)
    except Exception as e:
        return f"Error reading file: {e}"
    return get_inventory_summary_table(data, repo_path)
