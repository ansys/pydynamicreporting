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

"""Load the packaged JavaScript used by the browser-PDF renderer."""

from functools import cache
from importlib.resources import files

_RUNTIME_SCRIPT_NAMES: tuple[str, ...] = (
    "bootstrap.js",
    "readiness.js",
    "capture.js",
    "fit_visuals.js",
    "cohesion.js",
    "fragmentation.js",
)
_INVOCATION_SCRIPT_NAME = "invoke.js"


def _read_script(script_name: str) -> str:
    """Return one UTF-8 JavaScript resource from this package."""
    return files(__package__).joinpath(script_name).read_text(encoding="utf-8")


@cache
def browser_pdf_runtime_script() -> str:
    """Return the ordered browser-PDF runtime as one cached script.

    For example, resources containing ``"A;"`` and ``"B;"`` become
    ``"A;\nB;"`` in dependency order.
    """
    # Each file is an isolated module that extends the namespace created by bootstrap.js.
    # Concatenating in this fixed order keeps browser installation to one Playwright call.
    return "\n".join(_read_script(script_name) for script_name in _RUNTIME_SCRIPT_NAMES)


@cache
def browser_pdf_invocation_script() -> str:
    """Return the cached bridge used to invoke an installed runtime method."""
    return _read_script(_INVOCATION_SCRIPT_NAME)
