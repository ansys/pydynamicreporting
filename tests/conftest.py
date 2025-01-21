"""Global fixtures go here."""
from pathlib import Path
from random import randint
from uuid import uuid4

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.serverless import ADR


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


@pytest.fixture(scope="session")
def adr_serverless_create(pytestconfig: pytest.Config) -> ADR:
    use_local = pytestconfig.getoption("use_local_launcher")

    base_dir = Path(__file__).parent / "test_data"
    local_db = base_dir / f"auto_delete_{uuid4().hex}"
    static_dir = base_dir / "static"
    static_dir.mkdir(exist_ok=True)

    if use_local:
        adr = ADR(
            ansys_installation=pytestconfig.getoption("install_path"),
            db_directory=local_db,
            static_directory=static_dir,
            media_url="/media1/",
            static_url="/static2/",
        )
    else:
        adr = ADR(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=local_db,
            static_directory=static_dir,
            media_url="/media1/",
            static_url="/static2/",
        )
    adr.setup(collect_static=True)

    yield adr

    # Cleanup
    adr.close()
