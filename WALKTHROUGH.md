# WALKTHROUGH — `feat/server-browser-pdf-export-clean`

A beginner-oriented, line-by-line tour of every change on this branch. You should be able to review the work **without opening the source files**. Read top-to-bottom; each section says what the file does, then walks the new code line by line with the English meaning directly beneath each line.

> **Updated 2026-06-29** for three follow-up commits that **refactored the renderer's class structure** (split into an abstract base + two concrete renderers) and **privatized** all renderer classes. Behavior is unchanged; only the shape of the classes and their names moved. The walkthrough below reflects the current code.

### The big picture in three sentences
ADR can already turn a report into a PDF two ways: a legacy server-side PDF, and a "browser-fidelity" PDF where a headless Chromium browser renders the report and prints it (so charts/equations look exactly like the web view). That browser renderer already existed for the **serverless** mode (it builds a local `file://` copy of the report first). **This branch adds the same browser-fidelity PDF for the *remote service* mode** — where there is already a live ADR web server, so Chromium can just open the live report URL directly — and refactors the renderer into a shared, cleanly-layered class hierarchy so both modes reuse one pipeline.

### The renderer class hierarchy (after the refactor)
```
_BasePlaywrightPDFRenderer(ABC)         # the whole render pipeline; 3 abstract "seam" methods
   ├─ _OfflinePlaywrightPDFRenderer     # opens a local file:// bundle (serverless mode)
   └─ _ReportURLPlaywrightPDFRenderer   # opens a live report URL    (remote mode)  ← the new feature
```
- All three classes start with `_` → they are **internal**; users never touch them directly.
- The base is **abstract** (`ABC`): it cannot be instantiated on its own; the two children fill in the three "seam" methods.

### How the pieces connect (call chain for the new feature)
```
user code
  └─ Report.export_browser_pdf(...)                 # adr_report.py  (NEW public method)
       └─ Server.export_report_as_browser_pdf(...)  # report_remote_server.py (NEW)
            ├─ Server._get_browser_auth_cookies()   # logs in, converts cookies (NEW)
            │     ├─ report_utils.authenticate_web_session()  # NEW (extracted)
            │     └─ Server._build_playwright_cookie()         # NEW (requests→Playwright)
            └─ _ReportURLPlaywrightPDFRenderer(...).render_pdf()  # pdf_renderer.py (NEW class)
                  └─ inherits the whole render pipeline from _BasePlaywrightPDFRenderer
```

