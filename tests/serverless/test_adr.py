from pathlib import Path
from random import random as r

import numpy as np
import pytest

from ansys.dynamicreporting.core.serverless import ADR


@pytest.mark.ado_test
def test_create_no_setup():
    from ansys.dynamicreporting.core.serverless import Session

    with pytest.raises(RuntimeError):
        Session.create()


@pytest.mark.ado_test
def test_get_instance_error():
    with pytest.raises(RuntimeError):
        ADR.get_instance()


@pytest.mark.ado_test
def test_get_instance_no_setup():
    from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL

    adr = ADR(  # noqa: F841
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        media_url="/media1/",
        static_url="/static2/",
        in_memory=True,
    )
    assert ADR.get_instance() is adr


@pytest.mark.ado_test
def test_ensure_setup_error_no_setup():
    from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL

    adr = ADR(  # noqa: F841
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        media_url="/media1/",
        static_url="/static2/",
        in_memory=True,
    )

    with pytest.raises(RuntimeError):
        ADR.ensure_setup()


@pytest.mark.ado_test
def test_is_setup_before_setup():
    assert not ADR.get_instance().is_setup


@pytest.mark.ado_test
def test_get_instance(adr_serverless):
    assert ADR.get_instance() is adr_serverless


@pytest.mark.ado_test
def test_is_setup_after_setup(adr_serverless):
    assert adr_serverless.is_setup


@pytest.mark.ado_test
def test_setup_after_setup(adr_serverless):
    with pytest.raises(RuntimeError):
        adr_serverless.setup(collect_static=True)


@pytest.mark.ado_test
def test_get_instance_session():
    from ansys.dynamicreporting.core.serverless import Session

    adr = ADR.get_instance()
    assert adr.session is not None and isinstance(adr.session, Session) and adr.session_guid


@pytest.mark.ado_test
def test_get_instance_dataset():
    from ansys.dynamicreporting.core.serverless import Dataset

    adr = ADR.get_instance()
    assert adr.dataset is not None and isinstance(adr.dataset, Dataset) and adr.dataset.guid


@pytest.mark.ado_test
def test_init_twice(adr_serverless):
    from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL

    adr = ADR(
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=adr_serverless.db_directory,
        static_directory=adr_serverless.static_directory,
        media_url="/media1/",
        static_url="/static2/",
    )
    assert adr is adr_serverless


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


