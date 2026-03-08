"""
Upload export files from a local folder to the Data_exports GitHub repo.
Run from project root: python scripts/upload_exports_to_github.py
Uses Cursor_Railway_airlock.env (or .env) for GITHUB_TOKEN, EXPORTS_FOLDER, DATA_EXPORTS_REPO.
"""
import base64
import os
import sys
from datetime import datetime

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
os.chdir(_project_root)

# Load env from project root
_env_file = os.path.join(_project_root, "Cursor_Railway_airlock.env")
if not os.path.isfile(_env_file):
    _env_file = os.path.join(_project_root, ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_file)
    if not os.environ.get("GITHUB_TOKEN"):
        load_dotenv(os.path.join(os.path.dirname(_project_root), "Cursor_Railway_airlock.env"))
except ImportError:
    pass

UPLOAD_EXTENSIONS = (".xls", ".xlsx", ".csv", ".pdf")
DEFAULT_DATA_EXPORTS_REPO = "cornonthe15-cyber/Data_exports"


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    repo_spec = os.environ.get("DATA_EXPORTS_REPO", "").strip() or DEFAULT_DATA_EXPORTS_REPO
    exports_folder = os.environ.get("EXPORTS_FOLDER", "").strip()

    if not token:
        print("Set GITHUB_TOKEN in Cursor_Railway_airlock.env (or .env). Token must have write access to the Data_exports repo.")
        return 1
    if not exports_folder or not os.path.isdir(exports_folder):
        print("Set EXPORTS_FOLDER in env to the path of the folder where you save export files (e.g. C:\\...\\MCP\\exports).")
        print("Current EXPORTS_FOLDER:", repr(exports_folder))
        return 1

    from github import Github

    gh = Github(token)
    owner, _, repo_name = repo_spec.partition("/")
    if not repo_name:
        print("DATA_EXPORTS_REPO must be owner/repo (e.g. cornonthe15-cyber/Data_exports).")
        return 1
    repo = gh.get_repo(f"{owner}/{repo_name}")

    # Collect files to upload (flat: only top-level files in EXPORTS_FOLDER with allowed extensions)
    to_upload = []
    for name in os.listdir(exports_folder):
        if not os.path.isfile(os.path.join(exports_folder, name)):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in UPLOAD_EXTENSIONS:
            to_upload.append(name)

    if not to_upload:
        print(f"No .xls, .xlsx, .csv, or .pdf files found in {exports_folder}. Nothing to upload.")
        return 0

    msg_suffix = datetime.now().strftime("%Y-%m-%d %H:%M")
    failed = 0
    for name in sorted(to_upload):
        local_path = os.path.join(exports_folder, name)
        try:
            with open(local_path, "rb") as f:
                content_bytes = f.read()
        except Exception as e:
            print(f"  ERROR reading {name}: {e}")
            failed += 1
            continue

        content_b64 = base64.b64encode(content_bytes).decode("ascii")
        commit_msg = f"Upload exports (script run at {msg_suffix})"

        try:
            try:
                existing = repo.get_contents(name)
                # Update only if content changed (GitHub may return base64 with newlines)
                if existing.content:
                    existing_decoded = base64.b64decode(existing.content.replace("\n", ""))
                    if existing_decoded == content_bytes:
                        print(f"  skip (unchanged): {name}")
                        continue
                repo.update_file(name, commit_msg, content_b64, existing.sha)
                print(f"  updated: {name}")
            except Exception:
                # 404 or not a file -> create
                repo.create_file(name, commit_msg, content_b64)
                print(f"  created: {name}")
        except Exception as e:
            print(f"  ERROR uploading {name}: {e}")
            failed += 1

    if failed:
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
