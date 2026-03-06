"""Settings compatibility shim.

Translates product settings to be compatible with the dependency versions
installed in the client's venv. This handles known deprecations, renames,
and removals across product releases.
"""

from __future__ import annotations

import importlib.metadata
import logging
import warnings

from packaging.version import Version

logger = logging.getLogger(__name__)


# Registry of settings transformations.
# Each entry is:
#   (setting_to_check, condition_func, transform_func, description)
#
# condition_func(overrides, pkg_versions) -> bool
#   Returns True if the transformation should be applied.
# transform_func(overrides) -> overrides
#   Mutates and returns the overrides dict.

def _guardian_monkey_patch_rename(overrides: dict) -> dict:
    """Translate GUARDIAN_MONKEY_PATCH → GUARDIAN_MONKEY_PATCH_USER.

    django-guardian >= 2.4.0 deprecated GUARDIAN_MONKEY_PATCH in favor of
    GUARDIAN_MONKEY_PATCH_USER. Versions >= 3.0 may raise at import time
    if the old setting is present.
    """
    old_key = "GUARDIAN_MONKEY_PATCH"
    new_key = "GUARDIAN_MONKEY_PATCH_USER"

    if old_key in overrides:
        if new_key not in overrides:
            overrides[new_key] = overrides[old_key]
            logger.info(
                f"Compat shim: Translated '{old_key}' → '{new_key}' "
                f"(value={overrides[old_key]})"
            )
        del overrides[old_key]
    return overrides


def _guardian_needs_rename(overrides: dict, pkg_versions: dict) -> bool:
    """Check if guardian rename is needed."""
    guardian_ver = pkg_versions.get("django-guardian")
    if guardian_ver is None:
        return False
    return (
        "GUARDIAN_MONKEY_PATCH" in overrides
        and guardian_ver >= Version("2.4.0")
    )


def _remove_deprecated_default_file_storage(overrides: dict) -> dict:
    """Django 4.2+ deprecated DEFAULT_FILE_STORAGE in favor of STORAGES.

    If the installed Django is >= 5.1 and the product still uses the old
    setting, translate it.
    """
    old_key = "DEFAULT_FILE_STORAGE"
    if old_key in overrides:
        backend = overrides.pop(old_key)
        storages = overrides.get("STORAGES", {})
        if "default" not in storages:
            storages["default"] = {"BACKEND": backend}
            overrides["STORAGES"] = storages
            logger.info(
                f"Compat shim: Translated '{old_key}' → STORAGES['default'] "
                f"(backend={backend})"
            )
    return overrides


def _needs_storage_migration(overrides: dict, pkg_versions: dict) -> bool:
    """Check if DEFAULT_FILE_STORAGE → STORAGES migration is needed."""
    django_ver = pkg_versions.get("django")
    if django_ver is None:
        return False
    return (
        "DEFAULT_FILE_STORAGE" in overrides
        and django_ver >= Version("5.1")
    )


# The ordered registry of all known transformations.
COMPAT_REGISTRY: list[tuple] = [
    (
        "GUARDIAN_MONKEY_PATCH rename",
        _guardian_needs_rename,
        _guardian_monkey_patch_rename,
    ),
    (
        "DEFAULT_FILE_STORAGE → STORAGES migration",
        _needs_storage_migration,
        _remove_deprecated_default_file_storage,
    ),
    # Future entries go here:
    # ("description", condition_func, transform_func),
]


def _get_installed_versions() -> dict[str, Version]:
    """Collect versions of critical packages."""
    packages = ["django", "django-guardian", "djangorestframework"]
    versions = {}
    for pkg in packages:
        try:
            versions[pkg] = Version(importlib.metadata.version(pkg))
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def sanitize_settings(overrides: dict) -> dict:
    """Apply all applicable compatibility transformations to settings.

    Parameters
    ----------
    overrides : dict
        The settings dict built from the product's settings_serverless module.

    Returns
    -------
    dict
        The (potentially modified) settings dict, safe to pass to
        ``django.conf.settings.configure()``.
    """
    pkg_versions = _get_installed_versions()

    applied = []
    for description, condition_fn, transform_fn in COMPAT_REGISTRY:
        if condition_fn(overrides, pkg_versions):
            overrides = transform_fn(overrides)
            applied.append(description)

    if applied:
        logger.info(f"Compat shim applied {len(applied)} transformation(s): {applied}")

    return overrides
