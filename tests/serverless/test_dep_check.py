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

from pathlib import Path

import pytest

from ansys.dynamicreporting.core.exceptions import ImproperlyConfiguredError
import ansys.dynamicreporting.core.serverless._dep_check as dep_check_module
from ansys.dynamicreporting.core.serverless._dep_check import (
    InstalledDependencyVersion,
    audit_runtime_dependencies,
    enforce_runtime_dependencies,
)


def _installed_version(package_name: str, raw_version: str) -> InstalledDependencyVersion:
    """Build a test InstalledDependencyVersion using the real normalization helper."""
    return InstalledDependencyVersion(
        package_name=package_name,
        raw_version=raw_version,
        normalized_version=dep_check_module._normalize_version(raw_version),
    )


def test_v261_dependency_windows_stay_in_sync_with_constraints_file():
    constraints_path = Path(__file__).resolve().parents[2] / "constraints" / "v261.txt"
    expected_requirements = {
        line.strip()
        for line in constraints_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert expected_requirements == {
        window.requirement_text for window in dep_check_module._V261_DEPENDENCY_WINDOWS.values()
    }


def test_audit_runtime_dependencies_skips_non_enforced_install_versions(monkeypatch):
    monkeypatch.setattr(dep_check_module, "_get_installed_versions", lambda: {})

    audit_result = audit_runtime_dependencies(271)

    assert not audit_result.enforced
    assert audit_result.issues == ()


def test_audit_runtime_dependencies_reports_missing_v261_packages(monkeypatch):
    monkeypatch.setattr(dep_check_module, "_get_installed_versions", lambda: {})

    audit_result = audit_runtime_dependencies(261)

    assert audit_result.enforced
    assert {issue.package_name for issue in audit_result.issues} == set(
        dep_check_module.MONITORED_DEPENDENCIES
    )


def test_audit_runtime_dependencies_accepts_matching_v261_versions(monkeypatch):
    monkeypatch.setattr(
        dep_check_module,
        "_get_installed_versions",
        lambda: {
            "django": _installed_version("django", "4.2.27"),
            "django-guardian": _installed_version("django-guardian", "2.4.0"),
            "djangorestframework": _installed_version("djangorestframework", "3.15.9"),
        },
    )

    audit_result = audit_runtime_dependencies(261)

    assert audit_result.enforced
    assert audit_result.issues == ()


def test_audit_runtime_dependencies_reports_out_of_range_v261_versions(monkeypatch):
    monkeypatch.setattr(
        dep_check_module,
        "_get_installed_versions",
        lambda: {
            "django": _installed_version("django", "5.2.11"),
            "django-guardian": _installed_version("django-guardian", "3.2.0"),
            "djangorestframework": _installed_version("djangorestframework", "3.16.0"),
        },
    )

    audit_result = audit_runtime_dependencies(261)

    assert audit_result.enforced
    assert {issue.package_name for issue in audit_result.issues} == set(
        dep_check_module.MONITORED_DEPENDENCIES
    )


def test_enforce_runtime_dependencies_raises_for_v261_mismatch(monkeypatch):
    monkeypatch.setattr(
        dep_check_module,
        "_get_installed_versions",
        lambda: {
            "django": _installed_version("django", "5.2.11"),
            "django-guardian": _installed_version("django-guardian", "2.4.0"),
            "djangorestframework": _installed_version("djangorestframework", "3.15.2"),
        },
    )

    with pytest.raises(ImproperlyConfiguredError, match="ADR 2026 R1"):
        enforce_runtime_dependencies(261)


def test_enforce_runtime_dependencies_is_noop_for_current_line(monkeypatch):
    monkeypatch.setattr(dep_check_module, "_get_installed_versions", lambda: {})

    enforce_runtime_dependencies(271)
