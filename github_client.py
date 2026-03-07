"""
Read-only GitHub client for the Procurement Airlock.
Uses GITHUB_TOKEN and GITHUB_REPO from environment; only GET operations.
"""
import base64
import os
from typing import Optional

from github import Github

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv("Cursor_Railway_airlock.env")
except ImportError:
    pass


def _get_client():
    token = os.environ.get("GITHUB_TOKEN")
    repo_spec = os.environ.get("GITHUB_REPO")
    if not token or not repo_spec:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set")
    gh = Github(token)
    owner, _, repo_name = repo_spec.partition("/")
    if not repo_name:
        raise ValueError("GITHUB_REPO must be in form owner/repo")
    return gh.get_repo(f"{owner}/{repo_name}")


def get_data_path() -> str:
    """Return the path prefix inside the repo (DATA_PATH), normalized (no leading slash)."""
    path = (os.environ.get("DATA_PATH") or "").strip().strip("/")
    return path


def resolve_path(relative_path: str) -> str:
    """Resolve a path relative to DATA_PATH. Empty relative_path returns DATA_PATH."""
    base = get_data_path()
    if not relative_path.strip():
        return base
    rel = relative_path.strip().strip("/")
    return f"{base}/{rel}" if base else rel


def get_file_content(repo_path: str) -> bytes:
    """
    Read raw file content from the repo. Read-only.
    repo_path: path inside the repo (e.g. 'procurement/inventory.xls').
    """
    repo = _get_client()
    contents = repo.get_contents(repo_path)
    if contents.content:
        return base64.b64decode(contents.content)
    # Large file: use download_url
    import requests
    resp = requests.get(contents.download_url, headers={"Authorization": f"token {os.environ.get('GITHUB_TOKEN')}"})
    resp.raise_for_status()
    return resp.content


def list_directory(repo_path: str) -> list[dict]:
    """
    List contents of a directory in the repo. Read-only.
    Returns list of dicts with keys: name, path, type ('file'|'dir'), size (for files).
    """
    repo = _get_client()
    try:
        items = repo.get_contents(repo_path)
    except Exception:
        return []
    if not isinstance(items, list):
        items = [items]
    return [
        {
            "name": item.name,
            "path": item.path,
            "type": "dir" if item.type == "dir" else "file",
            "size": getattr(item, "size", None),
        }
        for item in items
    ]


def list_files_recursive(repo_path: str, extensions: Optional[list[str]] = None) -> list[dict]:
    """
    List all files under repo_path recursively. Read-only.
    If extensions is provided (e.g. ['.pdf', '.xls']), only include those extensions.
    Returns list of dicts with keys: name, path.
    """
    repo = _get_client()
    result = []
    path = (repo_path or "").strip().strip("/") or ""

    def walk(p: str) -> None:
        try:
            items = repo.get_contents(p)
        except Exception:
            return
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if item.type == "dir":
                walk(item.path)
            else:
                if extensions:
                    ext = os.path.splitext(item.name)[1].lower()
                    if ext not in extensions:
                        continue
                result.append({"name": item.name, "path": item.path})

    walk(path)
    return result
