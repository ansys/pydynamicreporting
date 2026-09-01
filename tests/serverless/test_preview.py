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

"""Unit tests for local serverless ADR report previews."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from django.urls.resolvers import RegexPattern, URLResolver
import pytest

from ansys.dynamicreporting.core.exceptions import ADRException, ImproperlyConfiguredError
from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.serverless import preview as preview_module
from ansys.dynamicreporting.core.serverless.preview import _ReportPreviewServer


def _make_preview_server(
    tmp_path: Path,
    *,
    render_report=None,
    static_url: str = "/static/",
    media_url: str = "/media/",
    port: int = 8000,
) -> _ReportPreviewServer:
    static_directory = tmp_path / "static"
    static_directory.mkdir(exist_ok=True)
    media_directory = tmp_path / "media"
    media_directory.mkdir(exist_ok=True)
    return _ReportPreviewServer(
        render_report=render_report or (lambda request: "<html></html>"),
        static_directory=static_directory,
        media_directory=media_directory,
        static_url=static_url,
        media_url=media_url,
        host="127.0.0.1",
        port=port,
        logger=Mock(),
    )


@pytest.mark.unit
def test_preview_server_routes_report_and_configured_asset_directories(tmp_path):
    """The isolated URL configuration should expose only the report and its assets."""
    server = _make_preview_server(
        tmp_path,
        static_url="/collected.assets/",
        media_url="/report-media/",
    )

    resolver = URLResolver(RegexPattern(r"^/"), server._build_urlconf())

    report_match = resolver.resolve("/")
    assert report_match.func == server._report_view

    static_match = resolver.resolve("/collected.assets/css/site.css")
    assert static_match.func is preview_module.serve
    assert static_match.kwargs == {
        "path": "css/site.css",
        "document_root": str(tmp_path / "static"),
    }

    media_match = resolver.resolve("/report-media/images/result.png")
    assert media_match.func is preview_module.serve
    assert media_match.kwargs == {
        "path": "images/result.png",
        "document_root": str(tmp_path / "media"),
    }


@pytest.mark.unit
def test_preview_server_passes_the_live_request_to_the_renderer(tmp_path, monkeypatch):
    """Each page request should render fresh HTML with that Django request."""
    request = object()
    rendered_requests = []
    response_arguments = {}

    def render_report(current_request):
        rendered_requests.append(current_request)
        return "<html><body>report</body></html>"

    def fake_http_response(content, *, content_type):
        response_arguments.update(content=content, content_type=content_type)
        return response_arguments

    monkeypatch.setattr(preview_module, "HttpResponse", fake_http_response)
    server = _make_preview_server(tmp_path, render_report=render_report)

    response = server._report_view(request)

    assert response is response_arguments
    assert rendered_requests == [request]
    assert response_arguments == {
        "content": "<html><body>report</body></html>",
        "content_type": "text/html",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("static_url", "media_url", "port", "error"),
    [
        ("/assets/", "/assets/", 8000, "must use non-overlapping URL prefixes"),
        ("/assets/", "/assets/media/", 8000, "must use non-overlapping URL prefixes"),
        ("/", "/media/", 8000, "cannot use the report preview's root URL"),
        ("//cdn.example/static/", "/media/", 8000, "must be a local URL path"),
        ("/static/", "/media/", 0, "integer between 1 and 65535"),
    ],
)
def test_preview_server_rejects_ambiguous_or_invalid_routes(
    tmp_path, static_url, media_url, port, error
):
    """Invalid route settings should fail before a socket is opened."""
    with pytest.raises(ImproperlyConfiguredError, match=error):
        _make_preview_server(
            tmp_path,
            static_url=static_url,
            media_url=media_url,
            port=port,
        )


@pytest.mark.unit
def test_preview_server_runs_django_wsgi_app_and_restores_settings(tmp_path, monkeypatch):
    """Preview startup should bind once, open the browser, and restore Django settings."""
    fake_settings = SimpleNamespace(
        ROOT_URLCONF="original.urls",
        ALLOWED_HOSTS=["existing.example"],
    )
    monkeypatch.setattr(preview_module, "settings", fake_settings)

    cache_clear_calls = []
    monkeypatch.setattr(
        preview_module,
        "clear_url_caches",
        lambda: cache_clear_calls.append(True),
    )
    application = object()
    monkeypatch.setattr(preview_module, "get_wsgi_application", lambda: application)

    server_calls = {}

    class FakeHTTPServer:
        server_port = 8123

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            server_calls["closed"] = True

        def serve_forever(self):
            server_calls["served"] = True
            raise KeyboardInterrupt

    def fake_make_server(host, port, wsgi_application):
        server_calls.update(host=host, port=port, application=wsgi_application)
        return FakeHTTPServer()

    monkeypatch.setattr(preview_module, "make_server", fake_make_server)
    open_new_tab = Mock()
    monkeypatch.setattr(preview_module.webbrowser, "open_new_tab", open_new_tab)
    server = _make_preview_server(tmp_path)

    server.serve_forever(open_browser=True)

    assert server_calls == {
        "host": "127.0.0.1",
        "port": 8000,
        "application": application,
        "served": True,
        "closed": True,
    }
    open_new_tab.assert_called_once_with("http://127.0.0.1:8123/")
    assert fake_settings.ROOT_URLCONF == "original.urls"
    assert fake_settings.ALLOWED_HOSTS == ["existing.example"]
    assert cache_clear_calls == [True, True]


def _bare_adr(tmp_path: Path) -> ADR:
    """Build the ADR state needed to test previews without product setup."""
    static_directory = tmp_path / "static"
    static_directory.mkdir(exist_ok=True)
    media_directory = tmp_path / "media"
    media_directory.mkdir(exist_ok=True)

    adr = object.__new__(ADR)
    adr._static_directory = static_directory
    adr._media_directory = media_directory
    adr._static_url = "/static/"
    adr._media_url = "/media/"
    adr._logger = Mock()
    return adr


@pytest.mark.unit
def test_preview_report_forwards_render_and_server_options(tmp_path, monkeypatch):
    """The preview entry point should bind one resolved template to the request view."""
    adr = _bare_adr(tmp_path)
    monkeypatch.setattr(ADR, "ensure_setup", classmethod(lambda cls: None))

    request = object()
    render_calls = []

    class FakeTemplate:
        def render(self, **kwargs):
            render_calls.append(kwargs)
            return "<html>rendered</html>"

    template = FakeTemplate()
    template_get = Mock(return_value=template)
    monkeypatch.setattr(preview_module.Template, "get", template_get)

    server_arguments = {}

    class FakeReportPreviewServer:
        def __init__(self, **kwargs):
            server_arguments.update(kwargs)

        def serve_forever(self, *, open_browser):
            server_arguments["open_browser"] = open_browser
            server_arguments["rendered_html"] = server_arguments["render_report"](request)

    monkeypatch.setattr(
        preview_module,
        "_ReportPreviewServer",
        FakeReportPreviewServer,
    )

    adr.preview_report(
        name="Preview Report",
        host="localhost",
        port=8124,
        open_browser=False,
        context={"plotly": 1},
        item_filter="A|i_tags|cont|preview;",
        embed_scene_data=True,
    )

    assert template_get.call_args_list == [
        call(name="Preview Report"),
        call(name="Preview Report"),
    ]
    assert render_calls == [
        {
            "context": {"plotly": 1},
            "item_filter": "A|i_tags|cont|preview;",
            "embed_scene_data": True,
            "request": request,
        }
    ]
    assert server_arguments["static_directory"] == tmp_path / "static"
    assert server_arguments["media_directory"] == tmp_path / "media"
    assert server_arguments["static_url"] == "/static/"
    assert server_arguments["media_url"] == "/media/"
    assert server_arguments["host"] == "localhost"
    assert server_arguments["port"] == 8124
    assert server_arguments["logger"] is adr._logger
    assert server_arguments["open_browser"] is False
    assert server_arguments["rendered_html"] == "<html>rendered</html>"


@pytest.mark.unit
def test_preview_report_requires_a_report_lookup(tmp_path, monkeypatch):
    """Starting a preview without selecting a report should fail before binding."""
    adr = _bare_adr(tmp_path)
    monkeypatch.setattr(ADR, "ensure_setup", classmethod(lambda cls: None))

    with pytest.raises(ADRException, match="At least one keyword argument"):
        adr.preview_report()


@pytest.mark.unit
def test_preview_report_requires_a_static_directory(tmp_path, monkeypatch):
    """The preview cannot load ADR assets when no static root was configured."""
    adr = _bare_adr(tmp_path)
    adr._static_directory = None
    monkeypatch.setattr(ADR, "ensure_setup", classmethod(lambda cls: None))

    with pytest.raises(ImproperlyConfiguredError, match="must be configured to preview a report"):
        adr.preview_report(name="Preview Report")


@pytest.mark.unit
def test_preview_report_chains_report_lookup_failure(tmp_path, monkeypatch):
    """A missing report should fail before the preview binds."""
    adr = _bare_adr(tmp_path)
    monkeypatch.setattr(ADR, "ensure_setup", classmethod(lambda cls: None))
    lookup_error = RuntimeError("report does not exist")
    monkeypatch.setattr(preview_module.Template, "get", Mock(side_effect=lookup_error))

    with pytest.raises(ADRException, match="Report preview setup failed") as exc_info:
        adr.preview_report(name="Missing Report")

    assert exc_info.value.__cause__ is lookup_error
