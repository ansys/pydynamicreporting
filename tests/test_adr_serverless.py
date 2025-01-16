import pytest


@pytest.mark.ado_test
def test_set_default_session(adr_serverless_create):
    from ansys.dynamicreporting.core.serverless import Session

    session = Session.create(application="serverless test default sesh", tags="dp=dp227")
    adr_serverless_create.set_default_session(session)
    assert adr_serverless_create.session_guid == session.guid


@pytest.mark.ado_test
def test_set_default_session_no_session(adr_serverless_create):
    adr_serverless_create.set_default_session(None)
    assert adr_serverless_create.session_guid is None


@pytest.mark.ado_test
def test_set_default_dataset(adr_serverless_create):
    from ansys.dynamicreporting.core.serverless import Dataset

    dataset = Dataset.create(filename="serverless test default dataset", tags="dp=dp227")
    adr_serverless_create.set_default_dataset(dataset)
    assert adr_serverless_create.dataset.guid == dataset.guid


@pytest.mark.ado_test
def test_set_default_dataset_no_dataset(adr_serverless_create):
    adr_serverless_create.set_default_dataset(None)
    assert adr_serverless_create.dataset is None
