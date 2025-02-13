from django.core.exceptions import ImproperlyConfigured
import pytest


@pytest.mark.ado_test
def test_import_no_setup():
    from ansys.dynamicreporting.core.serverless import Session

    with pytest.raises(ImproperlyConfigured):
        Session.create()


@pytest.mark.ado_test
def test_import(adr_serverless):
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
