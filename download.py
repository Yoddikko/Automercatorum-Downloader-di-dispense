#!/usr/bin/env python3
"""CLI alternative to the GUI app.

Usage:
    python download.py --list                    # show all subjects
    python download.py <COURSE_CODE> [...]       # download one or more
    python download.py --all                     # download every subject
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from mercatorum.api import AuthError, MercatorumAPI
from mercatorum.creds_store import CredentialsStore
from mercatorum.downloader import download_course

ROOT = Path(__file__).resolve().parent
AUTH_DIR = ROOT / ".auth"
DOWNLOADS = ROOT / "downloads"


def authenticate() -> MercatorumAPI:
    store = CredentialsStore(AUTH_DIR)
    if store.exists():
        username, password = store.load()
    else:
        username = input("Username/matricola: ").strip()
        password = getpass.getpass("Password: ")
        if input("Salvare credenziali per i prossimi run? [y/N] ").strip().lower() == "y":
            store.save(username, password)
    api = MercatorumAPI()
    try:
        api.login(username, password)
    except AuthError as e:
        print(f"Login fallito: {e}", file=sys.stderr)
        sys.exit(1)
    return api


def main() -> int:
    parser = argparse.ArgumentParser(description="Mercatorum dispense downloader (CLI).")
    parser.add_argument("codes", nargs="*", help="Course codes (e.g. 0082306MAT05I)")
    parser.add_argument("--list", action="store_true", help="Only list subjects")
    parser.add_argument("--all", action="store_true", help="Download every subject")
    args = parser.parse_args()

    api = authenticate()
    courses = api.list_courses()

    if args.list:
        for c in courses:
            prog = f" ({c.progress:.0f}%)" if c.progress is not None else ""
            print(f"  {c.code}  {c.name}{prog}")
        return 0

    if args.all:
        targets = courses
    elif args.codes:
        by_code = {c.code: c for c in courses}
        targets = [by_code[code] for code in args.codes if code in by_code]
        for code in args.codes:
            if code not in by_code:
                print(f"  ! Codice non trovato: {code}", file=sys.stderr)
    else:
        parser.print_help()
        return 1

    for course in targets:
        print(f"\n→ {course.name} ({course.code})")
        try:
            pdfs = api.get_course_pdfs(course.code)
        except Exception as e:
            print(f"  ! Fetch failed: {e}", file=sys.stderr)
            continue
        print(f"  {len(pdfs)} PDFs to fetch")

        def cb(evt: dict) -> None:
            print(f"  [{evt['index']:>2}/{evt['total']:<2}] {evt['file']} — {evt['message']}")

        summary = download_course(course.name, pdfs, DOWNLOADS, progress=cb)
        print(f"  ✓ {summary['downloaded']} new, {summary['skipped']} skipped, "
              f"{summary['failed']} failed → {summary['output_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
