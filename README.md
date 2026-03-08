# MCP Procurement Airlock Server

Read-only MCP server that exposes procurement data (Excel/CSV exports and technical drawings) from a private GitHub repo. Designed for 1-click deployment on Railway.

For architecture, deployment constraints, and bug-prevention context, see **[PROJECT.md](PROJECT.md)**.

---

## Quick start

1. Set environment variables (copy `.env.example` to `.env` and fill in):
   - `GITHUB_TOKEN` — Personal access token with `repo` scope (read-only).
   - `GITHUB_REPO` — `owner/repo` of the private data repo (e.g. `cornonthe15-cyber/Data_exports`).
   - `DATA_PATH` — Optional path prefix inside the repo (e.g. `exports/`). Defaults to repo root.

2. Install and run locally:
   ```bash
   pip install -r requirements.txt
   python server.py
   ```
   MCP endpoint: `http://localhost:8000/mcp`

3. Deploy to Railway: connect this repo, add the env vars as Railway secrets. Railway uses the `Procfile` (`web: python server.py`) and `.python-version` (Python 3.11) automatically.

---

## Tools

- **`list_repo_files(path="")`** — Lists all files under a path in the data repo (defaults to root). Returns name, path, size, and extension. Use this first to discover what data is available.
- **`get_file_contents(path)`** — Fetches a file by its repo path and returns its contents. Spreadsheets (`.xls`, `.xlsx`, `.csv`) are returned as CSV text. Binary files (PDF, DWG, etc.) return metadata only.

All access is read-only — no write or delete operations.

---

## Updating the data

The ERP exports live in the separate private repo `cornonthe15-cyber/Data_exports`. To push new exports:

1. Set `EXPORTS_FOLDER` in `Cursor_Railway_airlock.env` to your local exports folder path.
2. Drop the new export files into that folder.
3. Run:
   ```bash
   python scripts/upload_exports_to_github.py
   ```
   The script uploads new and changed files to the data repo. The MCP server sees updated data immediately on the next tool call — no restart needed.

**Automate with Windows Task Scheduler:**

1. Open Task Scheduler → Create Basic Task.
2. Trigger: Daily (or after you usually download exports).
3. Action: Start a program — `python`, arguments: `scripts/upload_exports_to_github.py`, start in: `c:\Users\corno\OneDrive\Documents\00_Projects\MCP`.

Or create a batch file:
```bat
cd /d "c:\Users\corno\OneDrive\Documents\00_Projects\MCP"
python scripts/upload_exports_to_github.py
```

---

## Discovery scripts

- `python scripts/list_repo_contents.py` — Lists all files in the data repo. Useful for verifying the `DATA_PATH` setting.
- `python scripts/peek_export_files.py` — Prints the first few rows of each spreadsheet. Useful for checking what columns your exports contain.

---

## Security

- Only GitHub read operations are used (get file, list contents).
- `GITHUB_TOKEN` should be stored as a Railway secret, never committed to this repo.
- `.env` and `Cursor_Railway_airlock.env` are gitignored.