@pytest.mark.ado_test
def test_create_html(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    # HTML item
    item_html = (
        "<h1>Heading 1</h1>"
        "<h2>Heading 2</h2>"
        "<h3>Heading 3</h3>"
        "<h4>Heading 4</h4>"
        "<h5>Heading 5</h5>"
        "Two breaks below"
        "<br><br />"
        "<h6>Heading 6 (& one break below)</h6>"
        "<br>"
        "The end"
    )
    intro_html = adr_serverless.create_item(
        HTML,
        name="intro_html",
        content=item_html,
        source="sls-test",
    )
    assert HTML.get(name="intro_html").guid == intro_html.guid


@pytest.mark.ado_test
def test_set_tags(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.get(name="intro_html")
    intro_html.set_tags("dp=dp227 section=intro")
    intro_html.save()

    assert "section=intro" in HTML.get(guid=intro_html.guid).tags


@pytest.mark.ado_test
def test_get_tags(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.get(name="intro_html")
    assert "dp=dp227" in intro_html.get_tags()


@pytest.mark.ado_test
def test_edit_html(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.get(name="intro_html")
    intro_html.content = (
        "<h1>Heading 1</h1>"
        "<h2>Heading 2</h2>"
        "<h3>Heading 3</h3>"
        "<h4>Heading 4</h4>"
        "<h5>Heading 5</h5>"
        "Two breaks below"
        "<br><br />"
        "<h6>Heading 6 (& one break below)</h6>"
        "<br>"
    )
    intro_html.save()

    assert "end" not in HTML.get(guid=intro_html.guid).content


@pytest.mark.ado_test
def test_add_rem_tag(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    intro_html = HTML.get(name="intro_html")
    intro_html.add_tag("pptx_slide_title", "headers and breaks")
    intro_html.save()
    intro_html.rem_tag("pptx_slide_title")
    intro_html.save()

    assert "pptx_slide_title" not in HTML.get(guid=intro_html.guid).get_tags()


@pytest.mark.ado_test
def test_create_html_bad_content(adr_serverless):
    from ansys.dynamicreporting.core.serverless import HTML

    with pytest.raises(ValueError):  # must be valid HTML
        adr_serverless.create_item(HTML, name="empty_html", content="lololol")


@pytest.mark.ado_test
def test_create_string(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    # string
    item_text = "This section describes the settings for the simulation: initial conditions, solver settings, and such."
    intro_text = adr_serverless.create_item(
        String,
        name="intro_text",
        content=item_text,
        tags="dp=dp227 section=intro",
        source="sls-test",
    )

    assert String.get(name="intro_text").guid == intro_text.guid


@pytest.mark.ado_test
def test_create_string_no_content(adr_serverless):
    from ansys.dynamicreporting.core.serverless import String

    with pytest.raises(ValueError):  # must be str
        adr_serverless.create_item(String, name="empty_text", content=None)


@pytest.mark.ado_test
def test_create_anim(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Animation

    # anim
    anim = adr_serverless.create_item(
        Animation,
        name="intro_anim",
        content=str(Path(__file__).parent / "test_data" / "movie.mp4"),
        tags="dp=dp227 section=data",
        source="sls-test",
        sequence=1,
    )

    assert Animation.get(name="intro_anim").guid == anim.guid


@pytest.mark.ado_test
def test_create_anim_no_content(adr_serverless):  # content is None
    from ansys.dynamicreporting.core.serverless import Animation

    with pytest.raises(ValueError):
        adr_serverless.create_item(Animation, name="empty_anim", content=None)


@pytest.mark.ado_test
def test_create_anim_no_file(adr_serverless):  # file does not exist
    from ansys.dynamicreporting.core.serverless import Animation

    with pytest.raises(ValueError):
        adr_serverless.create_item(
            Animation,
            name="bad_anim",
            content=str(Path(__file__).parent / "test_data" / "lolol.mp4"),
        )


@pytest.mark.ado_test
def test_create_anim_bad_format(adr_serverless):  # file is not a video
    from ansys.dynamicreporting.core.serverless import Animation

    with pytest.raises(ValueError):
        adr_serverless.create_item(
            Animation,
            name="bad_anim",
            content=str(Path(__file__).parent / "test_data" / "scene.avz"),
        )


@pytest.mark.ado_test
def test_create_file(adr_serverless):
    from ansys.dynamicreporting.core.serverless import File

    # file
    file = adr_serverless.create_item(
        File,
        name="intro_file",
        content=str(Path(__file__).parent / "test_data" / "input.pptx"),
        tags="dp=dp227 section=data",
        source="sls-test",
        sequence=1,
    )

    assert File.get(name="intro_file").guid == file.guid


@pytest.mark.ado_test
def test_create_file_csf(adr_serverless):
    from ansys.dynamicreporting.core.serverless import File

    # csf
    intro_csf = adr_serverless.create_item(
        File,
        name="intro_csf",
        content=str(Path(__file__).parent / "test_data" / "scene1.csf"),
        tags="dp=dp227 section=data",
        source="sls-test",
        sequence=1,
    )

    assert File.get(name="intro_csf").guid == intro_csf.guid


@pytest.mark.ado_test
def test_create_file_ens(adr_serverless):
    from ansys.dynamicreporting.core.serverless import File

    # ens
    intro_ens = adr_serverless.create_item(
        File,
        name="intro_ens",
        content=str(Path(__file__).parent / "test_data" / "scene2.ens"),
        tags="dp=dp227 section=data",
        source="sls-test",
        sequence=1,
    )

    assert File.get(name="intro_ens").guid == intro_ens.guid


@pytest.mark.ado_test
def test_create_file_evsn(adr_serverless):
    from ansys.dynamicreporting.core.serverless import File

    # evsn
    intro_evsn = adr_serverless.create_item(
        File,
        name="intro_evsn",
        content=str(Path(__file__).parent / "test_data" / "scenario.evsn"),
        tags="dp=dp227 section=data",
        source="sls-test",
        sequence=1,
    )

    assert File.get(name="intro_evsn").guid == intro_evsn.guid


@pytest.mark.ado_test
def test_create_image(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # image
    intro_image = adr_serverless.create_item(
        Image,
        name="intro_image",
        content=str(Path(__file__).parent / "test_data" / "nexus_logo.png"),
        tags="dp=dp227 section=data",
        source="sls-test",
    )

    assert Image.get(name="intro_image").guid == intro_image.guid


@pytest.mark.ado_test
def test_create_enhanced_image(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Image

    # enhanced image
    intro_enhanced_image = adr_serverless.create_item(
        Image,
        name="intro_enhanced_image",
        content=str(Path(__file__).parent / "test_data" / "case.tif"),
        tags="dp=dp227 section=data",
        source="sls-test",
    )

    assert Image.get(name="intro_enhanced_image").guid == intro_enhanced_image.guid


@pytest.mark.ado_test
def test_create_scene(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Scene

    # scene
    scene = adr_serverless.create_item(
        Scene,
        name="intro_scene",
        content=str(Path(__file__).parent / "test_data" / "scene.avz"),
        session=adr_serverless.session,  # random test
        dataset=adr_serverless.dataset,
        tags="dp=dp227 section=data",
        source="sls-test",
    )

    assert Scene.get(name="intro_scene").guid == scene.guid


@pytest.mark.ado_test
def test_create_table(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Table

    # table
    ics = []
    ips = []
    zet = []
    for i in range(30):
        ics.append(i / 5.0)
        ips.append(np.sin((i + 6 * 0) * np.pi / 10.0) + r() * 0.1)
        zet.append(np.cos((i + 6 * 0) * np.pi / 10.0) + r() * 0.1)

    intro_table = adr_serverless.create_item(
        Table,
        name="intro_table",
        content=np.array([ics, ips, zet], dtype="|S20"),
        tags="dp=0 type=hex8",
        source="sls-test",
    )

    intro_table.labels_row = ["X", "Sin", "Cos"]
    intro_table.set_tags("dp=dp227 section=data")
    intro_table.plot = "line"
    intro_table.xaxis = "X"
    intro_table.yaxis = ["Sin", "Cos"]
    intro_table.xaxis_format = "floatdot0"
    intro_table.yaxis_format = "floatdot1"
    intro_table.ytitle = "Values"
    intro_table.xtitle = "X"

    intro_table.save()

    assert Table.get(name="intro_table").guid == intro_table.guid


@pytest.mark.ado_test
def test_create_tree(adr_serverless):
    from ansys.dynamicreporting.core.serverless import Tree

    # tree
    tree_content = [
        {"key": "root", "name": "Solver", "value": "My Solver"},
        {"key": "root", "name": "Number cells", "value": 10e6},
        {"key": "root", "name": "Mesh Size", "value": "1.0 mm^3"},
        {"key": "root", "name": "Mesh Type", "value": "Hex8"},
    ]
    # alternative way of creation
    tree = adr_serverless.create_item(
        Tree,
        name="intro_tree",
        content=tree_content,
        tags="dp=dp227 section=data",
        session=adr_serverless.session,
        dataset=adr_serverless.dataset,
        source="sls-test",
    )

    assert Tree.get(name="intro_tree").guid == tree.guid
