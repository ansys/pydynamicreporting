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

"""Tests for the CI-only Python security baseline."""

import pytest

from scripts.check_ci_python import python_meets_ci_security_baseline


@pytest.mark.parametrize(
    "version", [(3, 11, 18), (3, 12, 16), (3, 13, 18), (3, 14, 10), (3, 14, 11)]
)
def test_ci_python_accepts_security_releases(version):
    assert python_meets_ci_security_baseline(version)


@pytest.mark.parametrize(
    "version", [(3, 10, 19), (3, 11, 17), (3, 12, 15), (3, 13, 17), (3, 14, 9), (3, 15, 2)]
)
def test_ci_python_rejects_unpatched_or_unconfigured_branches(version):
    assert not python_meets_ci_security_baseline(version)
