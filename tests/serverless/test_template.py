from uuid import uuid4

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
def test_template_set_params_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_params_none", tags="dp=dp227")
    template.set_params(None)
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_params() == {}


@pytest.mark.ado_test
def test_template_add_params_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_params_none", tags="dp=dp227")
    template.add_params(None)
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_params() == {}


@pytest.mark.ado_test
def test_template_set_property_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_property_none", tags="dp=dp227")
    template.set_property(None)
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {}


@pytest.mark.ado_test
def test_template_add_property_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_property_none", tags="dp=dp227")
    template.add_property(None)
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {}


@pytest.mark.ado_test
def test_template_add_properties_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_add_properties_none", tags="dp=dp227")
    template.add_properties(None)
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_property() == {}


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


@pytest.mark.ado_test
def test_template_set_sort_selection_all(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_sort_selection_all", tags="dp=dp227")
    template.set_sort_selection("all")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_sort_selection() == "all"


@pytest.mark.ado_test
def test_template_set_sort_selection_first(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_sort_selection_first", tags="dp=dp227")
    template.set_sort_selection("first")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_sort_selection() == "first"


@pytest.mark.ado_test
def test_template_set_sort_selection_last(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_sort_selection_last", tags="dp=dp227")
    template.set_sort_selection("last")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_sort_selection() == "last"


@pytest.mark.ado_test
def test_template_set_sort_selection_invalid_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(
        name="test_template_set_sort_selection_invalid_type", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="sort selection input should be a string"):
        template.set_sort_selection(123)


@pytest.mark.ado_test
def test_template_set_sort_selection_invalid_value(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(
        name="test_template_set_sort_selection_invalid_value", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="sort selection not among the acceptable inputs"):
        template.set_sort_selection("invalid-option")


@pytest.mark.ado_test
def test_template_set_filter_mode_items(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_filter_mode_items", tags="dp=dp227")
    template.set_filter_mode("items")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_filter_mode() == "items"


@pytest.mark.ado_test
def test_template_set_filter_mode_root_replace(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(
        name="test_template_set_filter_mode_root_replace", tags="dp=dp227"
    )
    template.set_filter_mode("root_replace")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_filter_mode() == "root_replace"


@pytest.mark.ado_test
def test_template_set_filter_mode_root_append(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_set_filter_mode_root_append", tags="dp=dp227")
    template.set_filter_mode("root_append")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert out.get_filter_mode() == "root_append"


@pytest.mark.ado_test
def test_template_set_filter_mode_invalid_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(
        name="test_template_set_filter_mode_invalid_type", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="filter mode input should be a string"):
        template.set_filter_mode(123)


@pytest.mark.ado_test
def test_template_set_filter_mode_invalid_value(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(
        name="test_template_set_filter_mode_invalid_value", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="filter mode not among the acceptable inputs"):
        template.set_filter_mode("invalid-mode")


@pytest.mark.ado_test
def test_template_reorder_children(adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout, PanelLayout

    # Create parent template
    parent = PanelLayout.create(name="test_template_reorder_children", tags="dp=dp227")

    # Create child templates
    child1 = BasicLayout.create(name="child1", parent=parent)
    child2 = BasicLayout.create(name="child2", parent=parent)
    child3 = BasicLayout.create(name="child3", parent=parent)

    # Manually set the parent's children
    parent.children = [child1, child2, child3]
    parent._children_order = f"{child2.guid},{child3.guid},{child1.guid}"  # Desired order
    parent.reorder_children()

    # After reorder, check order
    assert [child.name for child in parent.children] == ["child2", "child3", "child1"]


@pytest.mark.ado_test
def test_layout_set_get_column_count(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_column_count", tags="dp=dp227")
    layout.set_column_count(3)
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_column_count() == 3


@pytest.mark.ado_test
def test_layout_set_column_count_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_column_count_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="column count input should be an integer"):
        layout.set_column_count("not-an-integer")

    with pytest.raises(ValueError, match="column count input should be larger than 0"):
        layout.set_column_count(0)


@pytest.mark.ado_test
def test_layout_set_get_column_widths(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_column_widths", tags="dp=dp227")
    layout.set_column_widths([1.0, 2.0])
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_column_widths() == [1.0, 2.0]


@pytest.mark.ado_test
def test_layout_set_column_widths_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_column_widths_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="column widths input should be a list"):
        layout.set_column_widths("not-a-list")

    with pytest.raises(
        ValueError, match="column widths input should be a list of integers or floats"
    ):
        layout.set_column_widths([1, "bad", 3])

    with pytest.raises(ValueError, match="column widths input should be larger than 0"):
        layout.set_column_widths([1, -2])


@pytest.mark.ado_test
def test_layout_set_get_html(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_html", tags="dp=dp227")
    layout.set_html("<h1>Hello</h1>")
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_html() == "<h1>Hello</h1>"


@pytest.mark.ado_test
def test_layout_set_html_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_html_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="input needs to be a string"):
        layout.set_html(123)


@pytest.mark.ado_test
def test_layout_set_get_comments(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_comments", tags="dp=dp227")
    layout.set_comments("This is a comment")
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_comments() == "This is a comment"


@pytest.mark.ado_test
def test_layout_set_comments_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_comments_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="input needs to be a string"):
        layout.set_comments(456)


@pytest.mark.ado_test
def test_layout_set_get_transpose(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_transpose", tags="dp=dp227")
    layout.set_transpose(1)
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_transpose() == 1


@pytest.mark.ado_test
def test_layout_set_transpose_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_transpose_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="input needs to be an integer"):
        layout.set_transpose("not-integer")


@pytest.mark.ado_test
def test_layout_set_get_skip_empty(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_skip", tags="dp=dp227")
    layout.set_skip(1)
    layout.save()
    out = PanelLayout.get(guid=layout.guid)
    assert out.get_skip() == 1


@pytest.mark.ado_test
def test_layout_set_skip_empty_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    layout = PanelLayout.create(name="test_layout_skip_invalid", tags="dp=dp227")

    with pytest.raises(ValueError, match="input needs to be an integer"):
        layout.set_skip("invalid")

    with pytest.raises(ValueError, match="input needs to be an integer \\(0 or 1\\)"):
        layout.set_skip(5)


@pytest.mark.ado_test
def test_generator_set_get_generated_items(adr_serverless):
    from ansys.dynamicreporting.core.serverless import TableMergeGenerator

    generator = TableMergeGenerator.create(name="test_generator_generated_items", tags="dp=dp227")
    generator.set_generated_items("replace")
    generator.save()
    out = TableMergeGenerator.get(guid=generator.guid)
    assert out.get_generated_items() == "replace"


@pytest.mark.ado_test
def test_generator_set_generated_items_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import TableMergeGenerator

    generator = TableMergeGenerator.create(
        name="test_generator_generated_items_invalid", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="generated items should be a string"):
        generator.set_generated_items(123)

    with pytest.raises(ValueError, match="input should be add or replace"):
        generator.set_generated_items("invalid-option")


@pytest.mark.ado_test
def test_generator_set_get_append_tags(adr_serverless):
    from ansys.dynamicreporting.core.serverless import TableMergeGenerator

    generator = TableMergeGenerator.create(name="test_generator_append_tags", tags="dp=dp227")
    generator.set_append_tags(False)
    generator.save()
    out = TableMergeGenerator.get(guid=generator.guid)
    assert out.get_append_tags() is False


@pytest.mark.ado_test
def test_generator_set_append_tags_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import TableMergeGenerator

    generator = TableMergeGenerator.create(
        name="test_generator_append_tags_invalid", tags="dp=dp227"
    )

    with pytest.raises(ValueError, match="value should be True / False"):
        generator.set_append_tags("not-boolean")


@pytest.mark.ado_test
def test_template_str(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_str", tags="dp=dp227")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert isinstance(str(out), str)
    assert "PanelLayout" in str(out) and out.guid in str(out)


@pytest.mark.ado_test
def test_template_repr(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_repr", tags="dp=dp227")
    template.save()

    out = PanelLayout.get(guid=template.guid)

    assert isinstance(repr(out), str)
    assert "PanelLayout" in repr(out) and out.guid in repr(out)


@pytest.mark.ado_test
def test_template_delete(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_delete", tags="dp=dp227")
    template.save()

    template_guid = template.guid
    template.delete()

    with pytest.raises(PanelLayout.DoesNotExist):
        PanelLayout.get(guid=template_guid)


@pytest.mark.ado_test
def test_template_get_success(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_get_success", tags="dp=dp227")
    template.save()
    out = PanelLayout.get(guid=template.guid)
    assert out.guid == template.guid


@pytest.mark.ado_test
def test_template_get_invalid_kwargs(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_get_invalid_kwargs", tags="dp=dp227")
    template.save()

    with pytest.raises(
        ValueError, match="'children' kwarg is not supported for get and filter methods"
    ):
        p1 = PanelLayout.create(name="test_template_get_invalid_kwargs1", tags="dp=dp227")
        PanelLayout.get(children=[p1])


@pytest.mark.ado_test
def test_template_get_not_exist(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    with pytest.raises(PanelLayout.DoesNotExist):
        PanelLayout.get(guid=str(uuid4()))


@pytest.mark.ado_test
def test_template_get_multiple(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    PanelLayout.create(name="test_template_get_multiple", tags="dp=dp227").save()
    PanelLayout(name="test_template_get_multiple", tags="dp=dp227").save()

    with pytest.raises(PanelLayout.MultipleObjectsReturned):
        PanelLayout.get(name="test_template_get_multiple")


@pytest.mark.ado_test
def test_template_filter_success(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_filter_success", tags="dp=dp227")
    template.save()
    out = PanelLayout.filter(name="test_template_filter_success")
    assert out[0].guid == template.guid


@pytest.mark.ado_test
def test_template_find_success(adr_serverless):
    from ansys.dynamicreporting.core.serverless import PanelLayout

    template = PanelLayout.create(name="test_template_find_success", tags="dp=dp227")
    template.save()
    out = PanelLayout.find(query="A|t_name|cont|test_template_find_success")
    assert out[0].guid == template.guid


@pytest.mark.ado_test
def test_template_find_raises_exception(adr_serverless):
    from ansys.dynamicreporting.core.exceptions import ADRException
    from ansys.dynamicreporting.core.serverless import PanelLayout

    with pytest.raises(ADRException):
        PanelLayout.find(query="A|t_types|cont|panel")


@pytest.mark.ado_test
def test_template_render(monkeypatch, adr_serverless):
    from ansys.dynamicreporting.core.serverless import BasicLayout
    from ansys.dynamicreporting.core.serverless import template as template_module

    # Create a basic template instance.
    template = adr_serverless.create_template(
        BasicLayout, name="test_render_template", parent=None, tags="dp=dp227"
    )

    # Patch django.template.loader.render_to_string to return a fixed string.
    def fake_render_to_string(template_name, context, request):
        # Check that the expected template file is requested.
        assert template_name == "reports/report_display_simple.html"
        # Instead of an exact match, check for a few essential keys.
        assert context.get("plotly") == 1 and context.get("page_width") == 10.5
        return "dummy rendered content"

    monkeypatch.setattr(template_module, "render_to_string", fake_render_to_string)

    # Call the render method on the template.
    result = template.render(
        context={"plotly": 1, "pwidth": "10.5", "dpi": "96."},
        item_filter="A|i_tags|cont|dp=dp227;",
        request=None,
    )

    # Assert that the final rendered content matches the fixed string.
    assert result == "dummy rendered content"


@pytest.mark.ado_test
def test_pptx_layout_render_pptx_success(adr_serverless, monkeypatch):
    # The rendering engine is located in the 'reports' app of the Ansys core installation
    from reports.engine import TemplateEngine

    from ansys.dynamicreporting.core.serverless import PPTXLayout

    pptx_template = adr_serverless.create_template(
        PPTXLayout, name="TestRenderPPTXSuccess", parent=None
    )

    def fake_dispatch_render(self, render_type, items, context):
        # This fake method simulates a successful render by the engine
        assert render_type == "pptx"
        return b"mock pptx content from engine"

    monkeypatch.setattr(TemplateEngine, "dispatch_render", fake_dispatch_render)

    pptx_bytes = pptx_template.render_pptx()

    assert pptx_bytes == b"mock pptx content from engine"


@pytest.mark.ado_test
def test_pptx_layout_render_pptx_failure_wraps_exception(adr_serverless, monkeypatch):
    from reports.engine import TemplateEngine

    from ansys.dynamicreporting.core.exceptions import ADRException
    from ansys.dynamicreporting.core.serverless import PPTXLayout

    pptx_template = adr_serverless.create_template(
        PPTXLayout, name="TestRenderPPTXFailure", parent=None
    )

    def fake_dispatch_render_fails(self, render_type, items, context):
        raise ValueError("Simulated engine failure")

    monkeypatch.setattr(TemplateEngine, "dispatch_render", fake_dispatch_render_fails)

    with pytest.raises(ADRException, match="Failed to render PPTX for template"):
        pptx_template.render_pptx()


@pytest.mark.ado_test
def test_to_json(adr_serverless):
    import json
    import os

    from ansys.dynamicreporting.core.serverless import BasicLayout, PanelLayout

    root = adr_serverless.create_template(
        BasicLayout,
        name="A",
        parent=None,
        tags="dp=dp1",
        params='{"HTML": "<h1>Serverless Simulation Report</h1>"}',
    )

    adr_serverless.create_template(PanelLayout, name="B", parent=root, tags="dp=dp2")

    child_1 = adr_serverless.create_template(
        BasicLayout, name="C", parent=root, tags="dp=dp3", params='{"HTML": "<h2>Basic C</h2>"}'
    )

    adr_serverless.create_template(
        BasicLayout, name="D", parent=child_1, tags="dp=dp4", params='{"HTML": "<h2>Basic D</h2>"}'
    )

    file_path = os.path.join(adr_serverless.static_directory, "test.json")
    root.to_json(file_path)

    with open(file_path, encoding="utf-8") as json_file:
        data = json.load(json_file)

    assert (
        data["Template_0"]["children"] == ["Template_1", "Template_2"]
        and data["Template_0"]["name"] == "A"
        and data["Template_1"]["children"] == []
        and data["Template_1"]["name"] == "B"
        and data["Template_2"]["children"] == ["Template_3"]
        and data["Template_2"]["name"] == "C"
        and data["Template_3"]["children"] == []
        and data["Template_3"]["name"] == "D"
    )


@pytest.mark.ado_test
def test_to_json_non_root_template(adr_serverless):
    from ansys.dynamicreporting.core.exceptions import ADRException
    from ansys.dynamicreporting.core.serverless import BasicLayout

    # Create a parent template
    root_template = adr_serverless.create_template(
        BasicLayout,
        name="RootTemplate",
        parent=None,
        tags="dp=dp1",
    )

    # Create a child template
    child_template = adr_serverless.create_template(
        BasicLayout,
        name="ChildTemplate",
        parent=root_template,
        tags="dp=dp2",
    )

    # Attempt to call to_json on the child template and expect an ADRException
    with pytest.raises(ADRException, match="Only root templates can be dumped to JSON files."):
        child_template.to_json("dummy_path.json")
