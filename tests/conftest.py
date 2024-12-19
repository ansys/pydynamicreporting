"""Global fixtures go here."""

from pathlib import Path
from random import randint
from uuid import uuid4

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL


def pytest_addoption(parser):
    parser.addoption("--use-local-launcher", default=False, action="store_true")
    parser.addoption("--install-path", action="store", default="dev.json")


@pytest.fixture(scope="module")
def get_exec(pytestconfig: pytest.Config) -> str:
    exec_basis = ""
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        exec_basis = pytestconfig.getoption("install_path")
    return exec_basis


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

    if not use_local:
        adr_service._container.save_config()

    adr_service.start(create_db=False, exit_on_close=True, delete_db=False)

    yield adr_service  # Return to running the test session

    # Cleanup
    adr_service.stop()
