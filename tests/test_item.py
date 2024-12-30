from os.path import join

import numpy as np
import pytest

from ansys.dynamicreporting.core import Item, Service


@pytest.mark.ado_test
def test_create_img(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = join(join(request.fspath.dirname, "test_data"), "aa_00_0_alpha1.png")
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


@pytest.mark.ado_test
def test_create_img_jpg(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = join(join(request.fspath.dirname, "test_data"), "car_crash.jpg")
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


@pytest.mark.ado_test
def test_create_img_tiff(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = join(join(request.fspath.dirname, "test_data"), "displacement.tiff")
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


def test_create_scene(adr_service_create, request) -> None:
    my_scene = adr_service_create.create_item()
    my_scene.item_scene = join(
        join(join(request.fspath.dirname, "test_data"), "scenes"), "scene.avz"
    )
    my_scene.width = 800
    my_scene.height = 500
    assert type(my_scene) is Item


def test_create_text(adr_service_create, request) -> None:
    my_text = adr_service_create.create_item(obj_name="testtext", source="testing")
    my_text.item_text = "<h1>This is my first test of a text item</h1>"
    my_text.item_text = "Now let us change the text just to make sure it works"
    assert my_text.type == "text"


def test_create_file(adr_service_create, request) -> None:
    my_file = adr_service_create.create_item(obj_name="testfile", source="testing")
    my_file.item_file = join(join(request.fspath.dirname, "test_data"), "dam_break.ens")
    assert my_file.type == "file"


def test_create_anim(adr_service_create, request) -> None:
    my_anim = adr_service_create.create_item(obj_name="testanim", source="testing")
    my_anim.item_animation = join(join(request.fspath.dirname, "test_data"), "dam_break.mp4")
    assert my_anim.type == "animation"


def test_create_tree(adr_service_create, request) -> None:
    leaves = []
    for i in range(10):
        leaves.append({"key": "leaves", "name": f"Leaf {i}", "value": i})
    children = []
    children.append({"key": "child", "name": "Boolean example", "value": True})
    children.append({"key": "child", "name": "Integer example", "value": 10})
    children.append(
        {
            "key": "child_parent",
            "name": "A child parent",
            "value": "Parents can have values",
            "children": leaves,
            "state": "expanded",
        }
    )
    children.append({"key": "child", "name": "Float example", "value": 99.99})
    tree = []
    tree.append(
        {
            "key": "root",
            "name": "Top Level",
            "value": None,
            "children": children,
            "state": "collapsed",
        }
    )
    my_tree = adr_service_create.create_item(obj_name="testtree", source="testing")
    my_tree.item_tree = tree
    assert my_tree.type == "tree"


def test_change_type(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|html"
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = join(join(request.fspath.dirname, "test_data"), "aa_00_0_alpha1.png")
    my_img.item_text = "This is not supposed to work"
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_img_items) == len(img_items)


def test_vis_item(adr_service_query) -> None:
    success = False
    try:
        one_item = adr_service_query.query(query_type="Item")
        one_item[0].visualize()
        one_item[0].visualize(new_tab=True)
        success = True
    except SyntaxError:
        success = False
    assert success is True


def test_iframe_item(adr_service_query) -> None:
    success = False
    try:
        filter_str = "A|i_type|cont|table"
        one_item = adr_service_query.query(query_type="Item", filter=filter_str)
        _ = one_item[0].get_iframe()
        success = True
    except SyntaxError:
        success = False
    assert success is True


def test_iframe_on_img_item(adr_service_query) -> None:
    success = False
    try:
        filter_str = "A|i_type|cont|image"
        one_item = adr_service_query.query(query_type="Item", filter=filter_str)
        _ = one_item[0].get_iframe()
        success = True
    except SyntaxError:
        success = False
    assert success is True


@pytest.mark.ado_test
def test_get_url(adr_service_query) -> None:
    filter_str = "A|i_type|cont|table"
    one_item = adr_service_query.query(query_type="Item", filter=filter_str)
    url = one_item[0].url
    assert (url is not None) and ("http" in url)


@pytest.mark.ado_test
def test_create_table(adr_service_create) -> None:
    filter_str = "A|i_type|cont|table"
    table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_table = adr_service_create.create_item()
    my_table.item_table = np.array([[1, 2, 3, 4, 5, 6], [1, 4, 9, 16, 25, 36]], dtype="|S20")
    my_table.format = "floatdot3"
    my_table.format_column = "str"
    my_table.labels_column = ["colA", "ColB", "col3", "Column4", "CFive", "c6"]
    my_table.format_row = "str"
    my_table.labels_row = ["Row1", "row_number_two"]
    my_table.plot = "line"
    my_table.title = "This is a test"
    my_table.line_color = "red"
    my_table.line_marker = "circle"
    my_table.line_marker_text = "Position: ({{v/x}},{{v/y}})"
    my_table.line_marker_size = 30
    my_table.line_marker_opacity = 0.8
    my_table.line_marker_scale = [1.0, 0]
    my_table.line_error_bars = 0.3
    my_table.line_style = "dot"
    my_table.line_width = 12
    my_table.stacked = 0
    my_table.xaxis = 0
    my_table.yaxis = [0, 1, 2, 3, 4, 5, 6]
    my_table.palette = "Greens"
    my_table.palette_position = [1.2, 5]
    my_table.palette_range = [0, 40]
    my_table.palette_show = 1
    my_table.palette_title = "Green palette"
    my_table.width = 600
    my_table.height = 100
    my_table.show_legend = 1
    my_table.legend_position = [0.9, 5]
    my_table.show_legend_border = 1
    my_table.show_border = 1
    my_table.plot_margins = [5, 10, 5, 2]
    my_table.plot_title = "Test Plot Title"
    my_table.plot_xaxis_type = "linear"
    my_table.plot_yaxis_type = "linear"
    my_table.xrange = [0, 7]
    my_table.yrange = [0, 40]
    my_table.xaxis_format = "floatdot4"
    my_table.yaxis_format = "floatdot1"
    my_table.xtitle = "X axis test"
    my_table.ytitle = "Test Y axis"
    my_table.item_justification = "left"
    my_table.nan_display = "NaN"
    my_table.table_sort = "none"
    my_table.table_title = "Test Table title"
    my_table.align_column = ["left", "right", "center"]
    my_table.table_search = 1
    my_table.table_page = 0
    my_table.table_pagemenu = [10, 25, 50, 100, -1]
    my_table.table_scrollx = 1
    my_table.table_scrolly = 1
    my_table.table_bordered = 1
    my_table.table_condensed = 0
    my_table.table_wrap_content = 0
    my_table.table_default_col_labels = 1
    my_table.table_cond_format = ""
    my_table.row_tags = ["dp=0", "dp=2"]
    my_table.col_tags = ["a", "b", "c", "d", "e", "f"]
    new_table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_table_items) == (len(table_items) + 1)


@pytest.mark.ado_test
def test_create_histo(adr_service_create) -> None:
    filter_str = "A|i_type|cont|table"
    table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_table = adr_service_create.create_item()
    my_table.item_table = np.random.normal(0, 0.1, 100)
    my_table.plot = "histogram"
    my_table.histogram_cumulative = 1
    my_table.histogram_normalized = 1
    my_table.histogram_bin_size = 0.5
    new_table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_table_items) == (len(table_items) + 1)


@pytest.mark.ado_test
def test_create_3d_scatter(adr_service_create) -> None:
    filter_str = "A|i_type|cont|table"
    table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_table = adr_service_create.create_item()
    my_table.item_table = np.random.uniform(1.0, 50.0, size=(6, 20))
    my_table.labels_row = ["X1", "Y1", "Z1", "X2", "Y2", "Z2"]
    my_table.plot = "line"
    my_table.line_style = "none"
    my_table.line_marker = "diamond"
    my_table.xaxis = ["X1", "X2"]
    my_table.yaxis = ["Y1", "Y2"]
    my_table.zaxis = ["Z1", "Z2"]
    my_table.zaxis_format = "floatdot0"
    my_table.yaxis_format = "floatdot0"
    my_table.xaxis_format = "floatdot1"
    my_table.xtitle = "x"
    my_table.ytitle = "f(x)"
    my_table.ztitle = "f(x,y)"
    my_table.line_marker_opacity = 0.7
    new_table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_table_items) == (len(table_items) + 1)


