"""
List contents of the configured GitHub repo (Data_exports) to decide DATA_PATH and DRAWINGS_PATH.
Run from project root with env set: python scripts/list_repo_contents.py
"""
import os
import sys

# Allow importing github_client when run as scripts/list_repo_contents.py
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, "Cursor_Railway_airlock.env"))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

import github_client as gh

SPREADSHEET_EXTENSIONS = [".xls", ".xlsx", ".csv"]
DRAWING_EXTENSIONS = [".pdf", ".dwg", ".dxf", ".png", ".jpg"]


def main() -> None:
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPO"):
        print("Set GITHUB_TOKEN and GITHUB_REPO (e.g. in .env) then run again.")
        sys.exit(1)

    base = gh.get_data_path() or ""
    root_label = f" (DATA_PATH={base!r})" if base else " (repo root)"
    print(f"Listing repo: {os.environ.get('GITHUB_REPO')}{root_label}\n")

    # Top-level contents
    list_path = base or ""
    items = gh.list_directory(list_path)
    if not items:
        print("(empty or path not found)\n")
    else:
        print("Top-level contents:")
        for x in sorted(items, key=lambda t: (t["type"] != "dir", (t["name"] or "").lower())):
            t = "dir " if x["type"] == "dir" else "file"
            size = f"  {x['size']} bytes" if x.get("size") else ""
            print(f"  [{t}] {x['path']}{size}")
        print()

    # All spreadsheets recursively
    spreadsheets = gh.list_files_recursive(list_path, SPREADSHEET_EXTENSIONS)
    print(f"Spreadsheets (.xls, .xlsx, .csv) under '{list_path or 'root'}':")
    if not spreadsheets:
        print("  (none)")
    else:
        for f in spreadsheets:
            print(f"  {f['path']}")
    print()

    # All drawing-type files recursively
    drawings = gh.list_files_recursive(list_path, DRAWING_EXTENSIONS)
    print(f"Drawing files ({', '.join(DRAWING_EXTENSIONS)}) under '{list_path or 'root'}':")
    if not drawings:
        print("  (none)")
    else:
        for f in drawings:
            print(f"  {f['path']}")

    print("\nUse the paths above to set DATA_PATH and optionally DRAWINGS_PATH in .env")


if __name__ == "__main__":
    main()
