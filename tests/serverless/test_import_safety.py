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

import builtins
from dataclasses import MISSING, fields
import importlib
import platform
import sys

import pytest


def _block_product_imports(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"ceiversion", "enve", "reports.engine"}:
            raise AssertionError(f"Unexpected import during serverless module load: {name}")
        if name == "reports" and "engine" in fromlist:
            raise AssertionError("Unexpected import during serverless module load: reports.engine")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


@pytest.mark.ado_test
def test_serverless_item_reload_does_not_import_product_modules(monkeypatch):
    import ansys.dynamicreporting.core.serverless.item as item_module
    import ansys.dynamicreporting.core.utils.geofile_processing as geofile_processing_module
    import ansys.dynamicreporting.core.utils.report_utils as report_utils_module

    for module_name in ("ceiversion", "enve", "reports.engine"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    _block_product_imports(monkeypatch)

    reloaded_report_utils = importlib.reload(report_utils_module)
    importlib.reload(geofile_processing_module)
    reloaded_item = importlib.reload(item_module)

    session_fields = {field.name: field for field in fields(reloaded_item.Session)}

    assert session_fields["hostname"].default is MISSING
    assert session_fields["hostname"].default_factory is platform.node
    assert session_fields["platform"].default is MISSING
    assert session_fields["platform"].default_factory is reloaded_report_utils.enve_arch
    assert reloaded_report_utils.has_enve is False
    assert reloaded_report_utils.enve_arch() == platform.system().lower()
