"""
Filter technical drawing files by drawing number and/or job number in filename.
Read-only; no file content is read.
"""
import re
from typing import Optional


def filter_drawings_by_filename(
    files: list[dict],
    drawing_number: str = "",
    job_number: str = "",
) -> list[dict]:
    """
    Filter a list of file dicts (each with 'name' and 'path') by substring match
    on filename for drawing_number and/or job_number.
    If both are provided, filename must contain both (AND). Case-insensitive.
    """
    drawing_number = (drawing_number or "").strip()
    job_number = (job_number or "").strip()
    if not drawing_number and not job_number:
        return list(files)

    out = []
    for f in files:
        name = (f.get("name") or "").lower()
        path = (f.get("path") or "").lower()
        text = f"{name} {path}"
        if drawing_number and drawing_number.lower() not in text:
            continue
        if job_number and job_number.lower() not in text:
            continue
        out.append(f)
    return out


def filter_drawings_by_regex(
    files: list[dict],
    drawing_pattern: Optional[str] = None,
    job_pattern: Optional[str] = None,
) -> list[dict]:
    """
    Filter by regex on filename (and path). If both patterns given, both must match.
    """
    if not drawing_pattern and not job_pattern:
        return list(files)
    out = []
    for f in files:
        name = f.get("name") or ""
        path = f.get("path") or ""
        text = f"{name} {path}"
        try:
            if drawing_pattern and not re.search(drawing_pattern, text, re.IGNORECASE):
                continue
            if job_pattern and not re.search(job_pattern, text, re.IGNORECASE):
                continue
        except re.error:
            continue
        out.append(f)
    return out
