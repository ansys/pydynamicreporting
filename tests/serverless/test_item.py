from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.ado_test
def test_field_error(adr_serverless):
    from ansys.dynamicreporting.core.exceptions import InvalidFieldError
    from ansys.dynamicreporting.core.serverless import HTML

    with pytest.raises(InvalidFieldError):
        assert HTML.get(lol=1)


@pytest.mark.ado_test
def test_field_type_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    with pytest.raises(TypeError):
        HTML.create(
            name=1,  # error
            content="<h1>Heading 1</h1>",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_create_html_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_create_html_cls",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert HTML.get(name="test_create_html_cls").guid == intro_html.guid


@pytest.mark.ado_test
def test_str(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_str",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert str(intro_html) == f"<HTML: {intro_html.guid}>"


@pytest.mark.ado_test
def test_repr(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_repr",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert repr(intro_html) == f"<HTML: {intro_html.guid}>"


@pytest.mark.ado_test
def test_add_tag(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_add_tag",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.add_tag("pptx_slide_title", value="headers and breaks")
    intro_html.save()

    assert "pptx_slide_title" in HTML.get(guid=intro_html.guid).get_tags()


@pytest.mark.ado_test
def test_add_tag_key(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    intro_text = String(
        name="intro_text",
        content="intro text",
        tags="dp=dp227 section=intro",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_text.add_tag("sls-test")
    intro_text.save()

    assert "sls-test" in String.get(guid=intro_text.guid).tags


@pytest.mark.ado_test
def test_rem_tag(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_rem_tag",
        content="<h1>Heading 1</h1>",
        tags="tag1=1 tag2",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.rem_tag("tag1")
    intro_html.remove_tag("tag2")
    intro_html.save()

    tags = HTML.get(guid=intro_html.guid).get_tags()
    assert "tag1" not in tags and "tag2" not in tags


@pytest.mark.ado_test
def test_rem_empty_tag(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_rem_empty_tag",
        content="<h1>Heading 1</h1>",
        tags="",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.rem_tag("tag1")
    intro_html.remove_tag("tag2")
    intro_html.save()

    tags = HTML.get(guid=intro_html.guid).get_tags()
    assert "tag1" not in tags and "tag2" not in tags


@pytest.mark.ado_test
def test_set_tags(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_set_tags",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.set_tags("section=intro")
    intro_html.save()

    assert "section" in HTML.get(guid=intro_html.guid).tags


@pytest.mark.ado_test
def test_get_tags(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_get_tags",
        tags="dp=dp227",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert "dp=dp227" in HTML.get(guid=intro_html.guid).get_tags()


@pytest.mark.ado_test
def test_db(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_db",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    from django.conf import settings

    assert intro_html.db in settings.DATABASES


@pytest.mark.ado_test
def test_reinit(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_reinit",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.reinit()
    assert intro_html.saved is False


@pytest.mark.ado_test
def test_integrity_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_integrity_error",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    with pytest.raises(HTML.IntegrityError):
        HTML.create(
            guid=intro_html.guid,
            name="test_integrity_error",
            content="<h1>Heading 1</h1>",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_delete_not_saved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML(
        name="test_delete_not_saved",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    with pytest.raises(HTML.NotSaved):
        intro_html.delete()


@pytest.mark.ado_test
def test_get_item(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_get_item",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    item = HTML.get(guid=intro_html.guid)
    assert item.guid == intro_html.guid


@pytest.mark.ado_test
def test_get_item_does_not_exist(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    with pytest.raises(HTML.DoesNotExist):
        HTML.get(guid=str(uuid4()))


@pytest.mark.ado_test
def test_get_item_multiple(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    HTML.create(
        name="test_get_item_multiple",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    HTML(
        name="test_get_item_multiple",
        content="<h1>Heading 2</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    ).save()
    with pytest.raises(HTML.MultipleObjectsReturned):
        HTML.get(name="test_get_item_multiple")


@pytest.mark.ado_test
def test_get_or_create_item(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_kwargs = {
        "name": "intro_tree",
        "source": "sls-test",
        "tags": "dp=dp227",
        "session": adr_serverless.session,
        "dataset": adr_serverless.dataset,
    }
    tree, _ = Tree.get_or_create(**tree_kwargs)
    new_tree, _ = Tree.get_or_create(**tree_kwargs)
    assert new_tree.guid == tree.guid


@pytest.mark.ado_test
def test_get_or_create_item_w_content(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = [
        {"key": "root", "name": "Solver", "value": "My Solver"},
        {"key": "root", "name": "Number cells", "value": 10e6},
        {"key": "root", "name": "Mesh Size", "value": "1.0 mm^3"},
        {"key": "root", "name": "Mesh Type", "value": "Hex8"},
    ]
    # tree
    tree_kwargs = {
        "name": "intro_tree",
        "content": tree_content,
        "source": "sls-test",
        "tags": "dp=dp227",
        "session": adr_serverless.session,
        "dataset": adr_serverless.dataset,
    }
    with pytest.raises(ValueError):
        Tree.get_or_create(**tree_kwargs)


@pytest.mark.ado_test
def test_item_objectset_repr(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_objectset_repr",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(query_type=HTML, query="A|i_name|cont|test_item_objectset_repr;")
    assert repr(objs) == f"<ObjectSet  [<HTML: {intro_html.guid}>]>"


@pytest.mark.ado_test
def test_item_objectset_str(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_objectset_str",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(query_type=HTML, query="A|i_name|cont|test_item_objectset_str;")
    assert str(objs) == f"[<HTML: {intro_html.guid}>]"


@pytest.mark.ado_test
def test_item_objectset_getitem(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_objectset_getitem",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(query_type=HTML, query="A|i_name|cont|test_item_objectset_getitem;")
    assert objs[0].guid == intro_html.guid


@pytest.mark.ado_test
def test_item_objectset_saved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    HTML.create(
        name="test_item_objectset_saved",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(query_type=HTML, query="A|i_name|cont|test_item_objectset_saved;")
    assert objs.saved is True


@pytest.mark.ado_test
def test_item_objectset_values_list(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    HTML.create(
        name="test_item_objectset_values_list",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(
        query_type=HTML, query="A|i_name|cont|test_item_objectset_values_list;"
    )
    assert objs.values_list("name", flat=True) == ["test_item_objectset_values_list"]


@pytest.mark.ado_test
def test_item_objectset_values_list_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    HTML.create(
        name="test_item_objectset_values_list_error",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(
        query_type=HTML, query="A|i_name|cont|test_item_objectset_values_list_error;"
    )
    with pytest.raises(ValueError):
        objs.values_list("name", "guid", flat=True)


@pytest.mark.ado_test
def test_item_objectset_values_list_empty(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    objs = adr_serverless.query(
        query_type=HTML, query="A|i_name|cont|test_item_objectset_values_list_empty;"
    )
    assert objs.values_list("name", flat=True) == []


@pytest.mark.ado_test
def test_string_content_none(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    with pytest.raises(ValueError):
        String(
            name="test_string_content_none",
            content=None,
            tags="dp=dp227",
            source="sls-test",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_string_content_wrong_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    with pytest.raises(TypeError):
        String(
            name="test_string_content_wrong_type",
            content=1,
            tags="dp=dp227",
            source="sls-test",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_string_content_empty(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    string = String(
        name="test_string_content_empty",
        content="",
        tags="dp=dp227",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    string.save()
    assert String.get(guid=string.guid).content == ""


@pytest.mark.ado_test
def test_table_content_not_numpy(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Table

    with pytest.raises(TypeError):
        Table(
            name="test_table_content_not_numpy",
            content="",
            tags="dp=dp227",
            source="sls-test",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_table_content_invalid_dtype(adr_serverless):
    import numpy as np

    from ansys.dynamicreporting.core.serverless import Table

    with pytest.raises(TypeError):
        Table(
            name="test_table_content_invalid_dtype",
            content=np.array([[1, 2], [3, 4]], dtype=int),  # Invalid dtype
            session=adr_serverless.session,
            tags="dp=dp227",
            source="sls-test",
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_table_content_invalid_shape(adr_serverless):
    import numpy as np

    from ansys.dynamicreporting.core.serverless import Table

    with pytest.raises(ValueError):
        Table(
            name="test_table_content_invalid_shape",
            content=np.array([1, 2, 3], dtype="|S20"),  # Invalid shape (1D array instead of 2D)
            session=adr_serverless.session,
            tags="dp=dp227",
            source="sls-test",
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_create_tree_success(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = [
        {"key": "root", "name": "Solver", "value": "My Solver"},
        {"key": "root", "name": "Number cells", "value": 10e6},
    ]
    tree = Tree.create(
        name="test_create_tree_success",
        content=tree_content,
        tags="dp=dp227 section=data",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
        source="sls-test",
    )
    assert Tree.get(guid=tree.guid).guid == tree.guid


@pytest.mark.ado_test
@pytest.mark.parametrize(
    "bad_content",
    [
        [{"name": "Missing key", "value": "Oops"}],  # Missing 'key'
        [{"key": "root", "value": "Oops"}],  # Missing 'name'
        [{"key": "root", "name": "Missing value"}],  # Missing 'value'
    ],
)
def test_create_tree_missing_keys(adr_serverless, bad_content):
    from ansys.dynamicreporting.core.serverless import Tree

    with pytest.raises(ValueError):
        Tree.create(
            name="test_create_tree_missing_keys",
            content=bad_content,
            tags="dp=dp227 section=data",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )


@pytest.mark.ado_test
def test_create_tree_invalid_value_type(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    bad_content = [{"key": "root", "name": "Invalid value", "value": {"not": "allowed"}}]
    with pytest.raises(ValueError):
        Tree.create(
            name="test_create_tree_invalid_value_type",
            content=bad_content,
            tags="dp=dp227 section=data",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )


@pytest.mark.ado_test
def test_create_tree_non_dict_element(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    bad_content = [
        {"key": "root", "name": "Good", "value": "OK"},
        "I am not a dictionary",
    ]
    with pytest.raises(ValueError):
        Tree.create(
            name="test_create_tree_non_dict_element",
            content=bad_content,
            tags="dp=dp227 section=data",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )


@pytest.mark.ado_test
def test_create_tree_invalid_nested_value(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    bad_content = [
        {
            "key": "root",
            "name": "Nested Tree",
            "value": "Root",
            "children": [{"key": "child", "name": "Bad Child", "value": {"bad": "value"}}],
        }
    ]
    with pytest.raises(ValueError):
        Tree.create(
            name="test_create_tree_invalid_nested_value",
            content=bad_content,
            tags="dp=dp227 section=data",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )
