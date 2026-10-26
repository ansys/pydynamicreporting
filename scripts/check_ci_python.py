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

"""Check the CI interpreter against the eMudhra security release baseline."""

import platform
import sys

MINIMUM_PATCH = {(3, 11): 18, (3, 12): 16, (3, 13): 18, (3, 14): 10}


def python_meets_ci_security_baseline(version: tuple[int, int, int]) -> bool:
    """Return whether the version meets a supported CI branch's patch minimum."""
    major, minor, patch = version
    minimum = MINIMUM_PATCH.get((major, minor))
    return minimum is not None and patch >= minimum


def main() -> None:
    """Reject CI interpreters without the required compromised-key protection."""
    if (
        platform.python_implementation() != "CPython"
        or sys.version_info.releaselevel != "final"
        or not python_meets_ci_security_baseline(sys.version_info[:3])
    ):
        raise SystemExit(
            "CI requires CPython 3.11.18+, 3.12.16+, 3.13.18+, or 3.14.10+. "
            "The package's Python 3.10 compatibility is unchanged."
        )
    print(f"CI security baseline verified: CPython {platform.python_version()}")


if __name__ == "__main__":
    main()
