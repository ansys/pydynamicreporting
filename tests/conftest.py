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

"""Global fixtures go here."""

from pathlib import Path
from random import randint
from uuid import uuid4

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL


def pytest_addoption(parser):
    parser.addoption("--use-local-launcher", action="store_true", default=False)
    parser.addoption("--install-path", action="store", default="dev.json")


@pytest.fixture(scope="session")
def get_exec(pytestconfig: pytest.Config) -> str:
    if pytestconfig.getoption("use_local_launcher"):
        return pytestconfig.getoption("install_path")
    return ""


@pytest.fixture(scope="module")
def adr_service_create(pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")

    # Paths setup
    base_dir = Path(__file__).parent / "test_data"
    local_db = base_dir / f"auto_delete_{str(uuid4()).replace('-', '')}"
    tmp_docker_dir = base_dir / "tmp_docker_create"

    if use_local:
        adr_service = Service(
            ansys_installation=pytestconfig.getoption("install_path"),
            db_directory=str(local_db),
            port=8000 + randint(0, 3999),
        )
    else:
        adr_service = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(local_db),
            data_directory=str(tmp_docker_dir),
            port=8000 + randint(0, 3999),
        )

    adr_service.start(create_db=True, exit_on_close=True, delete_db=True)

    yield adr_service  # Return to running the test session

    # Cleanup
    adr_service.stop()


@pytest.fixture(scope="module")
def adr_service_query(pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")

    # Paths setup
    base_dir = Path(__file__).parent / "test_data"
    local_db = base_dir / "query_db"
    tmp_docker_dir = base_dir / "tmp_docker_query"

    if use_local:
        adr_service = Service(
            ansys_installation=pytestconfig.getoption("install_path"),
            db_directory=str(local_db),
            port=8000 + randint(0, 3999),
        )
    else:
        adr_service = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(local_db),
            data_directory=str(tmp_docker_dir),
            port=8000 + randint(0, 3999),
        )
        adr_service._docker_launcher.save_config()

    adr_service.start(create_db=False, exit_on_close=True, delete_db=False)

    yield adr_service  # Return to running the test session

    # Cleanup
    adr_service.stop()
