# MCP Procurement Airlock — Project Context

> This file is the authoritative context document for this project. Paste it into any new AI chat before making changes. It explains what the project does, how it is deployed, and — most importantly — the constraints that have already caused bugs and must not be re-introduced.

---

## What this project is

A lightweight MCP (Model Context Protocol) server that gives an AI assistant read-only access to procurement data stored in a private GitHub repository. The data consists of ERP export files (Excel/CSV spreadsheets updated multiple times daily) and technical drawings (PDFs, DWGs). The server acts as a secure proxy: the AI never touches GitHub credentials or raw file storage directly — it calls tools on this server, which fetches and returns the data. The primary use case is letting Claude (in Cursor or another MCP client) explore the raw data to build dashboards and find relationships across exports.

---

## Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  AI assistant (MCP client)  │        │  Private GitHub repo             │
│  e.g. Claude in Cursor      │        │  cornonthe15-cyber/Data_exports   │
│                             │        │                                  │
│  Calls MCP tools via HTTP   │        │  - ERP export spreadsheets       │
│  POST to /mcp               │        │  - Technical drawings (PDF/DWG)  │
└────────────┬────────────────┘        └──────────────┬───────────────────┘
             │                                        │
             ▼                                        │ GitHub API (read-only)
┌────────────────────────────────┐                   │ uses GITHUB_TOKEN
│  Railway cloud container       │◄──────────────────┘
│  https://web-production-       │
│  e8b91.up.railway.app          │
│                                │
│  python server.py              │
│  FastMCP / streamable-http     │
│  MCP endpoint: /mcp            │
└────────────────────────────────┘
```

The server exposes two tools:

- **`list_repo_files(path="")`** — lists all files under a given path (defaults to repo root). Returns name, path, size, and extension for each file. Use this to discover what data is available.
- **`get_file_contents(path)`** — fetches a file by its repo path and returns its contents. Spreadsheets (`.xls`, `.xlsx`, `.csv`) are returned as CSV text so the AI can read columns and rows. Binary files (PDFs, DWGs) return metadata only (name, path, size, download URL).

---

## How to update the data (no code changes needed)

The ERP exports are stored in the separate private repo `cornonthe15-cyber/Data_exports`.

1. Download your export file from NetSuite (or wherever).
2. Drop it into the local exports folder (set `EXPORTS_FOLDER` in `Cursor_Railway_airlock.env`).
3. Run from the project root:
   ```
   python scripts/upload_exports_to_github.py
   ```
   The script pushes all new/changed files to `Data_exports`. The MCP server immediately sees the updated data on the next tool call — no restart or redeploy required.

**Automate with Windows Task Scheduler:** See README.md for step-by-step instructions to schedule the upload script to run automatically.

---

## Critical technical constraints

These are the constraints that have caused real bugs. Do not change these patterns without understanding why they exist.

### 1. `FASTMCP_HOST` and `FASTMCP_PORT` must be set before FastMCP is imported

```python
# CORRECT — env vars set before the import
import os
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8000")

from mcp.server.fastmcp import FastMCP  # reads settings at import time
```

FastMCP reads `FASTMCP_HOST` and `FASTMCP_PORT` when the module is first imported (or when `FastMCP()` is instantiated at module level). If you set them later — for example inside `if __name__ == "__main__":` — they are ignored and the server defaults to `host=127.0.0.1`, which is unreachable from outside the Railway container.

### 2. `FastMCP.run()` only accepts `transport=`

```python
# CORRECT
mcp.run(transport="streamable-http")

# WRONG — raises TypeError in mcp >= 1.26.0
mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
mcp.run(transport="streamable-http", json_response=True)
```

As of `mcp` 1.12.3+, `FastMCP.run()` no longer accepts `host`, `port`, `json_response`, or any other kwargs. Pass only `transport`. All other configuration goes through `FASTMCP_*` environment variables.

### 3. `FastMCP()` constructor only accepts `name` and `instructions`

```python
# CORRECT
mcp = FastMCP("Procurement Airlock")

