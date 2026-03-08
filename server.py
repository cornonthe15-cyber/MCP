"""
MCP Procurement Airlock Server — read-only access to procurement data from a private GitHub repo.
Uses FastMCP with streamable-http for Railway deployment.

See PROJECT.md for architecture, deployment constraints, and the reasoning behind
the env var setup below (must happen before FastMCP is imported).
"""
import io
import json
import os

# IMPORTANT: must be set before 'from mcp.server.fastmcp import FastMCP'.
# FastMCP reads FASTMCP_HOST and FASTMCP_PORT at import/init time.
# Railway injects PORT but FastMCP reads FASTMCP_PORT — this mapping is intentional.
# FASTMCP_HOST must be 0.0.0.0 or Railway's router cannot reach the process.
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8000")

from mcp.server.fastmcp import FastMCP

import github_client as gh

mcp = FastMCP("Procurement Airlock")

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
    """Convert Excel file bytes to CSV text. All sheets are included, separated by headers."""
    try:
        import pandas as pd

        ext = os.path.splitext(filename)[1].lower()
        bio = io.BytesIO(data)
        engine = "xlrd" if ext == ".xls" else "openpyxl"

        try:
            xl = pd.ExcelFile(bio, engine=engine)
        except Exception:
            bio.seek(0)
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
        # Fall back: try XML Spreadsheet (NetSuite .xls export format)
        if filename.lower().endswith(".xls") and data.strip().startswith(b"<"):
            return _xml_spreadsheet_to_csv(data)
        return f"Could not parse spreadsheet: {e}"


def _xml_spreadsheet_to_csv(data: bytes) -> str:
    """Parse XML Spreadsheet (NetSuite SpreadsheetML) and return as CSV text."""
    try:
        try:
            import defusedxml.ElementTree as ET
        except ImportError:
            import xml.etree.ElementTree as ET

        import csv
        import io as _io

        root = ET.fromstring(data)
        ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
        rows = (
            root.findall(".//ss:Row", ns)
            or root.findall(".//Row")
            or root.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Row")
        )

        out = _io.StringIO()
        writer = csv.writer(out)
        for row in rows:
            cells = (
                row.findall("ss:Cell", ns)
                or row.findall("Cell")
                or row.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Cell")
            )
            row_data = []
            for cell in cells:
                data_elem = (
                    cell.find("ss:Data", ns)
                    or cell.find("Data")
                )
                row_data.append(data_elem.text.strip() if data_elem is not None and data_elem.text else "")
            writer.writerow(row_data)

        return out.getvalue()
    except Exception as e:
        return f"Could not parse XML spreadsheet: {e}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
