"""Version helpers for the ADR exchange schema."""

from __future__ import annotations

from .errors import ExchangeVersionError

SCHEMA_VERSION = "1.0"
SUPPORTED_MAJOR = 1


def parse_version(version: str) -> tuple[int, int]:
    """Parse a schema version like ``1.2`` into ``(major, minor)``."""
    if not isinstance(version, str):
        raise ExchangeVersionError(f"Invalid schema version: {version!r}")

    try:
        major_text, minor_text = version.split(".", 1)
        major = int(major_text)
        minor = int(minor_text)
    except (ValueError, TypeError) as exc:
        raise ExchangeVersionError(f"Invalid schema version: {version!r}") from exc

    return major, minor


def check_version(version: str | None, logger: object | None = None) -> None:
    """Guard the payload major version against the supported major."""
    payload_version = version or SCHEMA_VERSION
    major, _minor = parse_version(payload_version)
    if major > SUPPORTED_MAJOR:
        raise ExchangeVersionError(
            f"Unsupported schema major version {major}: supported major is {SUPPORTED_MAJOR}."
        )
    if logger is not None and hasattr(logger, "info"):
        logger.info("ADR exchange schema version %s accepted", payload_version)
