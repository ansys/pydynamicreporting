# Copyright (C) 2023 - 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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

"""Tests for Dependabot and lockfile CI guardrails."""

from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_uv_dependabot_entry() -> dict:
    config = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    uv_entries = [entry for entry in config["updates"] if entry["package-ecosystem"] == "uv"]
    assert len(uv_entries) == 1
    return uv_entries[0]


def test_dependabot_ignores_all_shipped_dependencies_only():
    """Dependabot must ignore every shipped runtime dependency while keeping test/doc/dev active."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    shipped = {
        canonicalize_name(Requirement(spec).name) for spec in pyproject["project"]["dependencies"]
    }
    optional_deps = {
        canonicalize_name(Requirement(spec).name)
        for specs in pyproject["project"].get("optional-dependencies", {}).values()
        for spec in specs
    }

    uv_entry = _load_uv_dependabot_entry()
    assert {"dependency-type": "direct"} in uv_entry.get("allow", [])

    ignored = {
        canonicalize_name(rule["dependency-name"])
        for rule in uv_entry.get("ignore", [])
        if "update-types" not in rule and "versions" not in rule
    }

    missing_shipped = shipped - ignored
    assert not missing_shipped, (
        f"Shipped runtime dependencies missing from .github/dependabot.yml ignore list: {sorted(missing_shipped)}"
    )

    ignored_optional = (optional_deps - shipped) & ignored
    assert not ignored_optional, (
        f"Optional test/doc/dev dependencies must not be ignored in .github/dependabot.yml: {sorted(ignored_optional)}"
    )


def test_ci_enforces_uv_lock_consistency():
    """CI style job must verify uv.lock stays in sync with pyproject.toml."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci_cd.yml").read_text(encoding="utf-8")
    )
    style_steps = workflow["jobs"]["style"]["steps"]
    lock_steps = [step for step in style_steps if step.get("run") == "uv lock --locked"]
    assert len(lock_steps) == 1
