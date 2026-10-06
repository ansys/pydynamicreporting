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

"""Public-API tests for ``Service.import_from_json``."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.utils.json_import import ImportResult


def _write_document(tmp_path: Path) -> Path:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema_version": "1.0", "app_id": "demo-app"}), encoding="utf-8")
    return path


@pytest.mark.unit
def test_import_from_json_delegates_to_the_importer(tmp_path: Path):
    service = Service.__new__(Service)
    service.logger = MagicMock()
    path = _write_document(tmp_path)
    expected = ImportResult(schema_version="1.0", app_id="demo-app")

    with patch(
        "ansys.dynamicreporting.core.utils.json_import.importer.JSONImporter"
    ) as importer_cls:
        importer_cls.return_value.import_file.return_value = expected
        result = service.import_from_json(path)

    assert result is expected
    importer_cls.return_value.import_file.assert_called_once_with(
        path, on_error="collect", base_dir=None, strict_keys=False
    )


@pytest.mark.unit
def test_import_from_json_forwards_every_option(tmp_path: Path):
    service = Service.__new__(Service)
    service.logger = MagicMock()
    path = _write_document(tmp_path)

    with patch(
        "ansys.dynamicreporting.core.utils.json_import.importer.JSONImporter"
    ) as importer_cls:
        service.import_from_json(path, on_error="raise", base_dir="/media", strict_keys=True)

    importer_cls.return_value.import_file.assert_called_once_with(
        path, on_error="raise", base_dir="/media", strict_keys=True
    )


@pytest.mark.unit
def test_import_from_json_uses_the_server_backend(tmp_path: Path):
    from ansys.dynamicreporting.core.import_backend_server import ServerImportBackend

    service = Service.__new__(Service)
    service.logger = MagicMock()
    path = _write_document(tmp_path)

    with patch(
        "ansys.dynamicreporting.core.utils.json_import.importer.JSONImporter"
    ) as importer_cls:
        service.import_from_json(path)

    backend = importer_cls.call_args.args[0]
    assert isinstance(backend, ServerImportBackend)
