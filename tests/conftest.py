"""Global fixtures go here."""
import os
from random import choice, random
import shutil
from string import ascii_letters
import subprocess

import pytest

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL


def pytest_addoption(parser):
    parser.addoption("--use-local-launcher", default=False, action="store_true")
    parser.addoption("--install-path", action="store", default="dev.json")


def cleanup_docker(request) -> None:
    # Stop and remove 'nexus' containers. This needs to be deleted once we address the issue
    # in the pynexus code by giving unique names to the containers
    try:
        subprocess.run(["docker", "stop", "nexus"])
        subprocess.run(["docker", "rm", "nexus"])
    except Exception:
        # There might not be a running nexus container. That is fine, just continue
        pass
    try:
        querydb_dir = os.path.join(os.path.join(request.fspath.dirname, "test_data"), "query_db")
        os.remove(os.path.join(querydb_dir, "nexus.log"))
        os.remove(os.path.join(querydb_dir, "nexus.status"))
        shutil.rmtree(os.path.join(querydb_dir, "nginx"))
    except Exception:
        # There might not be these files / directories. In which case, nothing to do
        pass


@pytest.fixture
def get_exec(pytestconfig: pytest.Config) -> str:
    exec_basis = ""
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        exec_basis = pytestconfig.getoption("install_path")
    return exec_basis


@pytest.fixture
def adr_service_create(request, pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")
    dir_name = "auto_delete_" + "".join(choice(ascii_letters) for x in range(5))
    db_dir = os.path.join(os.path.join(request.fspath.dirname, "test_data"), dir_name)
    tmp_docker_dir = os.path.join(os.path.join(request.fspath.dirname, "test_data"), "tmp_docker")
    if use_local:
        tmp_service = Service(
            ansys_installation=pytestconfig.getoption("install_path"),
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    else:
        cleanup_docker(request)
        tmp_service = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            data_directory=tmp_docker_dir,
            port=8000 + int(random() * 4000),
        )
    return tmp_service


@pytest.fixture
def adr_service_query(request, pytestconfig: pytest.Config) -> Service:
    use_local = pytestconfig.getoption("use_local_launcher")
    local_db = os.path.join("test_data", "query_db")
    db_dir = os.path.join(request.fspath.dirname, local_db)
    if use_local:
        ansys_installation = pytestconfig.getoption("install_path")
    else:
        cleanup_docker(request)
        ansys_installation = "docker"
    tmp_service = Service(
        ansys_installation=ansys_installation,
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=db_dir,
        port=8000 + int(random() * 4000),
    )
    tmp_service.start(create_db=False, exit_on_close=True, delete_db=False)
    return tmp_service
