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

    results_panel = PanelLayout.create(name="test_edit_template", tags="dp=dp227")
    results_panel.params = (
        '{"HTML": "<h2>Results</h2>\\nYour simulation results.", "properties": {"TOCItem": "1"}}'
    )
    results_panel.save()

    assert "Your simulation results" in PanelLayout.get(name="test_edit_template").params


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
    from ansys.dynamicreporting.core.serverless import BasicLayout

    with pytest.raises(TypeError):
        top_parent = BasicLayout(name="test_raise_child_type_save", parent=None, tags="dp=dp227")
        top_parent.children.append("T1")
        top_parent.save()


@pytest.mark.ado_test
def test_as_dict(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, TOCLayout

    top_parent = adr_serverless.create_template(
        BasicLayout,
        name="test_as_dict",
        parent=None,
        tags="dp=dp227",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )

    toc_layout = adr_serverless.create_template(
        TOCLayout, name="TOC", parent=top_parent, tags="dp=dp227"
    )
    toc_layout.params = '{"TOCitems": 1, "HTML": "<h2>Table of Content</h2>"}'
    toc_layout.set_filter("A|i_name|eq|__NonexistentName__;")
    toc_layout.save()

    top_dict = top_parent.as_dict(recursive=True)

    assert (
        top_dict["name"] == "test_as_dict"
        and top_dict["tags"] == "dp=dp227"
        and top_dict["params"] == '{"HTML": "<h1>Serverless Simulation Report</h1>"}'
        and top_dict["children"][0] == toc_layout.guid
    )


@pytest.mark.ado_test
def test_child_not_exist(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, TOCLayout

    top_parent = adr_serverless.create_template(
        BasicLayout,
        name="test_child_not_exist",
        parent=None,
        tags="dp=dp227",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )
    toc_layout = TOCLayout(name="TOC", parent=top_parent, tags="dp=dp227")
    toc_layout._saved = True  # fake save
    top_parent.children.append(toc_layout)
    with pytest.raises(BasicLayout.DoesNotExist):
        top_parent.save()
