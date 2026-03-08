"""
MCP Procurement Airlock Server — read-only access to procurement data from a private GitHub repo.
Uses FastMCP with streamable-http for Railway deployment.
"""
import io
import json
import os

from mcp.server.fastmcp import FastMCP

import github_client as gh

_port = int(os.environ.get("PORT", "8000"))
mcp = FastMCP("Procurement Airlock", host="0.0.0.0", port=_port)

BINARY_EXTENSIONS = {".pdf", ".dwg", ".dxf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".docx"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".csv"}


@mcp.tool()
def list_repo_files(path: str = "") -> str:
    """List all files in the data repo under the given path (defaults to repo root).
    Returns a JSON array with name, path, size, and extension for each file.
    Use this first to discover what data is available before calling get_file_contents."""
    try:
        base = gh.resolve_path(path) if path.strip() else (gh.get_data_path() or "")
        files = gh.list_files_recursive(base or ".")
        result = [
            {
                "name": f["name"],
                "path": f["path"],
                "size": f.get("size"),
                "extension": os.path.splitext(f["name"])[1].lower(),
            }
            for f in files
        ]
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_file_contents(path: str) -> str:
    """Return the contents of a file by its repo path.
    - CSV files: returned as plain text.
    - Excel files (.xls, .xlsx): converted to CSV text (all sheets) so you can read column names and rows.
    - Binary files (PDF, DWG, etc.): returns metadata only (name, path, size) — binary is not readable as text.
    - Other text files: returned as-is.
    Use list_repo_files() first to find the path."""
    if not path.strip():
        return "Error: path is required. Use list_repo_files() to find available paths."
    try:
        resolved = gh.resolve_path(path)
        ext = os.path.splitext(resolved)[1].lower()

        if ext in BINARY_EXTENSIONS:
            repo = gh._get_client()
            try:
                item = repo.get_contents(resolved)
                return json.dumps({
                    "type": "binary",
                    "name": item.name,
                    "path": item.path,
                    "size_bytes": item.size,
                    "download_url": item.download_url,
                    "message": "Binary file — contents not returned. Use download_url to access directly.",
                })
            except Exception as e:
                return f"Error fetching metadata: {e}"

        data = gh.get_file_content(resolved)

        if ext == ".csv":
            return data.decode("utf-8", errors="replace")

        if ext in (".xls", ".xlsx"):
            return _excel_to_csv_text(data, resolved)

        return data.decode("utf-8", errors="replace")

    except ValueError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Error: {e}"


def _excel_to_csv_text(data: bytes, filename: str) -> str:
    """
    Parse a spreadsheet and return CSV text.

    For .xls files: NetSuite exports these as XML (not binary Excel).
    Parse with ElementTree exactly as SOWO.py does — iterate Row/Cell/Data
    elements, build a raw DataFrame, then auto-detect the real header row
    (first row whose values look like column names, within the first 20 rows).

    For .xlsx / .csv: use pandas normally.
    """
    import pandas as pd
    import xml.etree.ElementTree as ET
    import csv as csv_mod
    import io as _io

    ext = os.path.splitext(filename)[1].lower()

    # --- .xls: always treat as NetSuite XML (SOWO.py approach) ---
    if ext == ".xls":
        try:
            root = ET.fromstring(data)
            rows_xml = root.findall(".//{*}Row")
            raw: list[list[str]] = []
            for row in rows_xml:
                raw.append([
                    str(cell.find(".//{*}Data").text).strip()
                    if cell.find(".//{*}Data") is not None and cell.find(".//{*}Data").text
                    else ""
                    for cell in row.findall(".//{*}Cell")
                ])
            if not raw:
                return "No data found in XML spreadsheet."
            df = pd.DataFrame(raw)
            # Auto-promote header: first row in first 20 that has 3+ non-empty cells
            header_idx = 0
            for i in range(min(20, len(df))):
                non_empty = sum(1 for v in df.iloc[i] if str(v).strip())
                if non_empty >= 3:
                    header_idx = i
                    break
            df.columns = df.iloc[header_idx].astype(str)
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
            # Drop completely empty rows
            df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
            return df.to_csv(index=False)
        except Exception as e:
            return f"Could not parse .xls as XML: {e}"

    # --- .xlsx ---
    if ext == ".xlsx":
        try:
            bio = io.BytesIO(data)
            xl = pd.ExcelFile(bio, engine="openpyxl")
            parts = []
            for sheet_name in xl.sheet_names:
                df = xl.parse(sheet_name)
                if df.empty:
                    continue
                if len(xl.sheet_names) > 1:
                    parts.append(f"# Sheet: {sheet_name}")
                parts.append(df.to_csv(index=False))
            return "\n".join(parts) if parts else "No data found in spreadsheet."
        except Exception as e:
            return f"Could not parse .xlsx: {e}"

    # --- .csv ---
    try:
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not read CSV: {e}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
