from pathlib import Path
import tempfile
from uuid import uuid4

from PIL import Image as PILImage
import pytest

from ansys.dynamicreporting.core.exceptions import ADRException


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
def test_create_item_cls(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item

    intro_html = Item.create(
        name="test_create_item_cls",
        type="html",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert Item.get(guid=intro_html.guid).guid == intro_html.guid


@pytest.mark.ado_test
def test_create_item_cls_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item

    with pytest.raises(ADRException):
        Item.create(
            name="test_create_item_cls_error",
            content="<h1>Heading 1</h1>",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_item_cls_init(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item

    with pytest.raises(ADRException):
        Item(
            name="test_item_cls_init",
            type="tree",
            content="<h1>Heading 1</h1>",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )


@pytest.mark.ado_test
def test_item_get_w_content_error(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item

    intro_html = Item.create(
        name="test_create_item_cls",
        type="html",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    with pytest.raises(ValueError):
        Item.get(content=intro_html.content)


@pytest.mark.ado_test
def test_item_get_w_session(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item

    intro_html = Item.create(
        name="test_item_get_w_session",
        type="html",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert Item.get(guid=intro_html.guid, session=adr_serverless.session).guid == intro_html.guid


@pytest.mark.ado_test
def get_orm_saved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML(
        name="get_orm_saved",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert intro_html._orm_saved is False


@pytest.mark.ado_test
def test_item_filter(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_filter",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert (
        HTML.filter(
            name="test_item_filter", session=adr_serverless.session, dataset=adr_serverless.dataset
        )[0].guid
        == intro_html.guid
    )


@pytest.mark.ado_test
def test_item_cls_filter(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML, Item

    intro_html = HTML.create(
        name="test_item_cls_filter",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert (
        Item.filter(
            name="test_item_cls_filter",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
        )[0].guid
        == intro_html.guid
    )


@pytest.mark.ado_test
def test_item_find(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_find",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert HTML.find(query="A|i_name|cont|test_item_find")[0].guid == intro_html.guid


@pytest.mark.ado_test
def test_item_find_raises_exception(adr_serverless):
    from ansys.dynamicreporting.core.exceptions import ADRException
    from ansys.dynamicreporting.core.serverless import HTML

    with pytest.raises(ADRException):
        HTML.find(query="A|i_type|cont|html")


@pytest.mark.ado_test
def test_item_cls_find(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML, Item

    intro_html = HTML.create(
        name="test_item_cls_find",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert Item.find(query="A|i_name|cont|test_item_cls_find")[0].guid == intro_html.guid


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
def test_save_item(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML(
        name="test_save_item",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.save()
    assert HTML.get(guid=intro_html.guid).guid == intro_html.guid


@pytest.mark.ado_test
def test_save_item_no_session(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML(
        name="test_save_item_no_session",
        content="<h1>Heading 1</h1>",
        dataset=adr_serverless.dataset,
    )
    with pytest.raises(ADRException):
        intro_html.save()


@pytest.mark.ado_test
def test_save_item_no_dataset(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML(
        name="test_save_item_no_dataset",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
    )
    with pytest.raises(ADRException):
        intro_html.save()


@pytest.mark.ado_test
def test_save_item_session_unsaved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML, Session

    session = Session()
    intro_html = HTML(
        name="test_save_item_session_unsaved",
        content="<h1>Heading 1</h1>",
        session=session,
        dataset=adr_serverless.dataset,
    )
    with pytest.raises(Session.NotSaved):
        intro_html.save()


@pytest.mark.ado_test
def test_save_item_dataset_unsaved(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML, Dataset

    dataset = Dataset()
    intro_html = HTML(
        name="test_save_item_dataset_unsaved",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=dataset,
    )
    with pytest.raises(Dataset.NotSaved):
        intro_html.save()


@pytest.mark.ado_test
def test_create_item(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = [
        {"key": "root", "name": "Solver", "value": "My Solver"},
        {"key": "root", "name": "Number cells", "value": 10e6},
        {"key": "root", "name": "Mesh Size", "value": "1.0 mm^3"},
        {"key": "root", "name": "Mesh Type", "value": "Hex8"},
    ]

    tree_kwargs = {
        "name": "test_create_item",
        "source": "sls-test",
        "content": tree_content,
        "tags": "dp=dp227",
        "session": adr_serverless.session,
        "dataset": adr_serverless.dataset,
    }
    tree = Tree.create(**tree_kwargs)
    assert tree.saved is True


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
def test_item_delete(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_delete",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.delete()
    with pytest.raises(HTML.DoesNotExist):
        HTML.get(guid=intro_html.guid)


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
def test_item_objectset_delete(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_item_objectset_delete",
        content="<h1>Heading 1</h1>",
        source="sls-test",
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    objs = adr_serverless.query(query_type=HTML, query="A|i_name|cont|test_item_objectset_delete;")
    objs.delete()
    with pytest.raises(HTML.DoesNotExist):
        HTML.get(guid=intro_html.guid)


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
def test_table_item_properties(adr_serverless):
    import numpy as np

    from ansys.dynamicreporting.core.serverless import Table

    # Create dummy 2D numpy array for content
    dummy_array = np.array([[1, 2], [3, 4]], dtype="f8")

    table_item = Table(
        name="table-real-test",
        content=dummy_array,
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
        source="sls-test",
    )

    # Set real properties
    table_item.labels_row = ["X", "Sin", "Cos"]
    table_item.set_tags("dp=dp227 section=data")
    table_item.plot = "line"
    table_item.xaxis = "X"
    table_item.yaxis = ["Sin", "Cos"]
    table_item.xaxis_format = "floatdot0"
    table_item.yaxis_format = "floatdot1"
    table_item.ytitle = "Values"
    table_item.xtitle = "X"

    table_item.save()

    # Load it back
    out = Table.get(guid=table_item.guid)

    assert (
        out.labels_row == ["X", "Sin", "Cos"]
        and out.plot == "line"
        and out.xaxis == "X"
        and out.yaxis == ["Sin", "Cos"]
        and out.xaxis_format == "floatdot0"
        and out.yaxis_format == "floatdot1"
        and out.ytitle == "Values"
        and out.xtitle == "X"
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


@pytest.mark.ado_test
def test_tree_content_value_list_valid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = [
        {"key": "root", "name": "Solver List", "value": ["Ansys", "Fluent", "CFX"]},
    ]
    tree = Tree.create(
        name="test_tree_content_value_list_valid",
        content=tree_content,
        tags="dp=dp227",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
        source="sls-test",
    )
    assert Tree.get(guid=tree.guid).guid == tree.guid


@pytest.mark.ado_test
def test_tree_content_value_list_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = [
        {"key": "root", "name": "Solver List", "value": ["Ansys", object()]},
    ]
    with pytest.raises(ValueError):
        Tree.create(
            name="test_tree_content_value_list_invalid",
            content=tree_content,
            tags="dp=dp227",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )


@pytest.mark.ado_test
def test_tree_content_invalid(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    tree_content = "This is not a valid content"
    with pytest.raises(ValueError):
        Tree.create(
            name="test_tree_content_invalid",
            content=tree_content,
            tags="dp=dp227",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )


@pytest.mark.ado_test
def test_item_file_ext_no_save(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = Image(
        name="test_item_file_ext_no_save",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert intro_image.file_ext is None


@pytest.mark.ado_test
def test_item_file_ext(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = Image(
        name="test_item_file_ext",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_image.save()

    assert intro_image.file_ext == "png"


@pytest.mark.ado_test
def test_item_has_no_file(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = Image(
        name="test_item_has_no_file",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )

    assert intro_image.has_file is False


@pytest.mark.ado_test
def test_item_has_file(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = Image(
        name="test_item_has_file",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_image.save()

    assert intro_image.has_file is True


@pytest.mark.ado_test
def test_item_is_enhanced(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = Image(
        name="test_item_is_enhanced",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
    )

    assert intro_image.enhanced is False


@pytest.mark.ado_test
def test_file_size_zero_fails_validation(adr_serverless):
    from ansys.dynamicreporting.core.serverless import File

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(ValueError, match="The file specified is empty"):
            File.create(
                name="test_file_size_zero_fails_validation",
                content=str(tmp_path),
                tags="dp=dp227",
                session=adr_serverless.session,
                dataset=adr_serverless.dataset,
                source="sls-test",
            )
    finally:
        tmp_path.unlink()


def test_image_on_disk(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img = PILImage.new("RGB", (10, 10), color="blue")
        img.save(tmp_path, "PNG")

    try:
        image_obj = Image.create(
            name="test_image_on_disk",
            content=str(tmp_path),
            tags="dp=dp227",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )
        assert Path(image_obj.file_path).is_file() is True and image_obj.file_ext == "png"
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.ado_test
def test_image_conversion_to_png(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img = PILImage.new("RGB", (10, 10), color="red")
        img.save(tmp_path, "JPEG")  # Save as JPEG

    try:
        image_obj = Image.create(
            name="test_image_conversion_to_png",
            content=str(tmp_path),
            tags="dp=dp227",
            session=adr_serverless.session,
            dataset=adr_serverless.dataset,
            source="sls-test",
        )
        file_path = Path(image_obj.file_path)
        assert (
            Path(image_obj._file.name).suffix == ".jpg"
            and file_path.is_file()
            and file_path.suffix == ".png"
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.ado_test
def test_invalid_file_extension_fails(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(b"Dummy content")
        tmp.flush()

    try:
        with pytest.raises(ValueError, match="File type txt is not supported"):
            Image.create(
                name="test_invalid_file_extension_fails",
                content=str(tmp_path),
                tags="dp=dp227",
                session=adr_serverless.session,
                dataset=adr_serverless.dataset,
                source="sls-test",
            )
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.ado_test
def test_image_save_raises_adr_exception(adr_serverless, monkeypatch):
    from ansys.dynamicreporting.core.serverless import Image

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img = PILImage.new("RGB", (10, 10), color="red")
        img.save(tmp_path, "JPEG")

    def fake_save(*args, **kwargs):
        raise OSError("Simulated save error")

    monkeypatch.setattr("PIL.Image.Image.save", fake_save)

    try:
        with pytest.raises(ADRException, match="Error converting image"):
            Image.create(
                name="test_image_save_raises_adr_exception",
                content=str(tmp_path),
                tags="dp=dp227",
                session=adr_serverless.session,
                dataset=adr_serverless.dataset,
                source="sls-test",
            )
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.ado_test
def test_is_enhanced_fails_on_non_enhanced_tiff(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    with tempfile.NamedTemporaryFile(suffix=".tiff", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img = PILImage.new("RGB", (10, 10), color="blue")
        img.save(tmp_path, format="TIFF")

    try:
        with pytest.raises(ADRException, match="The enhanced image is empty"):
            Image.create(
                name="test_is_enhanced_fails_on_non_enhanced_tiff",
                content=str(tmp_path),
                tags="dp=dp227",
                session=adr_serverless.session,
                dataset=adr_serverless.dataset,
                source="sls-test",
            )
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.ado_test
def test_objectset_empty(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Item
    from ansys.dynamicreporting.core.serverless.base import ObjectSet

    # Create an empty ObjectSet
    empty_set = ObjectSet(_model=Item, _orm_model=Item._orm_model_cls, _orm_queryset=None)
    assert empty_set._obj_set == []
