"""
Print the first few lines (headers + sample rows) of each data export file in Data_exports.
Run from project root: python scripts/peek_export_files.py
Uses .env in project root for GITHUB_TOKEN and GITHUB_REPO.
"""
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
os.chdir(_project_root)

# Load .env from project root (try Cursor_Railway_airlock.env first, then .env)
_env_file = os.path.join(_project_root, "Cursor_Railway_airlock.env")
if not os.path.isfile(_env_file):
    _env_file = os.path.join(_project_root, ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_file)
    if not os.environ.get("GITHUB_TOKEN") and os.path.isfile(os.path.join(os.path.dirname(_project_root), "Cursor_Railway_airlock.env")):
        load_dotenv(os.path.join(os.path.dirname(_project_root), "Cursor_Railway_airlock.env"))
except ImportError:
    pass

import github_client as gh
from parsing.inventory import load_spreadsheet_raw

SPREADSHEET_EXTENSIONS = [".xls", ".xlsx", ".csv"]
MAX_ROWS = 5


def main() -> None:
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPO"):
        print("Set GITHUB_TOKEN and GITHUB_REPO in Cursor_Railway_airlock.env (or .env) then run again.")
        print("Project root:", os.path.abspath(_project_root))
        sys.exit(1)

    base = gh.get_data_path() or ""
    list_path = base or ""
    files = gh.list_files_recursive(list_path, SPREADSHEET_EXTENSIONS)

    if not files:
        print(f"No spreadsheet files found under '{list_path or 'root'}'.")
        sys.exit(0)

    print(f"Data_exports repo: first few lines of each export ({list_path or 'root'})\n")
    print("=" * 72)

    for f in files:
        path = f["path"]
        name = f["name"]
        print(f"\n--- {path} ---\n")
        try:
            data = gh.get_file_content(path)
            df = load_spreadsheet_raw(data, path)
            if df is None or df.empty:
                print("  (empty or could not parse)\n")
                continue
            print("Columns:", list(df.columns))
            print()
            head = df.head(MAX_ROWS)
            print(head.to_string())
        except Exception as e:
            print(f"  Error: {e}")
        print()

    print("=" * 72)
    print("Done.")


if __name__ == "__main__":
    main()
