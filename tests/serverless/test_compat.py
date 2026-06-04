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

import ansys.dynamicreporting.core.serverless._compat as compat_module


def test_sanitize_settings_renames_guardian_setting(monkeypatch):
    overrides = {"GUARDIAN_MONKEY_PATCH": False}
    monkeypatch.setattr(
        compat_module,
        "_get_installed_versions",
        lambda: {"django-guardian": (2, 4, 0)},
    )

    sanitized = compat_module.sanitize_settings(overrides)

    assert "GUARDIAN_MONKEY_PATCH" not in sanitized
    assert sanitized["GUARDIAN_MONKEY_PATCH_USER"] is False


def test_sanitize_settings_preserves_explicit_guardian_user_setting(monkeypatch):
    overrides = {
        "GUARDIAN_MONKEY_PATCH": False,
        "GUARDIAN_MONKEY_PATCH_USER": True,
    }
    monkeypatch.setattr(
        compat_module,
        "_get_installed_versions",
        lambda: {"django-guardian": (3, 0, 0)},
    )

    sanitized = compat_module.sanitize_settings(overrides)

    assert "GUARDIAN_MONKEY_PATCH" not in sanitized
    assert sanitized["GUARDIAN_MONKEY_PATCH_USER"] is True


def test_sanitize_settings_migrates_default_file_storage(monkeypatch):
    overrides = {"DEFAULT_FILE_STORAGE": "django.core.files.storage.FileSystemStorage"}
    monkeypatch.setattr(
        compat_module,
        "_get_installed_versions",
        lambda: {"django": (5, 1, 0)},
    )

    sanitized = compat_module.sanitize_settings(overrides)

    assert "DEFAULT_FILE_STORAGE" not in sanitized
    assert sanitized["STORAGES"]["default"]["BACKEND"] == (
        "django.core.files.storage.FileSystemStorage"
    )


def test_sanitize_settings_keeps_existing_default_storage_config(monkeypatch):
    overrides = {
        "DEFAULT_FILE_STORAGE": "django.core.files.storage.FileSystemStorage",
        "STORAGES": {"default": {"BACKEND": "custom.backend.Storage"}},
    }
    monkeypatch.setattr(
        compat_module,
        "_get_installed_versions",
        lambda: {"django": (5, 2, 0)},
    )

    sanitized = compat_module.sanitize_settings(overrides)

    assert "DEFAULT_FILE_STORAGE" not in sanitized
    assert sanitized["STORAGES"]["default"]["BACKEND"] == "custom.backend.Storage"


def test_sanitize_settings_is_noop_below_version_thresholds(monkeypatch):
    overrides = {
        "GUARDIAN_MONKEY_PATCH": False,
        "DEFAULT_FILE_STORAGE": "django.core.files.storage.FileSystemStorage",
    }
    monkeypatch.setattr(
        compat_module,
        "_get_installed_versions",
        lambda: {"django": (5, 0, 9), "django-guardian": (2, 3, 9)},
    )

    sanitized = compat_module.sanitize_settings(overrides)

    assert sanitized == {
        "GUARDIAN_MONKEY_PATCH": False,
        "DEFAULT_FILE_STORAGE": "django.core.files.storage.FileSystemStorage",
    }


def test_normalize_version_ignores_non_numeric_suffixes():
    assert compat_module._normalize_version("5.1.2.post1") == (5, 1, 2)
    assert compat_module._normalize_version("2.4.0rc1") == (2, 4, 0)


def test_guardian_rename_is_noop_when_old_key_absent():
    # Transform function called directly (without condition gate) to cover
    # the early-return branch when GUARDIAN_MONKEY_PATCH is not present.
    overrides = {"SOME_OTHER_KEY": True}
    result = compat_module._guardian_monkey_patch_rename(overrides)
    assert result == {"SOME_OTHER_KEY": True}


def test_storage_migration_is_noop_when_old_key_absent():
    # Same as above for DEFAULT_FILE_STORAGE.
    overrides = {"SOME_OTHER_KEY": True}
    result = compat_module._remove_deprecated_default_file_storage(overrides)
    assert result == {"SOME_OTHER_KEY": True}


def test_filter_installed_apps_preserves_order_and_container_type():
    overrides = {
        "INSTALLED_APPS": (
            "django.contrib.admin",
            "guardian",
            "rest_framework",
            "ceireports",
        )
    }

    filtered = compat_module._filter_installed_apps(overrides, {"guardian", "ceireports"})

    assert filtered["INSTALLED_APPS"] == ("django.contrib.admin", "rest_framework")
    assert isinstance(filtered["INSTALLED_APPS"], tuple)


