from pathlib import Path

import pytest

from ansys.dynamicreporting.core.exceptions import InvalidPath
from ansys.dynamicreporting.core.serverless import ADR


def test_init_simple(adr_serverless):  # existing directory
    base_dir = Path(__file__).parent / "test_data"
    dest_dir = base_dir / "dest" / "db.sqlite3"
    adr = ADR(
        ansys_installation=adr_serverless._ansys_installation,
        db_directory=dest_dir,
    )
    adr.setup()
    assert adr.is_setup


def test_init_empty(adr_serverless, tmp_path):
    db_dir = tmp_path / "test_init_empty"
    db_dir.mkdir(parents=True, exist_ok=True)  # create beforehand
    # empty directory test
    with pytest.raises(InvalidPath):
        adr = ADR(
            ansys_installation=adr_serverless._ansys_installation,
            db_directory=db_dir,
        )
        adr.setup()


def test_init_new(adr_serverless, tmp_path):  # creates new directory
    db_dir = tmp_path / "test_init_new"
    adr = ADR(ansys_installation=adr_serverless._ansys_installation, db_directory=db_dir)
    adr.setup()
    assert adr.is_setup


def test_init_multiple(adr_serverless):  # multiple databases
    # Paths setup
    base_dir = Path(__file__).parent / "test_data"
    doc_ex = base_dir / "documentation_examples" / "db.sqlite3"
    dest_dir = base_dir / "dest" / "db.sqlite3"
    database_config = {
        "default": {
            "ENGINE": "sqlite3",
            "NAME": str(doc_ex),
            "USER": "nexus",
            "PASSWORD": "cei",
            "HOST": "",
            "PORT": "",
        },
        "dest": {
            "ENGINE": "sqlite3",
            "NAME": str(dest_dir),
            "USER": "nexus",
            "PASSWORD": "cei",
            "HOST": "",
            "PORT": "",
        },
    }
    adr = ADR(
        ansys_installation=adr_serverless._ansys_installation,
        databases=database_config,
        media_directory=doc_ex.parent / "media",
    )
    adr.setup()
    assert adr.is_setup


@pytest.mark.ado_test
def test_import_without_setup(adr_serverless):
    with pytest.raises(ImportError):
        ADR(
            ansys_installation=adr_serverless._ansys_installation,
            db_directory=adr_serverless._db_directory,
            debug=True,
        )
        from ansys.dynamicreporting.core.serverless import String  # noqa: F406


@pytest.mark.ado_test
def test_import_with_setup(adr_serverless):
    adr = ADR(
        ansys_installation=adr_serverless._ansys_installation,
        db_directory=adr_serverless._db_directory,
        debug=True,
    )
    adr.setup()
    from ansys.dynamicreporting.core.serverless import String

    assert String is not None


@pytest.mark.ado_test
def test_setup_already_setup(adr_serverless):
    with pytest.raises(RuntimeError):
        adr_serverless.setup()


@pytest.mark.ado_test
def test_set_default_session(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Session

    session = Session.create(application="serverless test default sesh", tags="dp=dp227")
    adr_serverless.set_default_session(session)
    assert adr_serverless.session_guid == session.guid


@pytest.mark.ado_test
def test_set_default_session_no_session(adr_serverless):
    with pytest.raises(TypeError, match="Must be an instance of type 'Session'"):
        adr_serverless.set_default_session(None)


@pytest.mark.ado_test
def test_set_default_dataset(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Dataset

    dataset = Dataset.create(filename="serverless test default dataset", tags="dp=dp227")
    adr_serverless.set_default_dataset(dataset)
    assert adr_serverless.dataset.guid == dataset.guid


@pytest.mark.ado_test
def test_set_default_dataset_no_dataset(adr_serverless):
    with pytest.raises(TypeError, match="Must be an instance of type 'Dataset'"):
        adr_serverless.set_default_dataset(None)