### Files in this review
1. [`utils/pdf_renderer.py`](#1-utilspdf_rendererpy--the-renderer-hierarchy) — renderer moved here, split into base + two children
2. [`utils/report_utils.py`](#2-utilsreport_utilspy--login-flow-extracted) — login flow extracted into a reusable helper
3. [`utils/report_remote_server.py`](#3-utilsreport_remote_serverpy--the-remote-browser-pdf-entry-point) — the remote browser-PDF entry point + cookie bridge
4. [`adr_report.py`](#4-adr_reportpy--the-public-reportexport_browser_pdf-method) — the public `Report.export_browser_pdf`
5. [`serverless/adr.py`](#5-serverlessadrpy--one-import-line) — one import line follows the move/rename
6. [Tests](#6-tests--what-each-one-locks-in) — what each test proves, in plain English
7. [Docs/meta](#7-docsmeta-changes) — CHANGELOG + two trivial RST tweaks + lockfile

> **Terminology cheat-sheet:** *headless Chromium* = a real browser with no visible window; *Playwright* = the Python library that drives Chromium; *context* = an isolated browser session (its own cookies/cache); *abstract class (ABC)* = a class you can't create directly — it defines required methods that children must implement; *seam / template method* = a small overridable step in an otherwise fixed recipe; *FOUC* = the brief unstyled flicker before a page's components load; *cookie jar* = where the `requests` library stores cookies after login.

---

## 1. `utils/pdf_renderer.py` — the renderer hierarchy

**What this file does:** Drives headless Chromium to render an ADR report and print it to PDF. It launches the browser, waits for the report to finish rendering (charts, fonts, images…), measures how wide the content is, then calls Chromium's "print to PDF."

**What changed (two refactors):**
1. **Move:** the file moved from `serverless/` to `utils/` so non-serverless code can use it.
2. **Split + privatize:** the old single concrete class `PlaywrightPDFRenderer` became an **abstract base** `_BasePlaywrightPDFRenderer(ABC)` holding the shared pipeline, plus **two concrete children** — `_OfflinePlaywrightPDFRenderer` (local file bundle) and `_ReportURLPlaywrightPDFRenderer` (live URL). The metadata helper class `PlaywrightBrowserBinaryInfo` was renamed `_PlaywrightBrowserBinaryInfo`. Everything is now underscore-private.

> **Why split it?** Before, the live-URL renderer was a child of the *concrete offline* renderer, so it inherited offline-only machinery (a local directory, a `file://` resolver) it never used. Making the base **abstract** and giving each mode its own concrete child removes that dead inheritance — each child only carries what it needs.

### 1a. The module docstring (top of file)
```text
"""
Browser-fidelity HTML-to-PDF rendering for ADR exports.

This module holds the shared Playwright renderers used by both:

- the serverless ADR export path, which stages HTML from Django-rendered content
- the remote-server export path, which opens the live report page directly
```
- `Browser-fidelity HTML-to-PDF rendering for ADR exports.` — describes the module's job for both callers.
- `the serverless … stages HTML …` / `the remote-server … opens the live report page directly` — documents the two callers, making the dual purpose explicit.

```text
from abc import ABC, abstractmethod
```
- New import. `ABC` is the base for "abstract class"; `abstractmethod` marks methods children **must** implement. This is what enforces the new seam contract.

### 1b. `_BasePlaywrightPDFRenderer(ABC)` — the shared pipeline (abstract)
This is the old `PlaywrightPDFRenderer`, minus anything offline-specific, now abstract.

```text
class _BasePlaywrightPDFRenderer(ABC):
    """Shared Playwright browser-to-PDF render pipeline for ADR reports.

    Subclasses supply the navigation target and browser-context setup for either
    a staged offline HTML bundle or a live ADR report URL.
    """
```
- `class _BasePlaywrightPDFRenderer(ABC):` — declares an abstract base. You cannot do `_BasePlaywrightPDFRenderer()` directly; Python raises `TypeError` because of the abstract methods below. The docstring states the contract: children provide the "where to navigate" and "how to set up the browser" pieces.

```text
    def __init__(
        self,
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with shared browser-PDF configuration."""
        self._landscape = landscape
        self._margins = self._validate_margins(margins)
        self._render_timeout = self._validate_render_timeout(render_timeout)
        ...
```
- `def __init__(self, *, landscape=…, margins=…, render_timeout=…, …):` — the base now only takes options **common to both modes**. Notice there is **no `html_dir`/`filename`** anymore — those are offline-only and moved down into the offline child.
- `self._margins = self._validate_margins(margins)` / `self._render_timeout = self._validate_render_timeout(render_timeout)` — validate page margins and the time budget up front (unchanged logic).

The base still owns the full render recipe — `render_pdf()`, the readiness pipeline, capture CSS, width measurement, timeout accounting, and the product-browser env handling — exactly as before. Inside `render_pdf()`, the three swappable steps are called as methods:
```text
        navigation_target = self._get_navigation_target()
        ...
        context = self._new_browser_context(browser)
        self._prepare_context(context)
        ...
        page.goto(navigation_target, wait_until="load", timeout=navigation_timeout_ms)
```
- `navigation_target = self._get_navigation_target()` — ask the child "what URL should Chromium open?"
- `context = self._new_browser_context(browser)` — ask the child to build the browser session.
- `self._prepare_context(context)` — ask the child to finish configuring it (block network vs. add cookies).
- `page.goto(navigation_target, …)` — open whatever URL the child supplied.

The three seams are now **abstract** — the base only declares them:
```python
@abstractmethod
def _get_navigation_target(self) -> str:
    """Return the URL Chromium should open for the browser-PDF render pass."""
    raise NotImplementedError


@abstractmethod
def _new_browser_context(self, browser: Any) -> Any:
    """Create the browser context used by this renderer."""
    raise NotImplementedError


@abstractmethod
def _prepare_context(self, context: Any) -> None:
    """Configure the browser context before opening the source page."""
    raise NotImplementedError
```
- `@abstractmethod` (×3) — marks each seam as "must be implemented by a child." If a child forgets one, Python refuses to instantiate it. This is the formal contract that replaced the old concrete defaults.
- `raise NotImplementedError` — a safety net; in practice it's never reached because `@abstractmethod` blocks instantiation first.

> Note: the old base also had `_resolve_entrypoint_path()` (which found the local `index.html`). That was offline-only, so it **moved out** of the base into the offline child (see 1c).

### 1c. `_OfflinePlaywrightPDFRenderer` — the local-file renderer (concrete)
This child renders a staged `file://` bundle. It is what serverless `ADR` uses.

```python
class _OfflinePlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):
    """Render an exported ADR HTML directory to PDF via headless Chromium. ..."""

    def __init__(
        self,
        html_dir: Path | str | None,
        filename: str = "index.html",
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        self._html_dir = (
            None if html_dir is None else Path(html_dir).expanduser().resolve()
        )
        self._filename = filename
        super().__init__(
            landscape=landscape,
            margins=margins,
            render_timeout=render_timeout,
            ansys_installation=ansys_installation,
            ansys_version=ansys_version,
            logger=logger,
        )
```
- `class _OfflinePlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):` — a concrete child of the abstract base.
- `html_dir: Path | str | None` / `filename="index.html"` — the offline-specific inputs: which folder holds the report and which file is the entry point. (These used to live on the old base; now they belong only here.)
- `self._html_dir = None if html_dir is None else Path(html_dir)...` — store an absolute path, or `None`. `.expanduser()` expands `~`; `.resolve()` makes it absolute.
- `super().__init__(landscape=…, …)` — hand the shared options up to the base. Note it does **not** pass `html_dir` (the base no longer accepts it).

```python
def _get_navigation_target(self) -> str:
    """Return the staged HTML bundle entry point for the browser-PDF render pass."""
    return self._resolve_entrypoint_path().as_uri()
```
- Implements seam #1: find the local `index.html` and turn it into a `file://…` URL (`.as_uri()` is correct on Windows and Linux).

```python
def _new_browser_context(self, browser: Any) -> Any:
    ...
    return browser.new_context(
        viewport={...},
        service_workers="block",
        accept_downloads=False,
        offline=True,
    )
```
- Implements seam #2: a deterministic, **offline** session. `viewport` fixes the window size; `service_workers="block"` and `accept_downloads=False` keep things predictable; `offline=True` cuts the network entirely (the bundle is self-contained).

```python
def _prepare_context(self, context: Any) -> None:
    """Configure the offline browser context before opening the staged bundle."""
    self._block_external_requests(context)
```
- Implements seam #3: install request filters that abort any external host (belt-and-suspenders on top of `offline=True`).

```python
def _resolve_entrypoint_path(self) -> Path:
    if self._html_dir is None:
        raise ADRException(
            "Browser PDF HTML directory is not configured for this renderer."
        )
    entrypoint_path = (self._html_dir / self._filename).resolve()
    if not entrypoint_path.is_relative_to(self._html_dir):
        raise ADRException(
            "Browser PDF entry-point file must be inside the exported HTML directory."
        )
    if not entrypoint_path.is_file():
        raise ADRException(
            f"Browser PDF entry-point file does not exist: {entrypoint_path}"
        )
    return entrypoint_path
```
- `if self._html_dir is None: raise ADRException(...)` — defensive: this renderer needs a folder; fail clearly if it wasn't given one.
- `entrypoint_path = (self._html_dir / self._filename).resolve()` — build the full path to the entry file and normalize it.
- `if not entrypoint_path.is_relative_to(self._html_dir): raise …` — **security guard**: reject a `filename` that escapes the folder (e.g. `../../etc/passwd`).
- `if not entrypoint_path.is_file(): raise …` — the file must actually exist.
- `return entrypoint_path` — the validated path. (This whole method moved here from the old base, unchanged.)

### 1d. `_ReportURLPlaywrightPDFRenderer` — the live-URL renderer (the new feature)
This child renders a **live report URL** with login cookies. It is what remote `Server` uses. (It was briefly named `_PlaywrightReportURLPDFRenderer` in the first review; the refactor renamed it and made it a sibling of the offline renderer instead of a child of it.)

```python
class _ReportURLPlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):
    """Render a live ADR report URL to PDF via headless Chromium. ..."""

    def __init__(
        self,
        url: str,
        *,
        auth_cookies: list[dict[str, object]] | None = None,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        logger: Any = None,
    ) -> None:
        self._url = self._validate_url(url)
        self._auth_cookies = [] if auth_cookies is None else list(auth_cookies)
        super().__init__(
            landscape=landscape,
            margins=margins,
            render_timeout=render_timeout,
            logger=logger,
        )
```
- `class _ReportURLPlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):` — a second concrete child, parallel to the offline one.
- `url: str` — the live report URL to render (required, positional).
- `*,` — everything after is **keyword-only** (callers must write `landscape=True`), which prevents argument mix-ups.
- `auth_cookies: list[dict...] | None = None` — optional cookies that log Chromium into the ADR web session.
- `render_timeout=_BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT` — reuse the base default (30s).
- `self._url = self._validate_url(url)` — validate the URL before anything else.
- `self._auth_cookies = [] if auth_cookies is None else list(auth_cookies)` — normalize to a list; `list(...)` makes a private copy so later caller changes can't mutate our state.
- `super().__init__(landscape=…, …)` — initialize the shared base. Note it passes **no `html_dir`** (there's no local folder; the base doesn't take one).

```python
def _get_navigation_target(self) -> str:
    return self._url
```
- Seam #1: Chromium opens the **live URL** (not a file).

```python
def _new_browser_context(self, browser: Any) -> Any:
    ...
    return browser.new_context(
        viewport={...},
        service_workers="block",
        accept_downloads=False,
    )
```
- Seam #2: same as offline **except `offline=True` is gone**. The live path *must* stay online so Chromium can fetch the report HTML + assets from the running ADR server. (This single missing argument is the key behavioral difference, and a test checks it.)

```python
def _prepare_context(self, context: Any) -> None:
    if self._auth_cookies:
        context.add_cookies(self._auth_cookies)
```
- Seam #3: instead of blocking the network, **inject the login cookies** so Chromium is recognized as the authenticated user. `context.add_cookies(...)` is the official Playwright call. Does nothing if there are no cookies (anonymous server).

```python
@staticmethod
def _validate_url(url: str) -> str:
    parsed_url = urlsplit(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ADRException(f"Browser PDF report URL is not valid: {url!r}")
    return url
```
- `@staticmethod` — a pure helper, no `self` needed.
- `parsed_url = urlsplit(url)` — split the URL into parts (scheme like `http`, host like `127.0.0.1:8000`, path…).
- `if not parsed_url.scheme or not parsed_url.netloc:` — reject anything that isn't an absolute URL (a bare `/reports/...` path has no scheme/host).
- `raise ADRException(... {url!r})` — `!r` shows the value with quotes so an empty/odd URL is visible.
- `return url` — hand back the validated URL.

> Also renamed in this file: the metadata class `PlaywrightBrowserBinaryInfo` → `_PlaywrightBrowserBinaryInfo` (now private). Pure rename; same fields and behavior. The only name in this module without a leading underscore is the helper function `resolve_playwright_browser_binary_info`.

---

## 2. `utils/report_utils.py` — login flow extracted

**What this file does:** Low-level HTTP helpers for talking to the ADR server.

**What changed:** The Django *web login* steps (which were buried inside `run_web_request`) were pulled out into a new reusable function `authenticate_web_session`, so the new browser-PDF code can log in and grab the same cookies. `run_web_request`'s public behavior is unchanged. *(This file was not touched by the latest refactor.)*

### 2a. `run_web_request` — now delegates the login
**Before**, this function unpacked credentials and logged in inline. **After:**
```python
session = authenticate_web_session(server)
response = None

if session is not None:
    resource_url = server.build_request_url(relative_url)
    req = requests.Request(method, resource_url, data=data, headers=headers)
    prepped_req = session.prepare_request(req)
    # session.send can take many more kwargs as needed
    response = session.send(prepped_req, stream=stream)

return response
```
- `session = authenticate_web_session(server)` — do the login via the new helper; get back a logged-in session, or `None` if login isn't possible/failed.
- `response = None` — default result if we can't authenticate.
- `if session is not None:` — only make the real request when we actually have a logged-in session. **This is the key robustness win:** the old code blindly unpacked credentials and would crash if none were configured; now it just returns `None`.
- `resource_url = server.build_request_url(relative_url)` — turn the relative path into a full URL.
- `req = requests.Request(...)` / `prepped_req = session.prepare_request(req)` — build and "prepare" (finalize headers/cookies) the request.
- `response = session.send(prepped_req, stream=stream)` — send it on the authenticated session (so the login cookies ride along).
- `return response` — same return type as before: a `Response` or `None`.

> **Compatibility note:** the only production caller, `Server.get_file`, already does `if r is not None:`, so returning `None` (instead of crashing) is handled safely.

### 2b. `authenticate_web_session` — the new helper
```python
def authenticate_web_session(server):
    """Authenticate the server's shared requests session for browser-facing pages. ..."""
    credentials = server.get_auth()
    # Browser-facing downloads can be attempted before username/password auth is configured.
    # Treat that as an unauthenticated session instead of crashing during tuple unpacking.
    if credentials is None:
        return None

    username, passwd = credentials
    login_url = server.build_request_url("/login/")

    session = server._http_session
```
- `credentials = server.get_auth()` — fetch `(username, password)` or `None`. (`get_auth()` returns `None` when no credentials are set.)
- `if credentials is None: return None` — no credentials → no authenticated session; bail gracefully. The comment explains *why* (avoids the old crash).
- `username, passwd = credentials` — only unpack once we know it's a real tuple.
- `login_url = server.build_request_url("/login/")` — the Django login endpoint.
- `session = server._http_session` — reuse the server's shared session object (so cookies persist across calls).

```python
if login_response.status_code == requests.codes.ok:
    return session

return None
```
- `if login_response.status_code == requests.codes.ok:` — login succeeded (HTTP 200)…
- `return session` — hand back the now-logged-in session for the caller to reuse.
- `return None` — login failed → signal "no session" instead of returning a half-logged-in object.

(The CSRF-token fetch and the `session.post(login_url, data={...})` between these lines are unchanged from the original `run_web_request`; they were just relocated into this helper.)

---

## 3. `utils/report_remote_server.py` — the remote browser-PDF entry point

**What this file does:** The `Server` class is the client's handle to a *remote* ADR web service (REST + browser pages).

**What changed:** (a) new imports; (b) the old `export_report_as_html` was split into a reusable private downloader (`_download_report_as_html_bundle`) plus a thin public wrapper; (c) two new cookie helpers; (d) the new public `export_report_as_browser_pdf`. *(The latest refactor only changed one class name in this file — see 3f.)*

### 3a. New imports
```python
from http.cookiejar import Cookie

...
from ..exceptions import ADRException
```
- `from http.cookiejar import Cookie` — the standard-library cookie type. Used only as a type hint so readers know exactly what `_build_playwright_cookie` consumes.
- `from ..exceptions import ADRException` — the project's error type, so this module can raise consistent errors.

### 3b. `_download_report_as_html_bundle` (extracted private helper)
This is the body of the **old** `export_report_as_html`, moved into a private method so both HTML export and (potential) other flows can share it. Key lines:
```python
url = self.build_url_with_query(report_guid, query or {}, item_filter)
resolved_ansys_version = self.get_api_version().get(
    "ansys_version", self._ansys_version
)
if ansys_version:
    resolved_ansys_version = ansys_version
```
- `url = self.build_url_with_query(report_guid, query or {}, item_filter)` — build the download URL; `query or {}` means "use an empty dict if `query` is `None`."
- `resolved_ansys_version = self.get_api_version().get("ansys_version", self._ansys_version)` — ask the server which Ansys version it is, falling back to the locally known one. (Renamed from `_ansys_version` to the clearer `resolved_ansys_version`.)
- `if ansys_version: resolved_ansys_version = ansys_version` — an explicit caller override wins.

The rest builds a `ReportDownloadHTML` worker and calls `.download()` — unchanged logic, just relocated. **The caller is now responsible for setting `query["print"]`**, which is what the wrapper does next.

### 3c. `export_report_as_html` (now a thin wrapper — same public behavior)
```python
if query is None:
    query = {}
query["print"] = "html"
self._download_report_as_html_bundle(
    report_guid=report_guid, directory_name=directory_name, query=query, ...
)
```
- `if query is None: query = {}` then `query["print"] = "html"` — set the "give me the HTML variant" flag (identical to before).
- `self._download_report_as_html_bundle(...)` — delegate the actual download. Net effect for users: **exactly the same as before.**

### 3d. `_get_browser_auth_cookies` — log in and collect cookies
```python
def _get_browser_auth_cookies(self) -> list[dict[str, object]]:
    ...
    if self.get_auth() is None:
        return []

    session = report_utils.authenticate_web_session(self)
    if session is None:
        raise ADRException(
            "Unable to authenticate the browser PDF web session for report export."
        )

    base_url = self.get_URL()
    cookies: list[dict[str, object]] = []
    for cookie in session.cookies:
        cookies.append(self._build_playwright_cookie(cookie, base_url=base_url))
    return cookies
```
- `if self.get_auth() is None: return []` — if no credentials are configured, the server is anonymous: return an **empty** cookie list (Chromium will open the report with no login). No need to even attempt a login.
- `session = report_utils.authenticate_web_session(self)` — log the shared session into the ADR web UI (reusing the helper from §2).
- `if session is None: raise ADRException(...)` — credentials existed but login failed → stop with a clear error (don't silently render an unauthenticated page).
- `base_url = self.get_URL()` — the server's base URL, used as a fallback scope for cookies that don't carry their own domain.
- `for cookie in session.cookies:` — iterate every cookie the login produced (e.g. `csrftoken`, `sessionid`).
- `cookies.append(self._build_playwright_cookie(cookie, base_url=base_url))` — convert each `requests` cookie into Playwright's format.
- `return cookies` — the list to seed into the browser context.

### 3e. `_build_playwright_cookie` — translate one cookie
`requests` cookies and Playwright cookies use different shapes; this converts one to the other.
```python
playwright_cookie: dict[str, object] = {
    "name": cookie.name,
    "value": cookie.value,
    "secure": bool(cookie.secure),
}
```
- Start with the always-present fields: the cookie's `name`, `value`, and whether it's HTTPS-only (`secure`).

```python
if cookie.domain:
    playwright_cookie["domain"] = cookie.domain
    playwright_cookie["path"] = cookie.path or "/"
elif base_url:
    playwright_cookie["url"] = base_url
else:
    raise ADRException(
        f"Browser PDF authentication cookie is missing a domain and base URL: {cookie.name!r}"
    )
```
- Playwright requires **either** a `domain`+`path` **or** a `url` to scope the cookie.
- `if cookie.domain:` — preferred: copy the server-issued `domain` and `path` (defaulting path to `/`). This keeps the exact same scoping `requests` used.
- `elif base_url:` — fallback: if the cookie has no domain, scope it to the server's base URL.
- `else: raise ADRException(...)` — neither available → fail clearly rather than send Playwright an invalid cookie.

```python
if cookie.expires is not None:
    playwright_cookie["expires"] = float(cookie.expires)
```
- Copy the expiry only if present; Playwright wants it as a float (Unix seconds).

```python
if cookie.has_nonstandard_attr("HttpOnly") or cookie.has_nonstandard_attr("httponly"):
    playwright_cookie["httpOnly"] = True
```
- `has_nonstandard_attr(...)` is the **public** `http.cookiejar` way to check flags like `HttpOnly` (which is presence-based, not a value). Checking both capitalizations handles servers that differ in case. The code comment explicitly notes this avoids touching private internals — good practice.

```python
same_site = None
for attr_name in ("SameSite", "samesite"):
    if cookie.has_nonstandard_attr(attr_name):
        same_site = cookie.get_nonstandard_attr(attr_name)
        break
if same_site in {"Strict", "Lax", "None"}:
    playwright_cookie["sameSite"] = same_site

return playwright_cookie
```
- Loop both capitalizations of the `SameSite` attribute; grab its value if present.
- `if same_site in {"Strict", "Lax", "None"}:` — only forward a value Playwright actually accepts (its API allows exactly these three). Anything else is dropped rather than risking an invalid cookie.
- `return playwright_cookie` — the finished Playwright-shaped dict.

> **Why a whole helper?** `requests` exposes cookie flags through accessor methods, while Playwright wants a flat dict with specific keys. This translator is the glue; it's verified against Playwright 1.60's documented cookie schema.

### 3f. `export_report_as_browser_pdf` — the new public Server method
```python
if not file_name:
    raise ADRException("A non-empty file_name must be provided for browser PDF export.")
```
- Reject an empty output filename up front — you can't write a PDF with nowhere to put it.

```python
browser_query = dict(query or {})
browser_query["print"] = "pdf"
output_path = Path(os.path.abspath(file_name))
```
- `browser_query = dict(query or {})` — make a **copy** of the caller's query dict (so the next line can't pollute the caller's reusable dict — a subtle but thoughtful detail).
- `browser_query["print"] = "pdf"` — ask the server for the PDF-styled variant of the page.
- `output_path = Path(os.path.abspath(file_name))` — turn the filename into an absolute path that works on any OS.

```text
        try:
            from .pdf_renderer import _ReportURLPlaywrightPDFRenderer

            report_url = self.build_url_with_query(report_guid, browser_query, item_filter)
            browser_auth_cookies = self._get_browser_auth_cookies()
```
- `from .pdf_renderer import _ReportURLPlaywrightPDFRenderer` — **lazy import**: Playwright is only loaded if the user actually requests browser-PDF, so normal server use doesn't pay that import cost/dependency. (The class name here is the only line the latest refactor touched in this file — it was `_PlaywrightReportURLPDFRenderer` before.)
- `report_url = self.build_url_with_query(...)` — construct the live URL Chromium will open.
- `browser_auth_cookies = self._get_browser_auth_cookies()` — log in and gather the cookies (from §3d).

```python
renderer = _ReportURLPlaywrightPDFRenderer(
    url=report_url,
    auth_cookies=browser_auth_cookies,
    landscape=landscape,
    margins=margins,
    render_timeout=render_timeout,
    logger=logger,
)
pdf_bytes = renderer.render_pdf()
output_path.write_bytes(pdf_bytes)
```
- Build the live-URL renderer with the URL, cookies, and visual options.
- `pdf_bytes = renderer.render_pdf()` — run the (inherited) full render pipeline and get raw PDF bytes.
- `output_path.write_bytes(pdf_bytes)` — save the PDF to disk (cross-platform).

```text
        except ADRException:
            raise
        except Exception as exc:
            raise ADRException(f"Browser PDF export failed: {exc}") from exc
```
- `except ADRException: raise` — if it's already our error type (with a precise message), let it pass through untouched.
- `except Exception as exc: raise ADRException(...) from exc` — wrap any *other* failure (including a disk write error) in one consistent `ADRException`, while `from exc` preserves the original cause for debugging. So callers only ever have to handle one error type.

---

## 4. `adr_report.py` — the public `Report.export_browser_pdf` method

**What this file does:** The `Report` class is the user-facing handle to a single report on a connected `Service`.

**What changed:** a module logger was added, three disconnected-state guards were fixed (they used to crash), two error returns were normalized to `False`, and the new `export_browser_pdf` method was added. *(Not touched by the latest refactor.)*

### 4a. Module logger
```python
import logging

...
LOGGER = logging.getLogger(__name__)
```
- `import logging` / `LOGGER = logging.getLogger(__name__)` — a module-level logger. Needed because some error paths happen when there is **no** `Service` object to log through.

### 4b. The "no service" guard fix (appears in 3 methods)
```python
if self.service is None:  # pragma: no cover
    # Detached Report objects cannot forward errors through a Service logger yet.
    LOGGER.error("No connection to any report")
    return False
```
- `if self.service is None:` — the report isn't attached to a service.
- `LOGGER.error("No connection to any report")` — **the fix:** the old code wrote `self.service.logger.error(...)` here, which is impossible when `self.service` is `None` (it would raise `AttributeError`). Using the module `LOGGER` actually works.
- `return False` — return a proper boolean failure. (Two methods previously returned `""` here; now they return `False`, matching their documented `bool` return type. Both are falsy, so `if not result:` checks behave the same.)

### 4c. The new method signature & docstring
```text
    def export_browser_pdf(
        self,
        file_name: str = "",
        query_params: dict | None = None,
        item_filter: str | None = None,
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = 30.0,
    ) -> bool:
```
- `file_name: str = ""` — where to write the PDF.
- `query_params: dict | None = None` — report-template parameters (e.g. `{"colormode": "dark"}`); forwarded to the server.
- `item_filter: str | None = None` — an ADR filter string to pick which items render.
- `*,` — again, the visual options below are keyword-only.
- `landscape` / `margins` / `render_timeout` — orientation, page margins, and the render time budget (seconds).
- `-> bool` — returns `True` on success, `False` on failure (same contract as `export_pdf`/`export_html`).

The docstring explains the difference from `export_pdf` (it uses headless Chromium to preserve JS/Plotly/MathJax fidelity) and warns that on remote connections a Chromium browser must be installed locally.

### 4d. The method body
```python
success = False
if self.service is None:
    LOGGER.error("No connection to any report")
    return False
if self.service.serverobj is None:
    self.service.logger.error("No connection to any server")
    return False
```
- `success = False` — default result.
- `if self.service is None: … return False` — not attached to a service (uses the safe `LOGGER`).
- `if self.service.serverobj is None: … return False` — attached to a service but it has no live server connection. Here `self.service` exists, so `self.service.logger` is safe to use.

```python
try:
    if query_params is None:
        query_params = {}
    self.service.serverobj.export_report_as_browser_pdf(
        report_guid=self.report.guid,
        file_name=file_name,
        query=query_params,
        item_filter=item_filter,
        landscape=landscape,
        margins=margins,
        render_timeout=render_timeout,
    )
    success = True
except Exception as e:
    self.service.logger.error(f"Can not export browser pdf report: {str(e)}")
return success
```
- `if query_params is None: query_params = {}` — normalize to an empty dict.
- `self.service.serverobj.export_report_as_browser_pdf(...)` — hand off to the `Server` method from §3f, forwarding every option plus this report's `guid`.
- `success = True` — only reached if the call didn't throw.
- `except Exception as e: … return success` — on any failure, log it and return `False` (never raise to the user). This is the standard "boolean status" pattern used by the sibling export methods.

---

## 5. `serverless/adr.py` — one import line

```python
from ..utils.pdf_renderer import _OfflinePlaywrightPDFRenderer

...
renderer = _OfflinePlaywrightPDFRenderer(html_dir=tmp_path, ...)
```
- The serverless export path imports the **offline** renderer from its new home (`..utils.pdf_renderer`) and constructs it with `html_dir=tmp_path`. Two things changed here over the life of the branch: the import path (file move) and the class name (`PlaywrightPDFRenderer` → `_OfflinePlaywrightPDFRenderer`, from the hierarchy split). The import is still lazy (inside the method) so Playwright loads only on the export path. Functionally identical; serverless still renders a staged offline bundle.

---

## 6. Tests — what each one locks in

You don't need to read the test code to trust the coverage; here's what each new test *proves*. (All external pieces — Playwright, the renderer, the login helper — are replaced with fakes via `monkeypatch`, so these are fast, deterministic unit tests with no real browser or server.)

> **Effect of the latest refactor on tests:** only **identifiers** changed — tests that built `PlaywrightPDFRenderer(html_dir=…)` now build `_OfflinePlaywrightPDFRenderer(html_dir=…)` (since the base is abstract and can't be instantiated), and the live-URL tests use `_ReportURLPlaywrightPDFRenderer`. **No test was added or removed**, and no assertion logic changed.

### `tests/test_report.py` (the public `Report` method)
- **`test_export_browser_pdf_forwards_options`** — calling `Report.export_browser_pdf(...)` passes every argument (guid, file_name, query, filter, landscape, margins, timeout) through to the `Server` method unchanged, and returns `True`.
- **`test_export_browser_pdf_returns_false_on_failure`** — if the underlying export raises, the method swallows it and returns `False` (never crashes the caller).
- **`test_export_browser_pdf_returns_false_without_service`** — a report with no `Service` returns `False` (and doesn't crash on the `None` service — the §4b fix).
- **`test_export_browser_pdf_returns_false_without_serverobj`** — a report whose service has no live server returns `False`.

### `tests/test_report_remote_server.py` (the `Server` method + cookie bridge)
- **`test_export_html_sets_html_print_query`** — the refactored `export_report_as_html` still sets `print="html"` and forwards all args to the new private downloader (proves the split didn't change behavior).
- **`test_export_browser_pdf_renders_live_report_url`** — end-to-end (with fakes): it builds the live URL with `print="pdf"`, logs in, converts both a `csrftoken` and a `sessionid` cookie into the exact Playwright shapes, passes options to the renderer, writes the returned bytes to disk, and crucially **does not** stage an offline HTML bundle and **does not** mutate the caller's `query` dict.
- **`test_export_browser_pdf_requires_file_name`** — empty `file_name` raises `ADRException` ("non-empty file_name").
- **`test_export_browser_pdf_wraps_renderer_failures`** — a renderer exception is re-wrapped as `ADRException("Browser PDF export failed…")`.
- **`test_export_browser_pdf_wraps_output_write_failures`** — if writing the file fails (the test points the output at a directory), it's also wrapped as the same `ADRException` (callers get one error type).
- **`test_build_playwright_cookie_uses_base_url_when_cookie_has_no_domain`** — a domain-less cookie is scoped via `url=base_url`.
- **`test_build_playwright_cookie_requires_domain_or_base_url`** — a cookie with neither domain nor base URL raises a clear `ADRException`.
- **`test_get_browser_auth_cookies_returns_empty_list_without_configured_auth`** — an anonymous server returns `[]` and never even attempts a login.
- **`test_get_browser_auth_cookies_requires_authenticated_session`** — credentials present but login fails → raises `ADRException`.

### `tests/test_report_utils.py` (the login helper + refactor)
- **`test_authenticate_web_session_logs_in_shared_session`** — verifies the login choreography: GET `/login/` for the CSRF token, then POST username/password/CSRF/next, and return the same session object.
- **`test_authenticate_web_session_returns_none_without_configured_auth`** — no credentials → returns `None` (no crash).
- **`test_run_web_request_uses_authenticated_session`** — when authenticated, `run_web_request` prepares and sends the request on that session and returns the response.
- **`test_run_web_request_returns_none_without_authenticated_session`** — when login is unavailable, it returns `None` (the safe path the one production caller relies on).

### `tests/serverless/test_pdf_renderer.py` (renderer + new class)
- **`test_live_report_url_renderer_navigates_to_report_url`** — the URL renderer navigates to the live URL, seeds cookies via `add_cookies`, creates an **online** context (no `offline=True`), and does **not** install the offline network blocks (`route`/`route_web_socket` not called).
- **`test_live_report_url_renderer_validates_absolute_urls`** — a relative URL raises `ADRException` ("report URL is not valid").
- **`test_renderer_requires_html_dir_for_offline_entrypoint_resolution`** — calling the file-path resolver on a `_OfflinePlaywrightPDFRenderer(html_dir=None)` raises the clear "HTML directory is not configured" error.
- **`test_playwright_pdf_rounds_tiny_browser_timeouts_up_to_one_millisecond`** — a tiny positive timeout rounds **up to 1 ms** (because Playwright treats `timeout=0` as "no timeout," which must never happen by accident).
- The other offline tests now construct `_OfflinePlaywrightPDFRenderer` instead of the (now-abstract) base. Pure mechanical update; same assertions.

### `tests/serverless/test_adr.py` and `test_pdf_renderer_browser_binary.py`
- Only **import paths / class names** changed (`utils.pdf_renderer`, `_OfflinePlaywrightPDFRenderer`, `_PlaywrightBrowserBinaryInfo`), following the move + privatization. No behavior change.

---

## 7. Docs/meta changes
- **`CHANGELOG.md`** — adds an "Added" entry for `Report.export_browser_pdf()`. (Tip: it doesn't mention the `Report.export_pdf`/`export_html` return-value normalization — see REVIEW Issue M3.)
- **`doc/source/examples_source/25-intermediate/00-tagging.py`** and **`doc/source/serverless/caveats.rst`** — each only lengthens an RST title underline by one `=` (7 → 8). Valid RST, harmless, but unrelated to this feature (REVIEW Issue H1).
- **`uv.lock`** — refreshed after dependency upgrades. The churn is transitive; the Playwright pin is still `==1.60.0`, so the browser-PDF behavior and all the API-grounding above are unaffected.

---

## 8. One-paragraph summary for a busy reviewer
This branch adds browser-fidelity PDF export for the remote ADR service by (1) moving the existing Playwright renderer into a shared `utils` module and refactoring it into an **abstract base** (`_BasePlaywrightPDFRenderer`) with **two concrete children** — `_OfflinePlaywrightPDFRenderer` (local `file://` bundle) and the new `_ReportURLPlaywrightPDFRenderer` (live URL with network ON and login cookies injected) — and (2) wiring a clean public path `Report.export_browser_pdf → Server.export_report_as_browser_pdf → _ReportURLPlaywrightPDFRenderer`. The login flow is reused (not reinvented) via a new `authenticate_web_session` helper, and a `requests→Playwright` cookie translator bridges the two libraries using only public, documented APIs. Every renderer class is private; everything is additive; the one refactored function keeps its contract and only improves a crash into a graceful `None`. Nothing here breaks existing callers.

---

## 9. Post-review changes (addressing REVIEW.md, 2026-06-29)

After the review, every REVIEW item was implemented. This section walks the changed code in the same line-by-line style. (See REVIEW.md §13 for the per-item commit table.)

### 9a. M2 — actionable error when Chromium is missing (`pdf_renderer.py`)
New import:
```python
from playwright.sync_api import Error as PlaywrightError
```
- Brings in Playwright's base error type so the launch step can recognize a failed browser launch by its **type**, rather than parsing the driver's English message (which can change between versions).

The `launch()` call inside `_BasePlaywrightPDFRenderer.render_pdf` is now wrapped:
```python
try:
    browser = playwright.chromium.launch(
        headless=True,
        timeout=self._remaining_browser_phase_timeout_ms(
            browser_phase_deadline, "browser launch"
        ),
    )
except PlaywrightTimeoutError:
    raise
except PlaywrightError as exc:
    raise ADRException(
        "Failed to launch headless Chromium for browser PDF export. If the "
        "Playwright browser is not installed, run 'playwright install chromium' "
        "on the client machine."
    ) from exc
```
- `try:` / `browser = playwright.chromium.launch(...)` — the same launch as before, now guarded.
- `except PlaywrightTimeoutError: raise` — a launch *timeout* is re-raised untouched so the existing outer handler still reports it as a timeout. (`TimeoutError` subclasses `Error`, so it must be caught first, or the next clause would mislabel it.)
- `except PlaywrightError as exc:` — any *other* launch failure (most commonly: the browser binary isn't installed)…
- `raise ADRException(...) from exc` — …becomes a clear, actionable message telling the user to run `playwright install chromium`, with the original Playwright error chained as the cause for debugging.

### 9b. L2 — value-less cookie guard (`report_remote_server.py`)
```text
            "value": cookie.value if cookie.value is not None else "",
```
- A cookie from `http.cookiejar` can have `value is None` (a header like `Set-Cookie: name` with no `=value`). Playwright requires a string value, so `None` is normalized to `""`. Real string values pass through unchanged.

### 9c. Comment / documentation changes (no behavior change)
- **M1** (`adr_report.py`): added an `Examples` block to `Report.export_browser_pdf`, matching the `::` style of `export_pdf`/`export_html`.
- **L1** (`pdf_renderer.py`): expanded the live renderer's `_new_browser_context` docstring to state that the live path permits network egress and that the seeded auth cookies stay domain-scoped (so they only return to the originating ADR service).
- **L3** (`adr_report.py`, `report_remote_server.py`): a comment beside each `render_timeout=30.0` default explaining it mirrors `_BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT` and is kept inline so importing these modules does not eagerly import the Playwright renderer (and Playwright itself).
- **M3** (`CHANGELOG.md`): a `Fixed` entry recording the `export_pdf`/`export_html` `""`→`False` return change and the crash-fix.
- **H1**: reverted the two unrelated RST title-underline edits, so the branch diff is browser-PDF-only.

### 9d. Test changes
- **M2 coverage** — `test_playwright_pdf_hints_browser_install_when_launch_raises_playwright_error`: a Playwright `Error` at launch yields the install hint and chains the cause.
- **T5** — `test_base_renderer_cannot_be_instantiated_directly`: the abstract base raises `TypeError` on direct construction.
- **T1**: the live-renderer test now asserts `new_context` was called once and that `offline` is absent from its kwargs, instead of pinning the full (shared) kwargs.
- **L2 coverage** — `test_build_playwright_cookie_normalizes_value_less_cookie_to_empty_string`: a `None`-valued cookie converts to `""`.
- **T2**: the omnibus live-render test now asserts only the forwarded cookie names/order; the exact cookie shape stays in the dedicated `_build_playwright_cookie` tests.
- **T3**: removed the unused `_ansys_version=252` stub from the `Report` test helpers.
- **T4**: the auth-session test uses `bytes` credentials (`b"nexus"`, `b"cei"`), matching what `get_auth()` actually returns.

---

## 10. Round 2 — product-packed browser + zero Playwright leakage (2026-06-30)

Two corrections from maintainer feedback. (REVIEW.md §14 has the commit table.)

### 10a. The remote path now uses the product-packed browser binary
Before, `Server.export_report_as_browser_pdf` built the live-URL renderer **without** an Ansys install/version, so the base renderer skipped `_resolve_playwright_browser_binary()` and Chromium launched from whatever browser happened to be on the machine. Now the local install is threaded through, exactly like the legacy `export_pdf`:

- `Report.export_browser_pdf` adds two forwarded arguments:
  ```text
  exec_basis=self.service._ansys_installation,
  ansys_version=self.service._ansys_version,
  ```
  — the same install root/version the report's service already knows.
- `Server.export_report_as_browser_pdf(..., exec_basis=None, ansys_version=None)` accepts them and passes them to the renderer as `ansys_installation=exec_basis, ansys_version=ansys_version`.
- `_ReportURLPlaywrightPDFRenderer.__init__(..., ansys_installation=None, ansys_version=None)` forwards them to the shared base, so the live-URL render resolves and uses the product-shipped browser binary. If that binary is missing, the base raises the existing clean, product-oriented error ("…requires a valid product-shipped browser binary…").

### 10b. Callers never see Playwright errors/info
Every browser-PDF handler that wraps a Playwright operation now logs the trace and raises a clean ADR error with **no chaining**:
```text
except Exception:
    self._logger.debug("Browser PDF rendering failed.", exc_info=True)   # trace -> logs only
    raise ADRException("Browser PDF rendering failed.") from None         # clean error, no chain
```
- `from None` is the important part. Plain `raise ADRException(...)` inside an `except` leaves Python's implicit `__context__` set, and a printed traceback still shows the original ("During handling of the above exception…"). `from None` sets `__suppress_context__`, so the Playwright/driver exception never appears in the traceback. The full detail is still available via debug logging.
- This applies to: `render_pdf`'s timeout and catch-all handlers and its `render_timeout` validation (`pdf_renderer.py`), `Server.export_report_as_browser_pdf` (`report_remote_server.py`), and the serverless `_render_template_as_browser_pdf` (`serverless/adr.py`).
- The launch-time "run `playwright install chromium`" hint added earlier was **removed** — it was wrong (the binary is product-packed, not user-installed).
- Two product-facing messages were degenericized from "Playwright browser binary" to "browser binary" so even the supported-version guidance names no third-party tool.

### 10c. Tests
Removed the install-hint test. The launch-failure test now asserts a clean message, `__cause__ is None`, `__suppress_context__ is True`, and no "playwright" text. Timeout / new-context / wrap tests assert the clean message and suppressed context. Added a renderer test that the live-URL renderer forwards the install metadata, and Server/Report assertions that `exec_basis`/`ansys_version` are forwarded.

### 10d. Follow-ups (commit `02edaaf0`)
- **Param rename:** the remote install argument is now `ansys_installation` (was `exec_basis`, which only echoed the legacy `export_report_as_pdf`). The forwarded value is unchanged — `Report.export_browser_pdf` still passes `self.service._ansys_installation` (the resolved install root).
- **Verified** the remote path actually uses the packed binary: against a real `apex<ver>/machines/<arch>/playwright-browsers` layout, the renderer resolves that binary and points `PLAYWRIGHT_BROWSERS_PATH` at it during the render (restoring it after), with no ambient fallback.
- **Docstrings scrubbed:** the public methods' docstrings no longer name "Playwright"/"Chromium" — they say "a headless browser", and the margin format is documented as CSS length strings (e.g. `"10mm"`). Internal/private docstrings, comments, and code identifiers keep the names (maintainer-facing).
