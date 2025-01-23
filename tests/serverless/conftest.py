from pathlib import Path
from uuid import uuid4

import pytest
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.serverless import ADR


@pytest.fixture(scope="session")
def adr_serverless(pytestconfig: pytest.Config) -> ADR:
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
