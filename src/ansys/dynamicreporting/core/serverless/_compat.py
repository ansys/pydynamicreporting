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

"""Settings compatibility shim.

Translate product settings so they remain compatible with the dependency
versions installed in the client's venv. This module only handles known
setting transitions between supported ADR product lines and current client
dependencies.
"""

from __future__ import annotations

import importlib.metadata
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

VersionKey = tuple[int, ...]
ConditionFn = Callable[[dict, dict[str, VersionKey]], bool]
TransformFn = Callable[[dict], dict]


# Registry of settings transformations.
# Each entry is:
#   (description, condition_func, transform_func)
#
# condition_func(overrides, pkg_versions) -> bool
#   Returns True if the transformation should be applied.
# transform_func(overrides) -> overrides
#   Mutates and returns the overrides dict.


def _normalize_version(version_string: str) -> VersionKey:
    """Convert a package version string into a comparable numeric tuple.

    Only the leading numeric components are relevant for the floor checks in
    this shim. Suffixes such as ``rc1`` or ``post1`` are ignored because the
    current transformations only need stable minimum-version comparisons.
    """
    components: list[int] = []
    for part in version_string.split("."):
        match = re.match(r"^(\d+)", part)
        if match is None:
            break
        components.append(int(match.group(1)))

    return tuple(components)


def _guardian_monkey_patch_rename(overrides: dict) -> dict:
    """Translate ``GUARDIAN_MONKEY_PATCH`` to ``GUARDIAN_MONKEY_PATCH_USER``.

    django-guardian >= 2.4.0 deprecated ``GUARDIAN_MONKEY_PATCH`` in favor of
    ``GUARDIAN_MONKEY_PATCH_USER``. Versions >= 3.0 may raise at import time
    if the old setting is still present.
    """
    old_key = "GUARDIAN_MONKEY_PATCH"
    new_key = "GUARDIAN_MONKEY_PATCH_USER"

    if old_key in overrides:
        if new_key not in overrides:
            overrides[new_key] = overrides[old_key]
            logger.info(
                f"Compat shim: Translated '{old_key}' -> '{new_key}' (value={overrides[old_key]})"
            )
        del overrides[old_key]
    return overrides


def _guardian_needs_rename(overrides: dict, pkg_versions: dict[str, VersionKey]) -> bool:
    """Check if the guardian setting rename is required."""
    guardian_ver = pkg_versions.get("django-guardian")
    if guardian_ver is None:
        return False
    return "GUARDIAN_MONKEY_PATCH" in overrides and guardian_ver >= (2, 4, 0)


def _remove_deprecated_default_file_storage(overrides: dict) -> dict:
    """Translate ``DEFAULT_FILE_STORAGE`` into ``STORAGES['default']``.

    Django 4.2 introduced ``STORAGES`` and later releases expect callers to
    define the default backend there instead of through
    ``DEFAULT_FILE_STORAGE``.
    """
    old_key = "DEFAULT_FILE_STORAGE"
    if old_key in overrides:
        backend = overrides.pop(old_key)
        storages = overrides.get("STORAGES", {})
        if "default" not in storages:
            storages["default"] = {"BACKEND": backend}
            overrides["STORAGES"] = storages
            logger.info(
                f"Compat shim: Translated '{old_key}' -> STORAGES['default'] (backend={backend})"
            )
    return overrides


def _needs_storage_migration(overrides: dict, pkg_versions: dict[str, VersionKey]) -> bool:
    """Check if the storage-setting migration is required."""
    django_ver = pkg_versions.get("django")
    if django_ver is None:
        return False
    return "DEFAULT_FILE_STORAGE" in overrides and django_ver >= (5, 1)


COMPAT_REGISTRY: list[tuple[str, ConditionFn, TransformFn]] = [
    (
        "GUARDIAN_MONKEY_PATCH rename",
        _guardian_needs_rename,
        _guardian_monkey_patch_rename,
    ),
    (
        "DEFAULT_FILE_STORAGE -> STORAGES migration",
        _needs_storage_migration,
        _remove_deprecated_default_file_storage,
    ),
]


def _get_installed_versions() -> dict[str, VersionKey]:
    """Collect installed versions for the packages used by the shim rules."""
    packages = ["django", "django-guardian", "djangorestframework"]
    versions: dict[str, VersionKey] = {}
    for pkg in packages:
        try:
            versions[pkg] = _normalize_version(importlib.metadata.version(pkg))
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def sanitize_settings(overrides: dict) -> dict:
    """Apply all applicable compatibility transformations to settings.

    Parameters
    ----------
    overrides : dict
        The settings dict built from the product's ``settings_serverless``
        module.

    Returns
    -------
    dict
        The potentially modified settings dict, safe to pass to
        ``django.conf.settings.configure()``.
    """
    pkg_versions = _get_installed_versions()

    applied: list[str] = []
    for description, condition_fn, transform_fn in COMPAT_REGISTRY:
        if condition_fn(overrides, pkg_versions):
            overrides = transform_fn(overrides)
            applied.append(description)

    if applied:
        logger.info(f"Compat shim applied {len(applied)} transformation(s): {applied}")

    return overrides
