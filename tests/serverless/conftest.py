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

from pathlib import Path
from uuid import uuid4

import pytest

from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.serverless import ADR


# Initialize ADR without setup
@pytest.fixture(scope="session", autouse=False)
def adr_init(pytestconfig: pytest.Config) -> ADR:
    use_local = pytestconfig.getoption("use_local_launcher")

    base_dir = Path(__file__).parent / "test_data"
    static_dir = base_dir / "static"

    if use_local:
        local_db = base_dir / f"auto_delete_{uuid4().hex}"
        media_dir = base_dir / "media"
        media_dir.mkdir(exist_ok=True)
        adr = ADR(
            ansys_installation=pytestconfig.getoption("install_path"),
            db_directory=local_db,
            static_directory=static_dir,
            media_url="/media/",
            static_url="/static/",
        )
    else:
        # existing db directory
        source_db = base_dir / "documentation_examples"
        dest_db = base_dir / "dest"
        database_config = {
            "default": {
                "ENGINE": "sqlite3",
                "NAME": str(source_db / "db.sqlite3"),
                "USER": "nexus",
                "PASSWORD": "cei",
                "HOST": "",
                "PORT": "",
            },
            "dest": {
                "ENGINE": "sqlite3",
                "NAME": str(dest_db / "db.sqlite3"),
                "USER": "nexus",
                "PASSWORD": "cei",
                "HOST": "",
                "PORT": "",
            },
        }
        adr = ADR(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            databases=database_config,
            media_directory=source_db / "media",
            static_directory=static_dir,
            media_url="/media/",
            static_url="/static/",
        )
    return adr


# Setup ADR after initialization
@pytest.fixture(scope="session", autouse=False)
def adr_serverless(adr_init: ADR) -> ADR:
    adr_init.setup(collect_static=True)
    yield adr_init
    adr_init.close()
