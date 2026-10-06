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

"""Helpers for displaying rendered serverless HTML."""

from html import escape


class _IFrameHTML(str):
    """String-like iframe markup understood by rich display frontends."""

    def _repr_html_(self) -> str:
        """Return the iframe markup for rich display frontends."""
        return str(self)


def _build_iframe(html: str, *, width: int | float, height: int | float) -> _IFrameHTML:
    """Wrap a rendered HTML document in display-ready iframe markup."""
    return _IFrameHTML(
        f'<iframe srcdoc="{escape(html, quote=True)}" '
        f'width="{escape(str(width), quote=True)}" '
        f'height="{escape(str(height), quote=True)}" '
        'sandbox="allow-downloads allow-forms allow-modals allow-popups allow-scripts" '
        'frameborder="0" allowfullscreen></iframe>'
    )


def _display_iframe(iframe: _IFrameHTML) -> None:
    """Display iframe markup in an IPython-compatible frontend."""
    try:
        from IPython.display import display
    except ImportError as exc:
        raise RuntimeError(
            "visualize() requires IPython. Use get_iframe() or render() outside IPython."
        ) from exc
    display(iframe)
