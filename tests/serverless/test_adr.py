from django.core.exceptions import ImproperlyConfigured
import pytest

from ansys.dynamicreporting.core.serverless import ADR


@pytest.mark.ado_test
def test_import_no_setup():
    from ansys.dynamicreporting.core.serverless import Session

    with pytest.raises(ImproperlyConfigured):
        Session.create()


@pytest.mark.ado_test
def test_get_instance_error():
    with pytest.raises(RuntimeError):
        ADR.get_instance()


@pytest.mark.ado_test
def test_get_instance_error_no_setup():
    from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL

    ADR(
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        media_url="/media1/",
        static_url="/static2/",
        in_memory=True,
    )
    with pytest.raises(RuntimeError):
        ADR.get_instance()


@pytest.mark.ado_test
def test_get_instance(adr_serverless):
    assert ADR.get_instance() is adr_serverless


@pytest.mark.ado_test
def test_init_twice(adr_serverless):
    from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL

    adr = ADR(
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=adr_serverless.db_directory,
        static_directory=adr_serverless.static_directory,
        media_url="/media1/",
        static_url="/static2/",
    )
    assert adr is adr_serverless


@pytest.mark.ado_test
def test_import(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    assert String is not None


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
