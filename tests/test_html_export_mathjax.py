# Copyright (C) 2023 - 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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

from ansys.dynamicreporting.core.utils.html_export_mathjax import detect_mathjax_version_from_html


def test_detect_mathjax_version_from_html_detects_mathjax_2_loader() -> None:
    """A script tag that loads ``MathJax.js`` should resolve to MathJax 2.x."""
    html = '<script src="/static/website/scripts/mathjax/MathJax.js"></script>'

    assert detect_mathjax_version_from_html(html) == "2"


def test_detect_mathjax_version_from_html_detects_mathjax_4_loader() -> None:
    """A script tag that loads ``tex-mml-chtml.js`` should resolve to MathJax 4.x."""
    html = '<script src="https://cdn.jsdelivr.net/npm/mathjax@4.0.0/tex-mml-chtml.js"></script>'

    assert detect_mathjax_version_from_html(html) == "4"


def test_detect_mathjax_version_from_html_ignores_inline_config_scripts() -> None:
    """Inline MathJax config without a loader URL should remain inconclusive."""
    html = """
    <script>
      window.MathJax = {tex: {inlineMath: [['$', '$']]}};
    </script>
    """

    assert detect_mathjax_version_from_html(html) == "unknown"


def test_detect_mathjax_version_from_html_returns_unknown_for_conflicting_loaders() -> None:
    """Conflicting major-version loaders should be treated as unknown."""
    html = """
    <script src="/static/website/scripts/mathjax/MathJax.js"></script>
    <script src="/static/website/scripts/mathjax/tex-mml-chtml.js"></script>
    """

    assert detect_mathjax_version_from_html(html) == "unknown"
