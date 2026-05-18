"""REST client for Universitas Mercatorum LMS.

Endpoints (reverse-engineered from the SPA bundle):
- Auth:    POST https://signin-api.prod.multiversity.click/oauth/token
- LMS:     base https://lms-api.prod.mercatorum.multiversity.click
           Authorization: Bearer <access_token>
- Courses: GET  /student/video-lessons/getCourses
- Folders: GET  /student/course/{code}/video-lessons/lp-folders
- Lessons: GET  /student/course/{code}/video-lessons/{folder_id}
- Dispensa: GET /student/course/{code}/video-lesson/{lp_id}/paragraphs/{lp_id}
            → returns a paragraph list; the lesson item contains `bookUrl`.

PDFs themselves are public CloudFront URLs, no auth required to download.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)

SIGNIN_BASE = "https://signin-api.prod.multiversity.click"
LMS_BASE = "https://lms-api.prod.mercatorum.multiversity.click"

# OAuth2 password-grant client credentials, hard-coded in the public SPA bundle.
CLIENT_ID = 5
CLIENT_SECRET = "joySKkF8sldY0CTv3QvuIoCsKdKRpiZqEKJcfAsF"


class AuthError(Exception):
    pass


@dataclass
class Course:
    code: str
    name: str
    progress: float | None = None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class Pdf:
    url: str
    module_number: int | None
    module_title: str | None


class MercatorumAPI:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MercatorumDispenseDownloader/1.0",
        })
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._credentials: tuple[str, str] | None = None

    # ------------------------------------------------------------------ auth
    def login(self, username: str, password: str) -> None:
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "*",
        }
        log.info("login user=%r", username)
        r = self.session.post(f"{SIGNIN_BASE}/oauth/token", json=payload, timeout=20)
        if r.status_code != 200:
            raise AuthError(f"Login failed [{r.status_code}]: {r.text[:200]}")
        data = r.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        if not self.access_token:
            raise AuthError(f"No access_token in response: {data}")
        self._credentials = (username, password)
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def _refresh_or_relogin(self) -> None:
        if self.refresh_token:
            payload = {
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "*",
            }
            r = self.session.post(f"{SIGNIN_BASE}/oauth/token", json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                self.access_token = data.get("access_token") or self.access_token
                self.refresh_token = data.get("refresh_token") or self.refresh_token
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
                return
        if self._credentials:
            self.login(*self._credentials)
        else:
            raise AuthError("Session expired and no credentials available.")

    # ----------------------------------------------------------- transport
    def _get(self, path: str) -> Any:
        url = f"{LMS_BASE}/{path.lstrip('/')}"
        r = self.session.get(url, timeout=30)
        if r.status_code == 401:
            self._refresh_or_relogin()
            r = self.session.get(url, timeout=30)
        r.raise_for_status()
        return r.json()

    # ---------------------------------------------------------------- data
    def list_courses(self) -> list[Course]:
        data = self._get("student/video-lessons/getCourses")
        items = _unwrap_list(data)
        out: list[Course] = []
        for it in items:
            code = str(it.get("course_code") or it.get("code") or it.get("id") or "").strip()
            name = (it.get("course_name") or it.get("name") or it.get("title") or code).strip()
            progress = it.get("progress") or it.get("percentage") or it.get("perc")
            if code:
                out.append(Course(code=code, name=name, progress=progress, raw=it))
        return out

    def get_course_pdfs(self, course_code: str) -> list[Pdf]:
        """Walk the course's lp-folders → lessons → fetch each lesson's dispensa.

        Returns a deduplicated list of Pdf objects with module ordering metadata.
        """
        # 1) Top-level folders.
        folders_resp = self._get(f"student/course/{course_code}/video-lessons/lp-folders")
        folders = _unwrap_list(folders_resp)

        # 2) Fetch each folder's lesson list in parallel.
        def fetch_folder(folder: dict) -> list[dict]:
            folder_id = folder.get("id_folder") or folder.get("id")
            if folder_id is None:
                return []
            try:
                data = self._get(f"student/course/{course_code}/video-lessons/{folder_id}")
                return _unwrap_list(data)
            except Exception as e:
                log.warning("folder %s fetch failed: %s", folder_id, e)
                return []

        with ThreadPoolExecutor(max_workers=8) as ex:
            folder_lessons = list(ex.map(fetch_folder, folders))

        # 3) Flatten to (lp_id, display_order, lesson_name) tuples.
        lessons: list[tuple[int, int | None, str]] = []
        for lessons_in_folder in folder_lessons:
            for lesson in lessons_in_folder:
                lp_id = lesson.get("lp_id") or lesson.get("id")
                if lp_id is None:
                    continue
                lessons.append((
                    int(lp_id),
                    lesson.get("display_order"),
                    lesson.get("name") or lesson.get("title") or f"lp_{lp_id}",
                ))

        # 4) Fetch each lesson's dispensa in parallel.
        #    Endpoint quirk: /video-lesson/{X}/paragraphs/{Y} ignores X; only Y
        #    selects the lesson. Passing the same lp_id twice is what works.
        def fetch_lesson(item: tuple[int, int | None, str]) -> tuple[tuple, list[str]]:
            lp_id, _, _ = item
            try:
                data = self._get(
                    f"student/course/{course_code}/video-lesson/{lp_id}/paragraphs/{lp_id}"
                )
                return item, _extract_book_urls(data)
            except Exception as e:
                log.warning("lp_id=%s fetch failed: %s", lp_id, e)
                return item, []

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(fetch_lesson, lessons))

        # 5) Dedup by URL while preserving discovery order.
        seen: set[str] = set()
        pdfs: list[Pdf] = []
        for (lp_id, display_order, lesson_name), urls in results:
            for url in urls:
                if url in seen:
                    continue
                seen.add(url)
                pdfs.append(Pdf(url=url, module_number=display_order, module_title=lesson_name))
        return pdfs


# ---------------------------------------------------------------- helpers
def _unwrap_list(data: Any) -> list[dict]:
    """Pull a list of dicts out of a possibly-wrapped API response."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("data", "courses", "items", "result", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _extract_book_urls(node: Any) -> list[str]:
    """Find every `bookUrl` string in a (possibly nested) JSON tree."""
    out: list[str] = []
    if isinstance(node, dict):
        bu = node.get("bookUrl") or node.get("book_url")
        if isinstance(bu, str) and bu.startswith("http"):
            out.append(bu)
        for v in node.values():
            out.extend(_extract_book_urls(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_extract_book_urls(v))
    return out
