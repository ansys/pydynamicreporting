"""Global fixtures go here."""
import os
from random import choice, random
from string import ascii_letters

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL


def pytest_addoption(parser):
    parser.addoption("--use-local-launcher", default=False, action="store_true")
    parser.addoption("--install-path", action="store", default="dev.json")


@pytest.fixture(scope="session")
def get_exec(pytestconfig: pytest.Config) -> str:
    exec_basis = ""
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        exec_basis = pytestconfig.getoption("install_path")
    return exec_basis


@pytest.fixture(scope="session")
def adr_service_create(request, pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")
    dir_name = "auto_delete_" + "".join(choice(ascii_letters) for x in range(5))
    db_dir = os.path.join(os.path.join(request.fspath.dirname, "test_data"), dir_name)
    tmp_docker_dir = os.path.join(os.path.join(request.fspath.dirname, "test_data"), "tmp_docker")
    if use_local:
        adr_service = Service(
            ansys_installation=pytestconfig.getoption("install_path"),
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    else:
        adr_service = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            data_directory=tmp_docker_dir,
            port=8000 + int(random() * 4000),
        )

    _ = adr_service.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    # return to running the test session
    yield adr_service
    # cleanup
    adr_service.stop()


@pytest.fixture(scope="session")
def adr_service_query(request, pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")
    local_db = os.path.join("test_data", "query_db")
    db_dir = os.path.join(request.fspath.dirname, local_db)
    tmp_docker_dir = os.path.join(
        os.path.join(request.fspath.dirname, "test_data"), "tmp_docker_query"
    )
    if use_local:
        ansys_installation = pytestconfig.getoption("install_path")
    else:
        ansys_installation = "docker"
    adr_service = Service(
        ansys_installation=ansys_installation,
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=db_dir,
        data_directory=tmp_docker_dir,
        port=8000 + int(random() * 4000),
    )
    if not use_local:
        adr_service._container.save_config()
    adr_service.start(create_db=False, exit_on_close=True, delete_db=False)
    # return to running the test session
    yield adr_service
    # cleanup
    adr_service.stop()
