"""PDF downloader: streaming, idempotent (skips if same size on disk)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Callable, Iterable

import requests

from .api import Pdf


def slugify(text: str, max_len: int = 80) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:max_len] or "untitled"


def download_pdf(url: str, dest: Path) -> tuple[bool, str]:
    """Download a single PDF. Returns (downloaded_new, status_message)."""
    try:
        head = requests.head(url, allow_redirects=True, timeout=20)
        remote_size = int(head.headers.get("content-length", "0"))
    except Exception as e:
        return False, f"HEAD failed: {e}"

    if dest.exists() and remote_size and dest.stat().st_size == remote_size:
        return False, f"skip ({dest.stat().st_size // 1024} KB)"

    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
        tmp.replace(dest)
    return True, f"downloaded ({dest.stat().st_size // 1024} KB)"


ProgressCb = Callable[[dict], None]


def download_course(
    course_name: str,
    pdfs: Iterable[Pdf],
    output_root: Path,
    progress: ProgressCb | None = None,
) -> dict:
    """Download every PDF for a course into `output_root/<course>/`."""
    pdfs = list(pdfs)
    out_dir = output_root / slugify(course_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(pdfs)
    downloaded = skipped = failed = 0
    for i, pdf in enumerate(pdfs, start=1):
        prefix = f"{pdf.module_number:02d}_" if pdf.module_number is not None else ""
        title = slugify(pdf.module_title) if pdf.module_title else None
        if title:
            suffix = f"_{i}" if total > 1 and not pdf.module_number else ""
            fname = f"{prefix}{title}{suffix}.pdf"
        else:
            fname = pdf.url.rsplit("/", 1)[-1].split("?", 1)[0] or f"file_{i}.pdf"
        dest = out_dir / fname
        try:
            did, msg = download_pdf(pdf.url, dest)
            if did:
                downloaded += 1
                status = "downloaded"
            else:
                skipped += 1
                status = "skipped"
        except Exception as e:
            failed += 1
            msg = f"FAILED: {e}"
            status = "error"
        if progress:
            progress({
                "course": course_name, "index": i, "total": total,
                "file": fname, "status": status, "message": msg,
            })
    return {
        "course": course_name, "output_dir": str(out_dir),
        "total": total, "downloaded": downloaded,
        "skipped": skipped, "failed": failed,
    }