# WRONG — raises TypeError in mcp >= 1.12.3
mcp = FastMCP("Procurement Airlock", json_response=True, host="0.0.0.0")
```

### 4. Railway injects `PORT`; FastMCP reads `FASTMCP_PORT` — the mapping is intentional

Railway assigns a dynamic port via the `PORT` environment variable. FastMCP does not read `PORT` — it reads `FASTMCP_PORT`. The line `os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8000")` in `server.py` is the bridge between them. Do not remove it.

### 5. `FASTMCP_HOST` must be `0.0.0.0`, not `127.0.0.1`

Railway routes external traffic into the container. If the server only listens on `127.0.0.1` (localhost), incoming requests from Railway's router never reach the process and the deployment shows "Application failed to respond."

### 6. The MCP endpoint is `/mcp`, not `/`

A GET request to `/` returns 404 — this is normal and does not indicate a crash. The MCP protocol uses POST to `/mcp`. If a health check is needed, it should target `/mcp` (which returns 405 for plain GET, meaning the server is alive).

### 7. Python 3.11+ is required

The codebase uses `list[dict]` and `list[str]` type hints (lowercase generics), which are only valid in Python 3.9+. Python 3.11 is pinned in `.python-version` to match Railway's build. Do not remove `.python-version` or lower the version — Railway defaults to an older Python that breaks these hints.

### 8. This runs on Railway (cloud container), not locally and not in Docker

The deployment is a Railway-managed cloud container. There is no Docker Compose file, no Dockerfile, and no local container runtime involved. Do not suggest Docker-based changes unless the user explicitly moves to Docker. The `Procfile` (`web: python server.py`) is Railway's entry point.

---

## File map

| File | Purpose |
|---|---|
| `server.py` | MCP server entry point. Defines tools, sets FastMCP env vars, calls `mcp.run()`. |
| `github_client.py` | Read-only GitHub API client. Uses `GITHUB_TOKEN` and `GITHUB_REPO`. |
| `Procfile` | Railway start command: `web: python server.py`. |
| `railway.toml` | Railway build config. Sets builder to nixpacks, start command. |
| `.python-version` | Pins Python 3.11 for Railway's nixpacks builder. Do not remove. |
| `requirements.txt` | Python dependencies. |
| `scripts/upload_exports_to_github.py` | Pushes local export files to the `Data_exports` repo. |
| `scripts/list_repo_contents.py` | Discovery script — lists what's in the `Data_exports` repo. |
| `Cursor_Railway_airlock.env` | Local env file (gitignored). Contains secrets for local development. |
| `.env.example` | Template showing which env vars are needed. |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub personal access token with `repo` scope (read-only is sufficient). Store as a Railway secret, never commit. |
| `GITHUB_REPO` | Yes | The data repo in `owner/repo` format. Currently `cornonthe15-cyber/Data_exports`. |
| `DATA_PATH` | No | Path prefix inside `GITHUB_REPO` to scope file listing (e.g. `exports/`). Defaults to repo root. |
| `DRAWINGS_PATH` | No | Separate path prefix for technical drawings. Defaults to `DATA_PATH`. |
| `PORT` | Set by Railway | Railway-assigned port. Automatically mapped to `FASTMCP_PORT` in `server.py`. Do not set manually. |
| `EXPORTS_FOLDER` | Local only | Full local path to the folder where you drop export files before running the upload script. |

---

## Dependencies (key packages)

| Package | Why it's here |
|---|---|
| `mcp>=1.26.0` | The official Anthropic MCP Python SDK. Provides `FastMCP` and the `streamable-http` transport. |
| `PyGithub` | GitHub API client used in `github_client.py`. |
| `pandas`, `openpyxl`, `xlrd` | Used in `get_file_contents()` to convert Excel files to CSV text. |
| `defusedxml` | Safe XML parsing for NetSuite-style `.xls` files (XML Spreadsheet format). |
| `python-dotenv` | Loads `.env` / `Cursor_Railway_airlock.env` for local development. |
