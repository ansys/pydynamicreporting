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

"""Runtime dependency checks for serverless ADR setup.

This module intentionally keeps the backwards-compatibility enforcement logic
out of ``adr.py`` so the setup flow stays easy to read and the policy is easy
to remove or replace later.

The current enforcement is deliberately narrow:

- only the older ``261`` product line is checked strictly
- only the known upgraded libraries are monitored
- newer/current lines continue without an exact-version audit in this module

That policy matches the branch goal of preserving compatibility with older
serverless installs without turning setup into a broad environment linter.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
from typing import Final

from ..exceptions import ImproperlyConfiguredError

VersionKey = tuple[int, ...]


@dataclass(frozen=True)
class DependencyWindow:
    """Exact version window expected for one monitored dependency."""

    package_name: str
    minimum_version: VersionKey
    maximum_version: VersionKey
    requirement_text: str


@dataclass(frozen=True)
class InstalledDependencyVersion:
    """Installed package version in raw and normalized forms."""

    package_name: str
    raw_version: str
    normalized_version: VersionKey


@dataclass(frozen=True)
class DependencyIssue:
    """One missing or out-of-range dependency found during the audit."""

    package_name: str
    requirement_text: str
    installed_version: str | None


@dataclass(frozen=True)
class DependencyAuditResult:
    """Outcome of the runtime dependency audit for one target install line."""

    target_install_version: int
    enforced: bool
    issues: tuple[DependencyIssue, ...]


# Keep the monitored list small and explicit. These are the libraries whose
# version changes were introduced deliberately and whose drift matters for the
# older 261 serverless compatibility target.
MONITORED_DEPENDENCIES: Final[tuple[str, ...]] = (
    "django",
    "django-guardian",
    "djangorestframework",
)


# The runtime checker must work from an installed wheel, so it cannot rely on a
# repo-local constraints file being present on disk. This embedded profile
# mirrors ``constraints/v261.txt`` for the small set of runtime-enforced
# libraries only.
_V261_DEPENDENCY_WINDOWS: Final[dict[str, DependencyWindow]] = {
    "django": DependencyWindow(
        package_name="django",
        minimum_version=(4, 2, 27),
        maximum_version=(5, 0),
        requirement_text="django>=4.2.27,<5.0",
    ),
    "django-guardian": DependencyWindow(
        package_name="django-guardian",
        minimum_version=(2, 4, 0),
        maximum_version=(3, 0, 0),
        requirement_text="django-guardian>=2.4.0,<3.0.0",
    ),
    "djangorestframework": DependencyWindow(
        package_name="djangorestframework",
        minimum_version=(3, 15, 2),
        maximum_version=(3, 16, 0),
        requirement_text="djangorestframework>=3.15.2,<3.16.0",
    ),
}

_ENFORCED_WINDOWS_BY_INSTALL_VERSION: Final[dict[int, dict[str, DependencyWindow]]] = {
    261: _V261_DEPENDENCY_WINDOWS
}


def _normalize_version(version_string: str) -> VersionKey:
    """Convert a package version string into a comparable numeric tuple.

    The check only needs the leading numeric release components. Suffixes such
    as ``rc1`` or ``post1`` should not change whether a version falls inside the
    declared compatibility window.
    """
    components: list[int] = []
    for part in version_string.split("."):
        digits = []
        for char in part:
            if not char.isdigit():
                break
            digits.append(char)
        if not digits:
            break
        components.append(int("".join(digits)))
    return tuple(components)


def _get_installed_versions() -> dict[str, InstalledDependencyVersion]:
    """Return installed versions for the monitored runtime dependencies.

    The helper does a single linear pass over the monitored package list and
    records only the packages that are actually installed in the active
    environment.
    """
    installed_versions: dict[str, InstalledDependencyVersion] = {}
    for package_name in MONITORED_DEPENDENCIES:
        try:
            raw_version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            continue

        installed_versions[package_name] = InstalledDependencyVersion(
            package_name=package_name,
            raw_version=raw_version,
            normalized_version=_normalize_version(raw_version),
        )
    return installed_versions


def _version_in_window(
    installed_version: InstalledDependencyVersion, expected_window: DependencyWindow
) -> bool:
    """Return ``True`` when the installed version fits the exact compatibility window."""
    normalized = installed_version.normalized_version
    return expected_window.minimum_version <= normalized < expected_window.maximum_version


def audit_runtime_dependencies(target_install_version: int) -> DependencyAuditResult:
    """Audit runtime dependencies for one ADR install line.

    Only install lines with an explicit profile are enforced. The current ADR
    line ``271`` intentionally bypasses exact runtime enforcement here because
    this check exists to protect backwards compatibility for ``261``.
    """
    expected_windows = _ENFORCED_WINDOWS_BY_INSTALL_VERSION.get(target_install_version)
    if expected_windows is None:
        return DependencyAuditResult(
            target_install_version=target_install_version,
            enforced=False,
            issues=(),
        )

    installed_versions = _get_installed_versions()
    issues: list[DependencyIssue] = []

    # Iterate once over the expected profile so the audit cost stays linear in
    # the monitored package count and the output order remains deterministic.
    for package_name, expected_window in expected_windows.items():
        installed_version = installed_versions.get(package_name)
        if installed_version is None:
            issues.append(
                DependencyIssue(
                    package_name=package_name,
                    requirement_text=expected_window.requirement_text,
                    installed_version=None,
                )
            )
            continue

        if not _version_in_window(installed_version, expected_window):
            issues.append(
                DependencyIssue(
                    package_name=package_name,
                    requirement_text=expected_window.requirement_text,
                    installed_version=installed_version.raw_version,
                )
            )

    return DependencyAuditResult(
        target_install_version=target_install_version,
        enforced=True,
        issues=tuple(issues),
    )


def _format_dependency_issues(issues: tuple[DependencyIssue, ...]) -> str:
    """Build a stable, readable error summary for setup-time failures."""
    formatted_issues: list[str] = []
    for issue in issues:
        installed_text = issue.installed_version or "not installed"
        formatted_issues.append(
            f"{issue.package_name}: installed {installed_text}, expected {issue.requirement_text}"
        )
    return "; ".join(formatted_issues)


def enforce_runtime_dependencies(target_install_version: int) -> None:
    """Fail early when the active environment is incompatible with ADR ``261``.

    The message is intentionally specific so callers can see exactly which
    package drifted and which compatibility window must be restored for the
    older product line.
    """
    audit_result = audit_runtime_dependencies(target_install_version)
    if not audit_result.enforced or not audit_result.issues:
        return

    raise ImproperlyConfiguredError(
        "ADR 2026 R1 (install version 261) requires the exact backwards-compatible "
        "dependency window for serverless setup. "
        f"Detected dependency mismatches: {_format_dependency_issues(audit_result.issues)}. "
        "Use the 261 compatibility dependency set before targeting this install."
    )
