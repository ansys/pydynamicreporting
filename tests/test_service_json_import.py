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

"""Public-API tests for ``Service.import_items_from_json``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.exceptions import ConnectionToServiceError


def _service(serverobj) -> Service:
    service = Service.__new__(Service)
    service.logger = MagicMock()
    service.serverobj = serverobj
    return service


@pytest.mark.unit
def test_import_from_json_forwards_every_option_to_the_server():
    service = _service(MagicMock())
    document = {"schema_version": "1.0", "app_id": "demo-app"}

    result = service.import_items_from_json(document, on_error="raise", base_dir="/media")

    assert result is service.serverobj.import_items_from_json.return_value
    service.serverobj.import_items_from_json.assert_called_once_with(
        document, on_error="raise", base_dir="/media", logger=service.logger
    )


@pytest.mark.unit
def test_import_from_json_requires_a_connection():
    service = _service(None)
    with pytest.raises(ConnectionToServiceError):
        service.import_items_from_json({"app_id": "demo-app"})
    service.logger.error.assert_called_once()
