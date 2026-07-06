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

"""Unit tests for ``ansys.dynamicreporting.core.adr_utils`` logging helpers."""

import io
import logging

import pytest

from ansys.dynamicreporting.core.adr_utils import get_logger

_PACKAGE_LOGGER_NAME = "ansys.dynamicreporting.core"


@pytest.mark.ado_test
def test_get_logger_returns_named_logger_without_touching_root() -> None:
    """``get_logger`` must return the package's named logger and leave the root
    logger's level and handlers untouched.

    Regression guard: ``get_logger`` used to return the shared root logger and
    reconfigure it (forcing ``ERROR`` and stacking a handler on every call),
    which hijacked the host application's logging.
    """
    root = logging.getLogger()
    level_before = root.level
    handlers_before = list(root.handlers)

    logger = get_logger()

    assert logger is logging.getLogger(_PACKAGE_LOGGER_NAME)
    assert logger is not root
    assert root.level == level_before
    assert root.handlers == handlers_before


@pytest.mark.ado_test
def test_get_logger_emits_debug_once_caller_enables_logging() -> None:
    """A library ``DEBUG`` record must reach a caller-configured handler once the
    caller raises the package logger to ``DEBUG``.

    Regression guard: ``get_logger`` used to clamp the root logger to ``ERROR`` on
    every call, so every ``DEBUG``/``INFO``/``WARNING`` record the library emitted
    was dropped no matter how the caller configured logging.
    """
    package_logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    previous_level = package_logger.level

    package_logger.addHandler(handler)
    package_logger.setLevel(logging.DEBUG)
    try:
        # Emit the way the library does -- fetch the logger via get_logger() and
        # log. The old bug re-clamped the (root) logger to ERROR on this call.
        get_logger().debug("adr-debug-regression-probe")
    finally:
        package_logger.removeHandler(handler)
        package_logger.setLevel(previous_level)

    assert "adr-debug-regression-probe" in stream.getvalue()
