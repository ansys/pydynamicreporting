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

from collections.abc import Iterator
import io
import logging
from pathlib import Path

import pytest

import ansys.dynamicreporting.core.serverless.adr as serverless_adr_module
from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.adr_utils import get_logger
from ansys.dynamicreporting.core.common_utils import InstallResolution
from ansys.dynamicreporting.core.serverless import ADR

_PACKAGE_LOGGER_NAME = "ansys.dynamicreporting.core"


@pytest.fixture
def package_logger() -> Iterator[logging.Logger]:
    """Return the package logger with isolated handlers and level."""
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    for handler in previous_handlers:
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    try:
        yield logger
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        for handler in previous_handlers:
            logger.addHandler(handler)
        logger.setLevel(previous_level)


@pytest.mark.ado_test
def test_get_logger_returns_named_logger_without_touching_root(
    package_logger: logging.Logger,
) -> None:
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
def test_get_logger_emits_debug_once_caller_enables_logging(
    package_logger: logging.Logger,
) -> None:
    """A library ``DEBUG`` record must reach a caller-configured handler once the
    caller raises the package logger to ``DEBUG``.

    Regression guard: ``get_logger`` used to clamp the root logger to ``ERROR`` on
    every call, so every ``DEBUG``/``INFO``/``WARNING`` record the library emitted
    was dropped no matter how the caller configured logging.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    package_logger.addHandler(handler)
    package_logger.setLevel(logging.DEBUG)
    # Emit the way the library does -- fetch the logger via get_logger() and
    # log. The old bug re-clamped the (root) logger to ERROR on this call.
    get_logger().debug("adr-debug-regression-probe")

    assert "adr-debug-regression-probe" in stream.getvalue()


@pytest.mark.ado_test
def test_get_logger_preserves_caller_level_with_log_output(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """Adding an output handler must not replace the caller's logger level."""
    log_path = tmp_path / "adr.log"
    package_logger.setLevel(logging.WARNING)

    logger = get_logger(log_output=log_path)
    logger.debug("hidden-debug-message")
    logger.warning("visible-warning-message")

    assert logger.level == logging.WARNING
    contents = log_path.read_text()
    assert "hidden-debug-message" not in contents
    assert "visible-warning-message" in contents


@pytest.mark.ado_test
def test_get_logger_preserves_default_level_with_log_output(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """Adding an output handler must leave an untouched logger at ``NOTSET``."""
    logger = get_logger(log_output=tmp_path / "adr.log")

    assert logger is package_logger
    assert logger.level == logging.NOTSET


@pytest.mark.ado_test
def test_get_logger_preserves_inherited_application_level(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """The package logger must keep inheriting the caller's root level."""
    log_path = tmp_path / "adr.log"
    root = logging.getLogger()
    previous_root_level = root.level
    root.setLevel(logging.INFO)
    try:
        logger = get_logger(log_output=log_path)
        logger.debug("hidden-debug-message")
        logger.info("visible-info-message")
    finally:
        root.setLevel(previous_root_level)

    assert logger.level == logging.NOTSET
    contents = log_path.read_text()
    assert "hidden-debug-message" not in contents
    assert "visible-info-message" in contents


@pytest.mark.ado_test
def test_get_logger_applies_explicit_log_level(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """An explicit log level controls records written to the requested output."""
    log_path = tmp_path / "adr.log"
    package_logger.setLevel(logging.WARNING)

    logger = get_logger(log_output=log_path, log_level="INFO")
    logger.info("visible-info-message")

    assert logger.level == logging.INFO
    assert "visible-info-message" in log_path.read_text()


@pytest.mark.ado_test
def test_get_logger_adds_stdout_once(
    capsys: pytest.CaptureFixture[str],
    package_logger: logging.Logger,
) -> None:
    """Repeated stdout setup must not duplicate log lines."""
    get_logger(log_output="stdout", log_level=logging.INFO)
    logger = get_logger(log_output="stdout", log_level=logging.INFO)

    logger.info("stdout-message")

    assert capsys.readouterr().out.count("stdout-message") == 1


@pytest.mark.ado_test
def test_get_logger_adds_file_output_once(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """Repeated file setup must not duplicate handlers or log lines."""
    log_path = tmp_path / "adr.log"
    get_logger(log_output=log_path, log_level=logging.INFO)
    logger = get_logger(log_output=log_path, log_level=logging.INFO)

    logger.info("file-message")

    matching_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path.resolve()
    ]
    assert len(matching_handlers) == 1
    assert log_path.read_text().count("file-message") == 1


@pytest.mark.ado_test
def test_service_supports_deprecated_logfile(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """The legacy parameter works and warns at the public caller's location."""
    log_path = tmp_path / "legacy.log"

    with pytest.warns(DeprecationWarning, match="Use 'log_output' instead") as warning_info:
        service = Service(logfile=log_path, log_level=logging.ERROR)
    service.logger.error("legacy-error-message")

    assert warning_info[0].filename == __file__
    assert "legacy-error-message" in log_path.read_text()


@pytest.mark.ado_test
def test_get_logger_rejects_conflicting_output_parameters(tmp_path: Path) -> None:
    """The legacy and replacement output parameters are mutually exclusive."""
    with pytest.raises(ValueError, match="Use only one"):
        get_logger(logfile=tmp_path / "old.log", log_output=tmp_path / "new.log")


@pytest.mark.ado_test
def test_service_accepts_log_output_and_log_level(
    tmp_path: Path,
    package_logger: logging.Logger,
) -> None:
    """The public Service constructor must expose the replacement parameters."""
    log_path = tmp_path / "service.log"

    service = Service(log_output=log_path, log_level=logging.ERROR)
    service.logger.error("service-error-message")

    assert service.logger is package_logger
    assert service.logger.level == logging.ERROR
    assert "service-error-message" in log_path.read_text()


@pytest.mark.ado_test
def test_serverless_adr_accepts_log_output_and_log_level(
    tmp_path: Path,
    package_logger: logging.Logger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The serverless ADR constructor must expose the replacement parameters."""
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    log_path = tmp_path / "serverless.log"
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(
        serverless_adr_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=271,
        ),
    )

    adr = None
    try:
        adr = ADR(
            ansys_installation=str(install_dir),
            in_memory=True,
            log_output=log_path,
            log_level=logging.ERROR,
        )
        adr._logger.error("serverless-error-message")

        assert adr._logger is package_logger
        assert adr._logger.level == logging.ERROR
        assert "serverless-error-message" in log_path.read_text()
    finally:
        if adr is not None:
            # This constructor-only test stops before Django setup, so clean
            # its temporary directories without touching database connections.
            for temporary_directory in adr._tmp_dirs:
                temporary_directory.cleanup()
        ADR._instance = None
        ADR._is_setup = False
