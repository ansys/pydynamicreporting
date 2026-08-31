# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Development web server for one serverless ADR report."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import logging
from pathlib import Path
import re
from types import ModuleType
from urllib.parse import urlsplit
import webbrowser
from wsgiref.simple_server import make_server

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpRequest, HttpResponse
from django.urls import clear_url_caches, path, re_path
from django.urls.resolvers import URLPattern
from django.views.static import serve

from ..exceptions import ImproperlyConfiguredError, InvalidPath


@contextmanager
def _server_settings(urlconf: ModuleType, allowed_hosts: list[str]) -> Iterator[None]:
    """Install the server URL configuration for the lifetime of the server."""
    original_urlconf = getattr(settings, "ROOT_URLCONF", None)
    original_allowed_hosts = settings.ALLOWED_HOSTS
    settings.ROOT_URLCONF = urlconf
    settings.ALLOWED_HOSTS = allowed_hosts
    clear_url_caches()
    try:
        yield
    finally:
        settings.ROOT_URLCONF = original_urlconf
        settings.ALLOWED_HOSTS = original_allowed_hosts
        clear_url_caches()


class _ReportServer:
    """Serve one rendered report and its collected static and media files."""

    def __init__(
        self,
        *,
        render_report: Callable[[HttpRequest], str],
        static_directory: Path,
        media_directory: Path,
        static_url: str,
        media_url: str,
        host: str,
        port: int,
        logger: logging.Logger,
    ) -> None:
        self._render_report = render_report
        self._static_directory = self._require_directory(
            static_directory, option="static_directory"
        )
        self._media_directory = self._require_directory(media_directory, option="media_directory")
        self._static_url = self._validate_asset_url(static_url, option="static_url")
        self._media_url = self._validate_asset_url(media_url, option="media_url")
        if self._static_url.startswith(self._media_url) or self._media_url.startswith(
            self._static_url
        ):
            raise ImproperlyConfiguredError(
                "The 'static_url' and 'media_url' options must use non-overlapping URL prefixes."
            )
        if not isinstance(host, str) or not host:
            raise ImproperlyConfiguredError("The 'host' option must be a non-empty string.")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ImproperlyConfiguredError(
                "The 'port' option must be an integer between 1 and 65535."
            )

        self._host = host
        self._port = port
        self._logger = logger

    @staticmethod
    def _require_directory(directory: Path, *, option: str) -> Path:
        """Return an existing asset directory or raise an ADR path error."""
        directory = Path(directory)
        if not directory.is_dir():
            raise InvalidPath(extra_detail=f"The '{option}' directory does not exist: {directory}")
        return directory

    @staticmethod
    def _validate_asset_url(url: str, *, option: str) -> str:
        """Validate a non-root, relative URL prefix used by an asset route."""
        if not isinstance(url, str) or not url.startswith("/") or not url.endswith("/"):
            raise ImproperlyConfiguredError(
                f"The '{option}' option must start and end with a forward slash."
            )
        if url == "/":
            raise ImproperlyConfiguredError(
                f"The '{option}' option cannot use the report server's root URL."
            )
        parsed_url = urlsplit(url)
        if parsed_url.netloc or parsed_url.query or parsed_url.fragment or "\\" in url:
            raise ImproperlyConfiguredError(
                f"The '{option}' option must be a local URL path without a host, query, or fragment."
            )
        return url

    def _report_view(self, request: HttpRequest) -> HttpResponse:
        """Render the selected report for the current HTTP request."""
        return HttpResponse(self._render_report(request), content_type="text/html")

    @staticmethod
    def _asset_route(url: str, directory: Path) -> URLPattern:
        """Create a development-only route for one collected asset directory."""
        route = re.escape(url.lstrip("/"))
        return re_path(
            rf"^{route}(?P<path>.*)$",
            serve,
            {"document_root": str(directory)},
        )

    def _build_urlconf(self) -> ModuleType:
        """Build an isolated URL configuration for the report server."""
        urlconf = ModuleType("ansys.dynamicreporting.core.serverless._report_server_urlconf")
        urlconf.urlpatterns = [
            path("", self._report_view),
            self._asset_route(self._static_url, self._static_directory),
            self._asset_route(self._media_url, self._media_directory),
        ]
        return urlconf

    def serve_forever(self, *, open_browser: bool) -> None:
        """Run the report server until interrupted."""
        urlconf = self._build_urlconf()
        allowed_hosts = list(settings.ALLOWED_HOSTS)
        for host in (self._host, "localhost", "127.0.0.1", "[::1]"):
            if host not in allowed_hosts:
                allowed_hosts.append(host)

        with _server_settings(urlconf, allowed_hosts):
            application = get_wsgi_application()
            with make_server(self._host, self._port, application) as httpd:
                url = f"http://{self._host}:{httpd.server_port}/"
                self._logger.info(
                    "Serving the serverless ADR report at %s. Press Ctrl+C to stop.", url
                )
                if open_browser:
                    webbrowser.open_new_tab(url)
                try:
                    # Keep report renders serialized because the bundled template engine
                    # maintains process-wide render context.
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    self._logger.info("Stopped the serverless ADR report server.")
