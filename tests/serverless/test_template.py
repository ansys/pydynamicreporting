import pytest

from ansys.dynamicreporting.core.exceptions import ADRException


@pytest.mark.ado_test
def test_create_template_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout.create(name="test_create_template_cls", tags="dp=dp227")

    assert PanelLayout.get(name="test_create_template_cls").guid == results_panel.guid


@pytest.mark.ado_test
def test_get_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout(name="test_get_type", tags="dp=dp227")
    results_panel.save()

    assert PanelLayout.get(guid=results_panel.guid).type == "Layout:panel"


@pytest.mark.ado_test
def test_template_props(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PPTXLayout

    pptx_template = PPTXLayout(name="pptx")
    pptx_template.input_pptx = "input.pptx"
    pptx_template.output_pptx = "output-get.pptx"
    pptx_template.use_all_slides = "1"
    pptx_template.save()
    out = PPTXLayout.get(guid=pptx_template.guid)
    assert (
        out.input_pptx == "input.pptx"
        and out.output_pptx == "output-get.pptx"
        and out.use_all_slides == "1"
    )


@pytest.mark.ado_test
def test_init_template_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    results_panel = PanelLayout(name="test_init_template_cls", tags="dp=dp227")
    results_panel.save()

    assert PanelLayout.get(name="test_init_template_cls").guid == results_panel.guid


@pytest.mark.ado_test
def test_init_template_super_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Template

    with pytest.raises(ADRException, match="Cannot instantiate Template directly"):
        Template(name="test_init_template_super_cls", tags="dp=dp227", report_type="Layout:panel")


@pytest.mark.ado_test
def test_create_template_super_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Template

    template = Template.create(
        name="test_create_template_super_cls", tags="dp=dp227", report_type="Layout:panel"
    )
    assert Template.get(guid=template.guid).guid == template.guid


@pytest.mark.ado_test
def test_create_template_super_cls_no_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Template

    with pytest.raises(ADRException):
        Template.create(name="test_create_template_super_cls_no_type_error", tags="dp=dp227")


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
def test_parent_not_saved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, TOCLayout

    top_parent = BasicLayout(
        name="test_parent_not_saved",
        parent=None,
        tags="dp=dp227",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )
    toc_layout = TOCLayout(name="TOC", parent=top_parent, tags="dp=dp227")
    with pytest.raises(BasicLayout.NotSaved):
        toc_layout.save()


@pytest.mark.ado_test
def test_child_bad_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML, BasicLayout

    top_parent = adr_serverless.create_template(
        BasicLayout,
        name="test_child_bad_type",
        parent=None,
        tags="dp=dp227",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )
    # Wrong type of child
    toc_layout = HTML.create(
        name="test_child_bad_type_item",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    top_parent.children.append(toc_layout)
    with pytest.raises(TypeError):
        top_parent.save()


@pytest.mark.ado_test
def test_child_not_saved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, TOCLayout

    top_parent = adr_serverless.create_template(
        BasicLayout,
        name="test_child_not_saved",
        parent=None,
        tags="dp=dp227",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )
    toc_layout = TOCLayout(name="TOC", parent=top_parent, tags="dp=dp227")
    top_parent.children.append(toc_layout)
    with pytest.raises(TOCLayout.NotSaved):
        top_parent.save()


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
    toc_layout._saved = True  # Simulate that the child is saved, but does not exist in the database
    top_parent.children.append(toc_layout)
    with pytest.raises(TOCLayout.NotSaved):
        top_parent.save()


@pytest.mark.ado_test
def test_create_template(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout

    template_kwargs = {
        "name": "test_create_template",
        "parent": None,
        "tags": "dp=dp227",
        "params": '{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    }
    template = BasicLayout.create(**template_kwargs)
    assert template.saved is True


@pytest.mark.ado_test
def test_template_set_property(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_property", tags="dp=dp227")
    template.set_property({"custom_prop_1": "value1"})
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {"custom_prop_1": "value1"}


@pytest.mark.ado_test
def test_template_add_property(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_property", tags="dp=dp227")
    template.set_property({"custom_prop_1": "value1"})
    template.add_property({"custom_prop_2": "value2"})
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {
        "custom_prop_1": "value1",
        "custom_prop_2": "value2",
    }


@pytest.mark.ado_test
def test_template_add_properties(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_properties", tags="dp=dp227")
    template.set_property({"custom_prop_1": "value1"})
    template.add_properties({"custom_prop_2": "value2", "custom_prop_3": "value3"})
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {
        "custom_prop_1": "value1",
        "custom_prop_2": "value2",
        "custom_prop_3": "value3",
    }


@pytest.mark.ado_test
def test_template_set_property_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_property_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="input must be a dictionary"):
        template.set_property(["not", "a", "dict"])


@pytest.mark.ado_test
def test_template_add_property_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_property_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="input must be a dictionary"):
        template.add_property("not-a-dict")


@pytest.mark.ado_test
def test_template_add_properties_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_properties_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="input must be a dictionary"):
        template.add_properties(1234)


@pytest.mark.ado_test
def test_template_set_params(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_params", tags="dp=dp227")
    template.set_params({"param1": "value1"})
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_params() == {"param1": "value1"}


@pytest.mark.ado_test
def test_template_add_params(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_params", tags="dp=dp227")
    template.set_params({"param1": "value1"})
    template.add_params({"param2": "value2"})
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_params() == {
        "param1": "value1",
        "param2": "value2",
    }


@pytest.mark.ado_test
def test_template_set_params_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_params_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="input must be a dictionary"):
        template.set_params("not-a-dict")


@pytest.mark.ado_test
def test_template_add_params_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_params_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="input must be a dictionary"):
        template.add_params(1234)


@pytest.mark.ado_test
def test_template_set_filter(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_filter", tags="dp=dp227")
    template.set_filter("A|i_tags|cont|dp=dp227;")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_filter() == "A|i_tags|cont|dp=dp227;"


@pytest.mark.ado_test
def test_template_add_filter(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_filter", tags="dp=dp227")
    template.set_filter("A|i_tags|cont|dp=dp227;")
    template.add_filter("A|i_tags|cont|section=data;")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_filter() == "A|i_tags|cont|dp=dp227;A|i_tags|cont|section=data;"


@pytest.mark.ado_test
def test_template_set_filter_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_filter_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="filter value should be a string"):
        template.set_filter(123)


@pytest.mark.ado_test
def test_template_add_filter_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_filter_type_error", tags="dp=dp227")

    with pytest.raises(TypeError, match="filter value should be a string"):
        template.add_filter(456)


@pytest.mark.ado_test
def test_template_set_sort_fields(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_sort_fields", tags="dp=dp227")
    template.set_sort_fields(["name", "date"])
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_sort_fields() == ["name", "date"]


@pytest.mark.ado_test
def test_template_add_sort_fields(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_sort_fields", tags="dp=dp227")
    template.set_sort_fields(["name"])
    template.add_sort_fields(["date", "tags"])
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_sort_fields() == ["name", "date", "tags"]


@pytest.mark.ado_test
def test_template_set_sort_fields_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_sort_fields_type_error", tags="dp=dp227")

    with pytest.raises(ValueError, match="sorting filter is not a list"):
        template.set_sort_fields("not-a-list")


@pytest.mark.ado_test
def test_template_add_sort_fields_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_sort_fields_type_error", tags="dp=dp227")

    with pytest.raises(ValueError, match="sorting filter is not a list"):
        template.add_sort_fields("field_should_be_list")