@pytest.mark.ado_test
def test_create_3d_surface(adr_service_create) -> None:
    filter_str = "A|i_type|cont|table"
    table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_table = adr_service_create.create_item()
    my_table.item_table = np.array(
        [
            [0.00291, 0.01306, 0.02153, 0.01306, 0.00291],
            [0.01306, 0.05854, 0.09653, 0.05854, 0.01306],
            [0.02153, 0.09653, np.nan, 0.09653, 0.02153],
            [0.01306, 0.05854, 0.09653, 0.05854, 0.01306],
            [0.00291, 0.01306, 0.02153, 0.01306, 0.00291],
        ],
        dtype="|S20",
    )
    my_table.plot = "3d surface"
    my_table.format = "floatdot0"
    new_table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_table_items) == (len(table_items) + 1)


@pytest.mark.ado_test
def test_create_polar_plot(adr_service_create) -> bool:
    filter_str = "A|i_type|cont|table"
    table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_table = adr_service_create.create_item()
    my_table.item_table = np.array(
        [
            [-180, -135, -90, -45, 0, 45, 90, 135, 180],
            [8.2, 7.3, 10.6, 5.6, 5.9, 9.1, 2.4, 1.6, 4.8],
        ],
        dtype="|S20",
    )
    my_table.xaxis = 0
    my_table.plot = "polar"
    my_table.format = "floatdot0"
    new_table_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_table_items) == (len(table_items) + 1)


def test_set_tags(adr_service_query) -> None:
    success = False
    try:
        one_item = adr_service_query.query(query_type="Item", filter="A|i_name|cont|testtable")
        success = one_item[0].set_tags(tagstring="firsttag=one")
    except SyntaxError:
        success = False
    assert success is True


def test_get_tags(adr_service_query) -> None:
    success = False
    try:
        one_item = adr_service_query.query(query_type="Item", filter="A|i_name|cont|testone")
        tags = one_item[0].get_tags()
        success = True
    except SyntaxError:
        success = False
    assert success is True and len(tags) == 36


@pytest.mark.ado_test
def test_add_tag(adr_service_query) -> None:
    success = False
    try:
        one_item = adr_service_query.query(query_type="Item", filter="A|i_name|cont|img_two")
        success = one_item[0].add_tag(tag="Tag", value="one")
    except SyntaxError:
        success = False
    assert success is True


def test_rem_tag(adr_service_query) -> None:
    success = False
    try:
        one_item = adr_service_query.query(query_type="Item", filter="A|i_name|cont|testone")
        success = one_item[0].rem_tag(tag="tagtodelete")
    except SyntaxError:
        success = False
    assert success is True


def test_unit_item(request) -> None:
    valid = False
    try:
        _ = Item()
    except AttributeError:
        valid = True
    assert valid


def test_unit_item_empty_nexus(request) -> None:
    valid = False
    a = Service()
    try:
        _ = Item(service=a)
    except Exception:
        valid = True
    assert valid
