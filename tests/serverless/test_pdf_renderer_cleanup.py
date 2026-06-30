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

from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest

from ansys.dynamicreporting.core.serverless import pdf_renderer as pdf_renderer_module
from ansys.dynamicreporting.core.serverless.pdf_renderer import PlaywrightPDFRenderer


@pytest.mark.unit
def test_playwright_pdf_returns_bytes_when_browser_cleanup_fails(tmp_path, monkeypatch):
    html_path = tmp_path / "index.html"
    html_path.write_text("<html><body><p>Cleanup failure</p></body></html>", encoding="utf-8")
    renderer = PlaywrightPDFRenderer(html_dir=tmp_path)

    page = Mock()
    page.pdf.return_value = b"%PDF-mock"
    context = Mock()
    context.new_page.return_value = page
    context.close.side_effect = RuntimeError("context close boom")
    browser = Mock()
    browser.new_context.return_value = context
    browser.close.side_effect = RuntimeError("browser close boom")
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    playwright_manager = MagicMock()
    playwright_manager.__enter__.return_value = playwright

    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", lambda: playwright_manager)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    assert renderer.render_pdf() == b"%PDF-mock"
    context.close.assert_called_once_with()
    browser.close.assert_called_once_with()
