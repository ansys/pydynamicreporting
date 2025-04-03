import pytest

from src.ansys.dynamicreporting.core.exceptions import InvalidFieldError


@pytest.mark.ado_test
def test_field_error(adr_serverless):
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
def test_add_rem_tag(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.create(
        name="test_create_html_cls",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    intro_html.add_tag("pptx_slide_title", "headers and breaks")
    intro_html.save()

    assert "pptx_slide_title" in HTML.get(guid=intro_html.guid).get_tags()

    intro_html.rem_tag("pptx_slide_title")
    intro_html.remove_tag("pptx_slide_title")
    intro_html.save()

    assert "pptx_slide_title" not in HTML.get(guid=intro_html.guid).get_tags()


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
        name="test_set_tags",
        tags="dp=dp227",
        content="<h1>Heading 1</h1>",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
    )
    assert "dp=dp227" in HTML.get(guid=intro_html.guid).get_tags()
