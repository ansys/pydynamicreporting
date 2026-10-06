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

"""Version helpers for the ADR import schema."""

from __future__ import annotations

import re

from .errors import ImportVersionError

SCHEMA_VERSION = "1.0"
"""Schema version emitted and fully understood by this importer."""

SUPPORTED_MAJOR = 1
"""Highest document major version this importer accepts."""

# The format is deliberately 'MAJOR.MINOR' and not semver: a third component
# would have no defined meaning for this contract, so it is rejected instead of
# being silently ignored.
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


def parse_version(version: str) -> tuple[int, int]:
    """Parse a ``"MAJOR.MINOR"`` schema version string.

    Parameters
    ----------
    version : str
        Version string, for example ``"1.3"``.

    Returns
    -------
    tuple of (int, int)
        The major and minor components.

    Raises
    ------
    ImportVersionError
        If ``version`` is not exactly two dot-separated integers.
    """
    if not isinstance(version, str):
        raise ImportVersionError(
            f"expected a 'MAJOR.MINOR' version string, got {type(version).__name__}"
        )
    match = _VERSION_RE.match(version.strip())
    if match is None:
        raise ImportVersionError(
            f"{version!r} is not a valid schema version; expected 'MAJOR.MINOR', for example '1.0'"
        )
    return int(match.group(1)), int(match.group(2))


def check_version(version: str | None, logger: object | None = None) -> str:
    """Validate a document schema version against this importer.

    Parameters
    ----------
    version : str or None
        Version declared by the document. ``None`` is treated as
        :data:`SCHEMA_VERSION` with a logged warning.
    logger : object, optional
        Logger used for the missing-version warning and the
        forward-compatibility note.

    Returns
    -------
    str
        The resolved version string.

    Raises
    ------
    ImportVersionError
        If the version is malformed or its major exceeds
        :data:`SUPPORTED_MAJOR`.
    """
    if version is None:
        if logger is not None:
            logger.warning(
                "No 'schema_version' in the import document; assuming %s.", SCHEMA_VERSION
            )
        return SCHEMA_VERSION

    major, minor = parse_version(version)
    if major > SUPPORTED_MAJOR:
        raise ImportVersionError(
            f"document major version {major} is newer than the supported major "
            f"{SUPPORTED_MAJOR}; upgrade ansys-dynamicreporting-core to import it"
        )

    supported_major, supported_minor = parse_version(SCHEMA_VERSION)
    if major == supported_major and minor > supported_minor and logger is not None:
        logger.info(
            "Import document declares schema version %s, newer than the supported %s; "
            "unrecognized fields are retained but not interpreted.",
            version,
            SCHEMA_VERSION,
        )
    return version
