"""Automercatorum Dispense Downloader — pywebview entry point.

Launches a native window (WKWebView on macOS) rendering ui/index.html.
The JsApi class is exposed to JavaScript via window.pywebview.api.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path

import webview

from mercatorum.api import AuthError, MercatorumAPI
from mercatorum.creds_store import CredentialsStore
from mercatorum.downloader import download_course

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

ROOT = Path(__file__).resolve().parent
AUTH_DIR = ROOT / ".auth"
DOWNLOADS = ROOT / "downloads"
UI_INDEX = ROOT / "ui" / "index.html"


class JsApi:
    """Bridge exposed to JS via window.pywebview.api.<method>.

    pywebview converts Python snake_case method names to camelCase on the JS
    side. Keep names already in camelCase to avoid surprises.
    """

    def __init__(self) -> None:
        self.store = CredentialsStore(AUTH_DIR)
        self.api: MercatorumAPI | None = None
        self.username: str | None = None
        self.window: webview.Window | None = None

    # ---------------------------------------------------------------- auth
    def autoLogin(self) -> dict:
        """At startup: if creds saved → login + courses; else signal first-run."""
        if not self.store.exists():
            return {"firstRun": True}
        try:
            username, password = self.store.load()
            api = MercatorumAPI()
            api.login(username, password)
            self.api = api
            self.username = username
            return {
                "firstRun": False, "ok": True, "username": username,
                "courses": [self._course_to_dict(c) for c in api.list_courses()],
            }
        except AuthError as e:
            return {"firstRun": False, "ok": False, "error": f"Login fallito: {e}"}
        except Exception as e:
            log.exception("autoLogin failed")
            return {"firstRun": False, "ok": False, "error": str(e)}

    def login(self, username: str, password: str, remember: bool) -> dict:
        try:
            api = MercatorumAPI()
            api.login(username, password)
            if remember:
                self.store.save(username, password)
            self.api = api
            self.username = username
            return {
                "ok": True, "username": username,
                "courses": [self._course_to_dict(c) for c in api.list_courses()],
            }
        except AuthError as e:
            return {"ok": False, "error": f"Login fallito: {e}"}
        except Exception as e:
            log.exception("login failed")
            return {"ok": False, "error": str(e)}

    def forgetAccount(self) -> dict:
        self.store.reset()
        self.api = None
        self.username = None
        return {"ok": True}

    def logout(self) -> dict:
        self.api = None
        self.username = None
        return {"ok": True}

    # ----------------------------------------------------------- download
    def download(self, course_codes: list[str]) -> dict:
        if not self.api:
            return {"ok": False, "error": "Non autenticato."}
        threading.Thread(
            target=self._download_worker, args=(list(course_codes),), daemon=True
        ).start()
        return {"ok": True}

    def _download_worker(self, course_codes: list[str]) -> None:
        assert self.api is not None
        course_map = {c.code: c for c in self.api.list_courses()}
        for code in course_codes:
            course = course_map.get(code)
            if not course:
                self._emit({
                    "kind": "course_error", "course_code": code,
                    "message": f"Corso {code} non trovato",
                })
                continue
            log.info("fetching materials for %s (%s)", code, course.name)
            try:
                pdfs = self.api.get_course_pdfs(code)
            except Exception as e:
                log.exception("fetch failed for %s", code)
                self._emit({
                    "kind": "course_error", "course_code": code,
                    "message": f"Fetch fallito: {e}",
                })
                continue
            self._emit({
                "kind": "course_start", "course_code": code,
                "course_name": course.name, "total": len(pdfs),
            })

            def cb(evt: dict, _code=code) -> None:
                self._emit({
                    "kind": "file", "course_code": _code,
                    "index": evt["index"], "total": evt["total"],
                    "file": evt["file"], "message": evt["message"],
                    "status": evt["status"],
                })

            try:
                summary = download_course(course.name, pdfs, DOWNLOADS, progress=cb)
                self._emit({"kind": "course_done", "course_code": code, **summary})
            except Exception as e:
                log.exception("download_course failed for %s", code)
                self._emit({"kind": "course_error", "course_code": code, "message": str(e)})
        self._emit({"kind": "all_done"})

    def _emit(self, evt: dict) -> None:
        if not self.window:
            return
        payload = json.dumps(evt)
        self.window.evaluate_js(f"window.notifyProgress({json.dumps(payload)})")

    def openDownloadsFolder(self) -> dict:
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["open", str(DOWNLOADS)], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(DOWNLOADS)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(DOWNLOADS)], check=False)
        return {"ok": True}

    # ----------------------------------------------------------- helpers
    def _course_to_dict(self, c) -> dict:
        return {"code": c.code, "name": c.name, "progress": c.progress}


def main() -> int:
    log.info("Automercatorum Dispense Downloader")
    log.info("auth dir: %s", AUTH_DIR)
    log.info("downloads dir: %s", DOWNLOADS)
    js_api = JsApi()
    window = webview.create_window(
        "Automercatorum Dispense Downloader",
        str(UI_INDEX),
        js_api=js_api,
        width=960, height=720, min_size=(700, 500),
    )
    js_api.window = window
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
