import pytest


@pytest.mark.ado_test
def test_create_template_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout.create(name="test_create_template_cls", tags="dp=dp227")

    assert PanelLayout.get(name="test_create_template_cls").guid == results_panel.guid


@pytest.mark.ado_test
def test_init_template_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout(name="test_init_template_cls", tags="dp=dp227")
    results_panel.save()

    assert PanelLayout.get(name="test_init_template_cls").guid == results_panel.guid


@pytest.mark.ado_test
def test_edit_template(adr_serverless):
    # Templates/reports
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout.create(name="Results", tags="dp=dp227")
    results_panel.params = (
        '{"HTML": "<h2>Results</h2>\\nYour simulation results.", "properties": {"TOCItem": "1"}}'
    )
    results_panel.save()

    assert "Your simulation results" in PanelLayout.get(name="Results").params


@pytest.mark.ado_test
def test_raise_child_type_init(adr_serverless):
    # Templates/reports
    from ansys.dynamicreporting.core.serverless import BasicLayout

    with pytest.raises(TypeError):
        BasicLayout(
            name="test_raise_child_type_init", parent=None, tags="dp=dp227", children=["T1"]
        )


@pytest.mark.ado_test
def test_raise_child_type_create(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout

    with pytest.raises(TypeError):
        BasicLayout.create(
            name="test_raise_child_type_create", parent=None, tags="dp=dp227", children=["T1"]
        )


@pytest.mark.ado_test
def test_raise_child_type_save(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, PanelLayout

    with pytest.raises(TypeError):
        top_parent = BasicLayout(name="Serverless Simulation Report", parent=None, tags="dp=dp227")
        top_parent.children.append("T1")
        top_parent.save()
