import pytest


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
