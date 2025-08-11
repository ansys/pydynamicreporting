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
            media_url="/media1/",
            static_url="/static2/",
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
            media_url="/media1/",
            static_url="/static2/",
        )
    return adr


# Setup ADR after initialization
@pytest.fixture(scope="session", autouse=False)
def adr_serverless(adr_init: ADR) -> ADR:
    adr_init.setup(collect_static=True)
    yield adr_init
    adr_init.close()
