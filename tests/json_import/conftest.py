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

"""Shared fixtures for the JSON item import tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.utils.report_remote_server import Server


@pytest.fixture
def rest_server() -> Server:
    """An offline REST ``Server`` that builds real ``ItemREST`` objects.

    Only ``put_objects`` is mocked, so the real ``create_item`` and
    ``set_payload_*`` validation runs on every imported item.
    """
    server = Server()
    server._api_version = 1.0
    server.put_objects = MagicMock(return_value=requests.codes.ok)
    server.del_objects = MagicMock(return_value=requests.codes.ok)
    return server


@pytest.fixture
def serverless_adr() -> ADR:
    """A non-singleton ``ADR`` whose ``create_item`` returns inspectable mocks.

    ``object.__new__`` bypasses the singleton so the mocks attached here
    never leak into the shared instance other serverless tests use.
    """
    adr = object.__new__(ADR)
    adr._logger = MagicMock()
    adr.create_item = MagicMock(
        side_effect=lambda item_class, **kwargs: MagicMock(
            name=f"item::{item_class.__name__}", _item_class=item_class, _kwargs=kwargs
        )
    )
    return adr
