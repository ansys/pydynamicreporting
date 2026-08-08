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

"""Serverless compatibility hook system.

This module centralizes all compatibility rewrites that adapt product-shipped
serverless settings to the dependency versions installed in the client's
environment.

The hook system is intentionally phased so ADR setup can stay thin:

- pre-configure rules rewrite the product settings dictionary
- post-configure hooks can adjust configured Django settings
- pre-setup hooks can run just before ``django.setup()``

Only the first phase has active rules today. The later phases exist so future
compatibility fixes can be added without growing ad-hoc logic in ``adr.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import logging
import re
from typing import Any, Callable, Collection

logger = logging.getLogger(__name__)

VersionKey = tuple[int, ...]
OverridesDict = dict[str, Any]
ConditionFn = Callable[[OverridesDict, dict[str, VersionKey]], bool]
TransformFn = Callable[[OverridesDict], OverridesDict]
PostConfigureHookFn = Callable[[Any], None]
PreSetupHookFn = Callable[[], None]


@dataclass(frozen=True)
class PreConfigureRule:
    """One compatibility rule that rewrites settings before configuration."""

    description: str
    condition: ConditionFn
    transform: TransformFn


@dataclass(frozen=True)
class PostConfigureHook:
    """One deferred compatibility hook that runs after settings.configure()."""

    description: str
    apply: PostConfigureHookFn


@dataclass(frozen=True)
class PostConfigureRule:
    """One rule that schedules a post-configure hook when its condition matches."""

    description: str
    condition: ConditionFn
    build_hook: Callable[[OverridesDict, dict[str, VersionKey]], PostConfigureHook]


@dataclass(frozen=True)
class PreSetupHook:
    """One deferred compatibility hook that runs just before django.setup()."""

    description: str
    apply: PreSetupHookFn


@dataclass(frozen=True)
class PreSetupRule:
    """One rule that schedules a pre-setup hook when its condition matches."""

    description: str
    condition: ConditionFn
    build_hook: Callable[[OverridesDict, dict[str, VersionKey]], PreSetupHook]


@dataclass(frozen=True)
class CompatibilityPlan:
    """Compatibility rewrites and deferred hooks for one ADR setup call."""

    overrides: OverridesDict
    post_configure_hooks: tuple[PostConfigureHook, ...]
    pre_setup_hooks: tuple[PreSetupHook, ...]
    applied_pre_configure_rules: tuple[str, ...]
    scheduled_post_configure_hooks: tuple[str, ...]
    scheduled_pre_setup_hooks: tuple[str, ...]


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


def _guardian_monkey_patch_rename(overrides: OverridesDict) -> OverridesDict:
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
            logger.info(f"Compat shim: Translated '{old_key}' -> '{new_key}'")
        del overrides[old_key]
    return overrides


def _guardian_needs_rename(overrides: OverridesDict, pkg_versions: dict[str, VersionKey]) -> bool:
    """Check if the guardian setting rename is required."""
    guardian_ver = pkg_versions.get("django-guardian")
    if guardian_ver is None:
        return False
    return "GUARDIAN_MONKEY_PATCH" in overrides and guardian_ver >= (2, 4, 0)


def _remove_deprecated_default_file_storage(overrides: OverridesDict) -> OverridesDict:
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


def _needs_storage_migration(
    overrides: OverridesDict, pkg_versions: dict[str, VersionKey]
) -> bool:
    """Check if the storage-setting migration is required."""
    django_ver = pkg_versions.get("django")
    if django_ver is None:
        return False
    return "DEFAULT_FILE_STORAGE" in overrides and django_ver >= (5, 1)


def _filter_installed_apps(overrides: OverridesDict, blocked_apps: Collection[str]) -> OverridesDict:
    """Remove selected app labels from ``INSTALLED_APPS`` while preserving order.

    The helper uses a set for membership checks so filtering remains linear in
    the number of configured apps instead of degenerating into repeated scans.
    It also preserves the original container type to avoid surprising callers
    that expect a list versus tuple.
    """
    installed_apps = overrides.get("INSTALLED_APPS")
    if not isinstance(installed_apps, (list, tuple)):
        return overrides

    blocked_app_set = set(blocked_apps)
    filtered_apps = [app for app in installed_apps if app not in blocked_app_set]
    if len(filtered_apps) == len(installed_apps):
        return overrides

    if isinstance(installed_apps, tuple):
        overrides["INSTALLED_APPS"] = tuple(filtered_apps)
    else:
        overrides["INSTALLED_APPS"] = filtered_apps

    logger.info("Compat hook: filtered INSTALLED_APPS entries %s", sorted(blocked_app_set))
    return overrides


PRE_CONFIGURE_RULES: list[PreConfigureRule] = [
    PreConfigureRule(
        description="GUARDIAN_MONKEY_PATCH rename",
        condition=_guardian_needs_rename,
        transform=_guardian_monkey_patch_rename,
    ),
    PreConfigureRule(
        description="DEFAULT_FILE_STORAGE -> STORAGES migration",
        condition=_needs_storage_migration,
        transform=_remove_deprecated_default_file_storage,
    ),
]

# These registries are intentionally empty today. The phased planner exists so
# future compatibility fixes can add targeted hooks without growing `adr.py`.
POST_CONFIGURE_RULES: list[PostConfigureRule] = []
PRE_SETUP_RULES: list[PreSetupRule] = []


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


def build_compatibility_plan(overrides: OverridesDict) -> CompatibilityPlan:
    """Build the full compatibility plan for one ADR setup call.

    The planner runs every pre-configure transform immediately because those
    settings rewrites must happen before ``settings.configure(**overrides)``.
    Later-phase hooks are collected into the returned plan so the caller can
    run them at the right point in the Django setup lifecycle.
    """
    pkg_versions = _get_installed_versions()

    applied_pre_configure_rules: list[str] = []
    scheduled_post_configure_hooks: list[str] = []
    scheduled_pre_setup_hooks: list[str] = []
    post_configure_hooks: list[PostConfigureHook] = []
    pre_setup_hooks: list[PreSetupHook] = []

    for rule in PRE_CONFIGURE_RULES:
        if rule.condition(overrides, pkg_versions):
            overrides = rule.transform(overrides)
            applied_pre_configure_rules.append(rule.description)

    for rule in POST_CONFIGURE_RULES:
        if rule.condition(overrides, pkg_versions):
            post_configure_hooks.append(rule.build_hook(overrides, pkg_versions))
            scheduled_post_configure_hooks.append(rule.description)

    for rule in PRE_SETUP_RULES:
        if rule.condition(overrides, pkg_versions):
            pre_setup_hooks.append(rule.build_hook(overrides, pkg_versions))
            scheduled_pre_setup_hooks.append(rule.description)

    if applied_pre_configure_rules:
        logger.info(
            "Compat plan applied %d pre-configure rule(s): %s",
            len(applied_pre_configure_rules),
            applied_pre_configure_rules,
        )
    if scheduled_post_configure_hooks:
        logger.info(
            "Compat plan scheduled %d post-configure hook(s): %s",
            len(scheduled_post_configure_hooks),
            scheduled_post_configure_hooks,
        )
    if scheduled_pre_setup_hooks:
        logger.info(
            "Compat plan scheduled %d pre-setup hook(s): %s",
            len(scheduled_pre_setup_hooks),
            scheduled_pre_setup_hooks,
        )

    return CompatibilityPlan(
        overrides=overrides,
        post_configure_hooks=tuple(post_configure_hooks),
        pre_setup_hooks=tuple(pre_setup_hooks),
        applied_pre_configure_rules=tuple(applied_pre_configure_rules),
        scheduled_post_configure_hooks=tuple(scheduled_post_configure_hooks),
        scheduled_pre_setup_hooks=tuple(scheduled_pre_setup_hooks),
    )


def run_post_configure_hooks(plan: CompatibilityPlan, settings_obj: Any) -> None:
    """Run any post-configure compatibility hooks in registration order."""
    for hook in plan.post_configure_hooks:
        hook.apply(settings_obj)


def run_pre_setup_hooks(plan: CompatibilityPlan) -> None:
    """Run any pre-setup compatibility hooks in registration order."""
    for hook in plan.pre_setup_hooks:
        hook.apply()


def sanitize_settings(overrides: OverridesDict) -> OverridesDict:
    """Apply pre-configure compatibility transformations to settings.

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

    Notes
    -----
    This wrapper is kept for backwards compatibility with the earlier shim
    implementation. New setup code should prefer :func:`build_compatibility_plan`
    so later-phase hooks remain available.
    """
    return build_compatibility_plan(overrides).overrides
