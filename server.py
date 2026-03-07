"""
MCP Procurement Airlock Server – read-only access to procurement data from a private GitHub repo.
Uses FastMCP with streamable-http for Railway deployment.
"""
import os

from mcp.server.fastmcp import FastMCP

import github_client as gh
from parsing import (
    get_inventory_summary_from_path,
    get_inventory_summary_table,
    get_pricing_analysis_from_paths,
    filter_drawings_by_filename,
)

mcp = FastMCP("Procurement Airlock")

SPREADSHEET_EXTENSIONS = [".xls", ".xlsx", ".csv"]
DRAWING_EXTENSIONS = [".pdf", ".dwg", ".dxf", ".png", ".jpg"]


def _get_default_inventory_path() -> str:
    """Return first spreadsheet path under DATA_PATH, or empty string."""
    base = gh.get_data_path()
    if not base:
        base = ""
    files = gh.list_files_recursive(base or ".", SPREADSHEET_EXTENSIONS)
    return files[0]["path"] if files else ""


def _get_drawings_path() -> str:
    """Path for technical drawings; use DRAWINGS_PATH if set else DATA_PATH."""
    path = (os.environ.get("DRAWINGS_PATH") or "").strip().strip("/")
    if path:
        return path
    return gh.get_data_path() or ""


@mcp.tool()
def get_inventory_summary(file_path: str = "") -> str:
    """Get a summarized table of current stock levels from procurement logs (Excel/CSV).
    Use file_path to specify a file inside the repo, or leave empty to use default path from DATA_PATH."""
    try:
        path = gh.resolve_path(file_path) if file_path.strip() else _get_default_inventory_path()
        if not path:
            return "No spreadsheet found under DATA_PATH. Set DATA_PATH or pass file_path."
        return get_inventory_summary_from_path(gh.get_file_content, path)
    except ValueError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def analyze_vendor_pricing(
    part_identifier: str,
    date_range: str = "all history",
) -> str:
    """Compare historical pricing for a specific part and flag any variance over 10%.
    part_identifier: part number, SKU, or item name. date_range: 'all history' or describe range."""
    try:
        base = gh.get_data_path() or ""
        if not base:
            base = "."
        paths = [f["path"] for f in gh.list_files_recursive(base, SPREADSHEET_EXTENSIONS)]
        if not paths:
            return "No spreadsheet files found under DATA_PATH."
        return get_pricing_analysis_from_paths(
            gh.get_file_content,
            paths,
            part_identifier,
            date_range,
        )
    except ValueError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def search_technical_drawings(
    drawing_number: str = "",
    job_number: str = "",
) -> str:
    """Search file metadata (filenames) for technical drawings by drawing number and/or job number.
    Returns matching filenames and repo paths. At least one of drawing_number or job_number should be provided."""
    if not (drawing_number.strip() or job_number.strip()):
        return "Provide at least one of drawing_number or job_number to search."
    try:
        base = _get_drawings_path() or "."
        files = gh.list_files_recursive(base, DRAWING_EXTENSIONS)
        matched = filter_drawings_by_filename(files, drawing_number, job_number)
        if not matched:
            return "No matching drawings found."
        lines = [f"| {f['name']} | {f['path']} |" for f in matched]
        return "| Filename | Repo path |\n| --- | --- |\n" + "\n".join(lines)
    except ValueError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    # FastMCP 1.x reads host/port/json_response from env vars, not run() kwargs.
    # Railway injects PORT; map it to FASTMCP_PORT.
    os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
    os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8000")
    os.environ.setdefault("FASTMCP_JSON_RESPONSE", "true")
    mcp.run(transport="streamable-http")
