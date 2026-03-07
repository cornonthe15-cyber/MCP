# MCP Procurement Airlock Server

Read-only MCP server that exposes procurement data (Excel/CSV logs and technical drawings) from a private GitHub repo. Designed for 1-click deployment on Railway.

## Quick start

1. Set environment variables (see `.env.example`):
   - `GITHUB_TOKEN` – Personal access token with `repo` scope (read-only).
   - `GITHUB_REPO` – `owner/repo` of the private repo.
   - `DATA_PATH` – Optional path prefix inside the repo (e.g. `procurement/`).
   - `DRAWINGS_PATH` – Optional path for drawings (defaults to `DATA_PATH`).
   For local runs, copy `.env.example` to `.env` (or use `Cursor_Railway_airlock.env` in the project root), fill in your credentials, and the server will use them (no need to export variables manually).

2. Install and run locally:
   ```bash
   pip install -r requirements.txt
   python server.py
   ```
   Server listens on `http://0.0.0.0:8000` (or `PORT` if set). MCP endpoint: `http://localhost:8000/mcp`.

3. Deploy to Railway: connect the repo and add the env vars; Railway uses the `Procfile` (`web: python server.py`).

## Data_exports repo

The server is configured for the private repo **cornonthe15-cyber/Data_exports**. Set `GITHUB_REPO=cornonthe15-cyber/Data_exports` and a PAT in `GITHUB_TOKEN`. `DATA_PATH` and `DRAWINGS_PATH` depend on your folder layout inside that repo—run the discovery script below to inspect the structure and choose paths.

**Discovery script:** Run `python scripts/list_repo_contents.py` (with env set) to list repo contents and see spreadsheet/drawing paths so you can set `DATA_PATH` and `DRAWINGS_PATH`.

**Peek export data:** Run `python scripts/peek_export_files.py` to print the first few lines (column names + sample rows) of each spreadsheet in the repo. Use this to verify parsing and to tune column heuristics in `parsing/inventory.py` and `parsing/pricing.py` if your NetSuite column names differ.

## Tools

- **get_inventory_summary** – Parses Excel/CSV (including NetSuite .xls XML) and returns a summarized stock-level table. Use `file_path` or leave empty to use the first spreadsheet under `DATA_PATH`.
- **analyze_vendor_pricing** – Compares historical pricing by part and flags variance over 10%. Uses all spreadsheets under `DATA_PATH`.
- **search_technical_drawings** – Searches filenames under `DRAWINGS_PATH` (or `DATA_PATH`) for drawing number and/or job number. Returns matching filenames and repo paths.

All access is read-only; no write/delete operations.

## Tuning for your data

When you have sample files, you can refine behavior without changing tool contracts:

- **Column heuristics** – In `parsing/inventory.py`, edit `QUANTITY_ALIASES`, `PART_ALIASES`, and `LOCATION_ALIASES`. In `parsing/pricing.py`, edit `PART_ALIASES`, `PRICE_ALIASES`, `DATE_ALIASES`, and `VENDOR_ALIASES` to match your NetSuite/export column names.
- **NetSuite column names from Data_exports:** To add aliases for your exact export columns:
  - **Option A (preferred):** Paste the exact column headers (first row) from one inventory export and one pricing/order export. Those names can be added to the alias tuples in `parsing/inventory.py` and `parsing/pricing.py` (e.g. “Item”, “Quantity on Hand”, “Vendor (Bill to)”, “Amount”, “Tran Date”).
  - **Option B:** Run the server locally with `DATA_PATH` set, call `get_inventory_summary` and `analyze_vendor_pricing` with a known part, and share the tool output (or any “No data” / wrong-column message) so heuristics can be adjusted.
- **NetSuite .xls (XML)** – The loader in `parsing/inventory.py` tries standard Excel first, then falls back to XML Spreadsheet parsing; namespace and row/cell tags are in `_load_xml_spreadsheet()` if your export format differs.
- **Paths** – Set `DATA_PATH` and optionally `DRAWINGS_PATH` so the server looks in the right folders. For multiple spreadsheet sources, the server uses all files under `DATA_PATH` with extensions `.xls`, `.xlsx`, `.csv`.
- **Drawing file types** – In `server.py`, `DRAWING_EXTENSIONS` controls which extensions are searched for technical drawings; add or remove as needed.

## Security

- Only GitHub read operations (get repo, list contents, get file content) are used.
- No tools accept delete or modify targets; no local write paths to source data.
- Store `GITHUB_TOKEN` as a secret in Railway (or in `.env` locally, and keep `.env` out of version control).
