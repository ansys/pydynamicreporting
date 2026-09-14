"""Exceptions for the ADR exchange layer."""


class ExchangeError(Exception):
    """Base class for ADR exchange errors."""


class ExchangeValidationError(ExchangeError, ValueError):
    """Raised when a payload violates the exchange schema."""


class ExchangeVersionError(ExchangeError, ValueError):
    """Raised when a payload major version is unsupported."""