def test_build_compatibility_plan_collects_hooks_by_phase(monkeypatch):
    observed_calls = []

    def always_enabled(overrides, pkg_versions):
        return True

    def apply_pre_configure(overrides):
        observed_calls.append("pre-configure")
        overrides["COMPAT_PREPARED"] = True
        return overrides

    def build_post_configure_hook(overrides, pkg_versions):
        return compat_module.PostConfigureHook(
            description="test post-configure hook",
            apply=lambda settings_obj: observed_calls.append(f"post-configure:{settings_obj.marker}"),
        )

    def build_pre_setup_hook(overrides, pkg_versions):
        return compat_module.PreSetupHook(
            description="test pre-setup hook",
            apply=lambda: observed_calls.append("pre-setup"),
        )

    class DummySettings:
        marker = "configured"

    monkeypatch.setattr(compat_module, "_get_installed_versions", lambda: {"django": (5, 2, 0)})
    monkeypatch.setattr(
        compat_module,
        "PRE_CONFIGURE_RULES",
        [
            compat_module.PreConfigureRule(
                description="test pre-configure rule",
                condition=always_enabled,
                transform=apply_pre_configure,
            )
        ],
    )
    monkeypatch.setattr(
        compat_module,
        "POST_CONFIGURE_RULES",
        [
            compat_module.PostConfigureRule(
                description="test post-configure rule",
                condition=always_enabled,
                build_hook=build_post_configure_hook,
            )
        ],
    )
    monkeypatch.setattr(
        compat_module,
        "PRE_SETUP_RULES",
        [
            compat_module.PreSetupRule(
                description="test pre-setup rule",
                condition=always_enabled,
                build_hook=build_pre_setup_hook,
            )
        ],
    )

    plan = compat_module.build_compatibility_plan({"INSTALLED_APPS": ["ceireports"]})

    assert plan.overrides["COMPAT_PREPARED"] is True
    assert plan.applied_pre_configure_rules == ("test pre-configure rule",)
    assert plan.scheduled_post_configure_hooks == ("test post-configure rule",)
    assert plan.scheduled_pre_setup_hooks == ("test pre-setup rule",)

    compat_module.run_post_configure_hooks(plan, DummySettings())
    compat_module.run_pre_setup_hooks(plan)

    assert observed_calls == [
        "pre-configure",
        "post-configure:configured",
        "pre-setup",
    ]


def test_sanitize_settings_keeps_deferred_hooks_deferred(monkeypatch):
    observed_calls = []

    def always_enabled(overrides, pkg_versions):
        return True

    def build_post_configure_hook(overrides, pkg_versions):
        return compat_module.PostConfigureHook(
            description="test post-configure hook",
            apply=lambda settings_obj: observed_calls.append("post-configure"),
        )

    def build_pre_setup_hook(overrides, pkg_versions):
        return compat_module.PreSetupHook(
            description="test pre-setup hook",
            apply=lambda: observed_calls.append("pre-setup"),
        )

    monkeypatch.setattr(compat_module, "_get_installed_versions", lambda: {"django": (5, 2, 0)})
    monkeypatch.setattr(compat_module, "PRE_CONFIGURE_RULES", [])
    monkeypatch.setattr(
        compat_module,
        "POST_CONFIGURE_RULES",
        [
            compat_module.PostConfigureRule(
                description="test post-configure rule",
                condition=always_enabled,
                build_hook=build_post_configure_hook,
            )
        ],
    )
    monkeypatch.setattr(
        compat_module,
        "PRE_SETUP_RULES",
        [
            compat_module.PreSetupRule(
                description="test pre-setup rule",
                condition=always_enabled,
                build_hook=build_pre_setup_hook,
            )
        ],
    )

    sanitized = compat_module.sanitize_settings({"DEBUG": False})

    assert sanitized == {"DEBUG": False}
    assert observed_calls == []


def test_get_installed_versions_returns_real_packages():
    # Integration test: call _get_installed_versions without mocking to
    # cover the real importlib.metadata path.  Django is a declared
    # dependency so it should always be present in the test environment.
    versions = compat_module._get_installed_versions()
    assert "django" in versions
    assert isinstance(versions["django"], tuple)
    assert len(versions["django"]) >= 2
