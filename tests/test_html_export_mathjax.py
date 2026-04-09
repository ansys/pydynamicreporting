# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#

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
