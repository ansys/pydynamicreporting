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

"""Public client-to-product compatibility metadata."""

from dataclasses import dataclass
import re

from ._version import __version__

_PRODUCT_RELEASE_PATTERN = re.compile(r"^(?P<year_line>\d{2})\.(?P<release_index>\d+)$")
_CLIENT_MAJOR_BASE_PRODUCT_LINE = 27
_CLIENT_MAJOR_BASE_BUNDLED_RELEASE = "27.1"

SUPPORTED_PRODUCT_RELEASE_POLICY = (
    "Supports the bundled annual product line and the previous annual product line."
)
# Keep the legacy install-facing defaults separate from the public
# compatibility contract. Default install lookup must stay on the latest
# released ADR line so users who do not override ``ansys_version`` resolve a
# real installation by default. Unreleased lines can still be
# probed explicitly or as lower-priority fallbacks.
DEFAULT_ANSYS_INSTALL_RELEASE = "27.1"
DEFAULT_ANSYS_INSTALL_VERSION = "271"
# Preserve the historical no-argument constructor behavior by probing the
# bundled product line first.  This keeps existing ``Service()`` / ``ADR()``
# callers on the same default install they used on ``main`` while still
# allowing a released install as a lower-priority fallback.
#
# We intentionally do not probe older releases implicitly anymore.  Selecting an
# older unsupported line without an explicit user request changes the meaning
# of the default constructors too aggressively for a compatibility fix.
AUTO_DETECT_INSTALL_VERSIONS = ("271", "261")


@dataclass(frozen=True)
class ProductCompatibility:
    """Structured package compatibility metadata."""

    client_version: str
    client_major_epoch: int
    bundled_product_release: str
    supported_product_lines: tuple[str, ...]
    support_policy: str


def get_client_major_epoch(client_version: str = __version__) -> int:
    """Extract the SemVer major component from a client version string."""
    # ``__version__`` may include dev/build suffixes, so only the leading
    # numeric token is relevant for the compatibility epoch.
    major_token = client_version.split(".", maxsplit=1)[0]
    numeric = re.match(r"^\d+", major_token)
    return int(numeric.group(0)) if numeric else 0


def product_line_for_client_major(client_major: int) -> str:
    """Return the current annual product line for a client major epoch."""
    if client_major < 0:
        raise ValueError("Client major epoch must be 0 or greater.")
    return str(_CLIENT_MAJOR_BASE_PRODUCT_LINE + client_major)


def bundled_product_release_for_client_major(client_major: int) -> str:
    """Return the bundled product release for a client major epoch."""
    return f"{product_line_for_client_major(client_major)}.1"


def supported_product_lines_for_client_major(client_major: int) -> tuple[str, str]:
    """Return the previous/current annual product lines for a client major epoch."""
    bundled_line = int(product_line_for_client_major(client_major))
    return (str(bundled_line - 1), str(bundled_line))


_CURRENT_CLIENT_MAJOR_EPOCH = get_client_major_epoch()
# Public compatibility metadata follows the installed client major line.
# Major ``0`` is permanently anchored to the shipped 2026 product epoch.
BUNDLED_PRODUCT_RELEASE = bundled_product_release_for_client_major(_CURRENT_CLIENT_MAJOR_EPOCH)
SUPPORTED_PRODUCT_LINES = supported_product_lines_for_client_major(_CURRENT_CLIENT_MAJOR_EPOCH)


def parse_product_release(product_release: str) -> tuple[str, int]:
    """Parse a product release string like ``27.1`` into components."""
    match = _PRODUCT_RELEASE_PATTERN.fullmatch(product_release)
    if match is None:
        raise ValueError(
            "Product release must use the 'YY.R' format, for example '27.1' or '27.2'."
        )

    year_line = match.group("year_line")
    release_index = int(match.group("release_index"))
    if release_index < 1:
        raise ValueError("Product release index must be 1 or greater.")
    return year_line, release_index


def product_release_to_install_version(product_release: str) -> int:
    """Convert a public product release like ``27.1`` to the install version ``271``."""
    year_line, release_index = parse_product_release(product_release)
    return int(f"{year_line}{release_index}")


# HTML/static export helpers historically fell back to the bundled product
# namespace when they could not discover a server-specific version.  Keep that
# behavior separate from install probing so direct ``ReportDownloadHTML`` usage
# stays backwards compatible without forcing constructor defaults back to 271.
DEFAULT_STATIC_ASSET_VERSION = str(product_release_to_install_version(BUNDLED_PRODUCT_RELEASE))


def install_version_to_product_release(install_version: int | str) -> str:
    """Convert an internal install version like ``271`` to ``27.1``."""
    normalized = str(install_version).strip()
    if not normalized.isdigit() or len(normalized) < 3:
        raise ValueError(
            "Install version must be a digit-only string or int with at least three digits."
        )

    year_line = normalized[:-1]
    release_index = int(normalized[-1])
    return f"{year_line}.{release_index}"


def product_release_to_display_string(product_release: str) -> str:
    """Convert ``27.1`` to ``2027 R1``."""
    year_line, release_index = parse_product_release(product_release)
    return f"20{year_line} R{release_index}"


def product_release_to_short_label(product_release: str) -> str:
    """Convert ``27.1`` to ``2027R1``."""
    year_line, release_index = parse_product_release(product_release)
    return f"20{year_line}R{release_index}"


def product_release_to_product_line(product_release: str) -> str:
    """Return the annual product line, for example ``27`` for ``27.2``."""
    year_line, _ = parse_product_release(product_release)
    return year_line


def is_supported_product_release(
    product_release: str, supported_product_lines: tuple[str, ...] = SUPPORTED_PRODUCT_LINES
) -> bool:
    """Return ``True`` if the release belongs to one of the supported annual lines."""
    return product_release_to_product_line(product_release) in supported_product_lines


def get_compatibility_info(client_version: str = __version__) -> ProductCompatibility:
    """Return the public compatibility contract for the installed client."""
    # Keep all public compatibility facts assembled in one place so docs,
    # warnings, and future automation do not drift apart.
    client_major_epoch = get_client_major_epoch(client_version)
    return ProductCompatibility(
        client_version=client_version,
        client_major_epoch=client_major_epoch,
        bundled_product_release=bundled_product_release_for_client_major(client_major_epoch),
        supported_product_lines=supported_product_lines_for_client_major(client_major_epoch),
        support_policy=SUPPORTED_PRODUCT_RELEASE_POLICY,
    )


def get_compatibility_warning_for_install_version(
    install_version: int | str | None,
    supported_product_lines: tuple[str, ...] = SUPPORTED_PRODUCT_LINES,
) -> str | None:
    """Return a warning message when an install version falls outside the supported window."""
    if install_version is None:
        return None

    try:
        detected_release = install_version_to_product_release(install_version)
    except ValueError:
        # Preserve the historical behavior for unparsable versions by skipping
        # the compatibility check instead of raising at import/constructor time.
        return None

    if is_supported_product_release(detected_release, supported_product_lines):
        return None

    supported_lines = ", ".join(f"{line}.*" for line in supported_product_lines)
    return (
        "Detected ADR product release "
        f"{detected_release} is outside the supported window for this client. "
        f"This client is bundled with {BUNDLED_PRODUCT_RELEASE} and supports annual lines "
        f"{supported_lines}. Compatibility is not guaranteed."
    )
