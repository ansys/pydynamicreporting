"""Global fixtures go here."""

from pathlib import Path
from random import choice, random
from string import ascii_letters

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
    dir_name = "auto_delete_" + "".join(choice(ascii_letters) for _ in range(5))
    db_dir = base_dir / dir_name
    tmp_docker_dir = base_dir / "tmp_docker"

    if use_local:
        adr_service = Service(
            ansys_installation=pytestconfig.getoption("install_path"),
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(db_dir),
            port=8000 + int(random() * 4000),
        )
    else:
        adr_service = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(db_dir),
            data_directory=str(tmp_docker_dir),
            port=8000 + int(random() * 4000),
        )

    _ = adr_service.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )

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
        ansys_installation = pytestconfig.getoption("install_path")
    else:
        ansys_installation = "docker"

    adr_service = Service(
        ansys_installation=ansys_installation,
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=str(local_db),
        data_directory=str(tmp_docker_dir),
        port=8000 + int(random() * 4000),
    )

    if not use_local:
        adr_service._container.save_config()

    adr_service.start(create_db=False, exit_on_close=True, delete_db=False)

    yield adr_service  # Return to running the test session

    # Cleanup
    adr_service.stop()


@pytest.fixture
def adr_template_json(pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")

    # Paths setup
    base_dir = Path(__file__).parent / "test_data"
    local_db = base_dir / "template_json"
    tmp_docker_dir = base_dir / "tmp_docker_query"

    if use_local:
        ansys_installation = pytestconfig.getoption("install_path")
    else:
        ansys_installation = "docker"

    adr_service = Service(
        ansys_installation=ansys_installation,
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=str(local_db),
        data_directory=str(tmp_docker_dir),
        port=8000 + int(random() * 4000),
    )

    if not use_local:
        adr_service._container.save_config()

    adr_service.start(create_db=False, exit_on_close=True, delete_db=False)

    yield adr_service  # Return to running the test session

    # Cleanup
    adr_service.stop()
