import datetime
import json
import uuid

import pytest

from ansys.dynamicreporting.core.utils import report_objects as ro


@pytest.mark.ado_test
def test_convert_color() -> bool:
    assert ro.convert_color([1, 2, 3]) == "#ff1fe2fd"


@pytest.mark.ado_test
def test_convert_syle() -> bool:
    one = ro.convert_style(1, 0) == "none"
    two = ro.convert_style(1, 1) == "dot"
    three = ro.convert_style(3, 1) == "dash"
    assert one and two and three


@pytest.mark.ado_test
def test_convert_marker() -> bool:
    one = ro.convert_marker(1) == "circle"
    two = ro.convert_marker(2) == "circle-open"
    three = ro.convert_marker(3) == "triangle-open"
    four = ro.convert_marker(4) == "square-open"
    five = ro.convert_marker(5) == "none"
    assert one and two and three and four and five


@pytest.mark.ado_test
def test_convert_label_format() -> bool:
    one = ro.convert_label_format("aaaf") == "floatdota"
    two = ro.convert_label_format("aaa") == "scientific"
    three = ro.convert_label_format("g") == "sigfigs4"
    assert one and two and three


@pytest.mark.ado_test
def test_title_units() -> bool:
    assert ro.get_title_units("a", "v") == "a"


@pytest.mark.ado_test
class e_query:
    def __init__(self, norx=False, nory=False):
        self.QUERY_DATA = {
            "description": "plastic vs. Time for Node 440",
            "xaxis description": "Time",
            "yaxis description": "plastic",
            "segments": [21],
            "xydata": [[0.0, 0.0], [1, 3]],
            "nodes": [440, 440],
        }
        self.NORMALIZEX = norx
        self.NORMALIZEY = nory
        self.SCALE = [1, 1]
        self.OFFSET = [0, 0]
        self.LEGENDTITLE = "legend title"
        self.LINEWIDTH = 3
        self.LINESTYLE = "line"
        self.LINETYPE = "line"
        self.MARKER = "dot"
        self.MARKERSCALE = 1
        self.RGB = [1.0, 0.0, 0.0]


@pytest.mark.ado_test
class e_plotter:
    def __init__(self):
        self.QUERIES = [e_query(), e_query(norx=True, nory=True)]
        self.AXISXTITLE = "x axis"
        self.VAR_XAXIS_OBJ = "X"
        self.AXISYTITLE = "Y axis"
        self.VAR_YAXIS_LEFT_OBJ = "Y"
        self.PLOTTITLE = "Plot title"
        self.AXISXSCALE = "log"
        self.AXISYSCALE = "log"
        self.AXISXAUTOSCALE = True
        self.AXISXMIN = 0
        self.AXISXMAX = 1
        self.AXISYAUTOSCALE = False
        self.AXISYMIN = 0
        self.AXISYMAX = 1
        self.AXISYLABELFORMAT = "%g"
        self.AXISXLABELFORMAT = "%g"


@pytest.mark.ado_test
def test_extract_data_query() -> bool:
    a = e_query()
    assert (ro.extract_data_from_ensight_query(a) == [[0, 1], [0, 3]]).all()


@pytest.mark.ado_test
def test_extract_data_query_norm() -> bool:
    a = e_query(norx=True, nory=True)
    assert (ro.extract_data_from_ensight_query(a) == [[0, 1], [0, 1]]).all()


@pytest.mark.ado_test
def test_extract_data_plotter() -> bool:
    a = e_plotter()
    assert isinstance(ro.map_ensight_plot_to_table_dictionary(a), dict)


@pytest.mark.ado_test
def test_split_quoted() -> bool:
    assert ro.split_quoted_string_list(s="aa,aa", deliminator=",") == ["aa", "aa"]


@pytest.mark.ado_test
def test_query_parse() -> bool:
    one = ro.parse_filter(query="A|i_name|eq|test;")
    two = ro.parse_filter(query=b"A|i_name|eq|test;")
    assert len(one) == len(two) == 1


@pytest.mark.ado_test
def test_template() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    a.paste_reset()
    a.reset_defaults()
    mydict = {"a": 2}
    a.set_params(d=mydict)
    params = a.get_params()
    assert params == mydict


@pytest.mark.ado_test
def test_template_types() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    one = a.report_type
    a.change_type(t="Layout:header")
    assert one == "Layout:basic"


@pytest.mark.ado_test
def test_template_dirty() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    _ = a.from_json(json_dict={"a": 3})
    a.set_dirty(d=True)
    assert a.get_dirty()


@pytest.mark.ado_test
def test_template_date() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    assert type(a.get_date_object()) is datetime.datetime


@pytest.mark.ado_test
def test_template_get() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    assert len(a.get_url_data()) == 2 and a.get_url_file() is None


@pytest.mark.ado_test
def test_tempalte_child() -> bool:
    a = ro.Template(initial_data={"a": 1}, mar="test")
    b = ro.Template()
    a.add_template_object(b)
    assert a.get_child_objects() == []


@pytest.mark.ado_test
def test_baserest() -> bool:
    a = ro.BaseRESTObject()
    a.generate_new_guid()
    foo = a.get_url_base_name()
    a.update_api_version(new_api_version=1)
    mystr = "abc"

    assert (
        a.saved is False
        and (len(a.get_json_keys()) == 2)
        and foo == "foo"
        and (a.add_quotes(s=mystr) == mystr)
    )


@pytest.mark.ado_test
def test_itemcategory() -> bool:
    a = ro.ItemCategoryREST()
    item = a.get_url_base_name()
    assert (
        a.perms_and_groups == {}
        and item == "item-categories"
        and a.get_list_url() in a.get_detail_url()
    )


@pytest.mark.ado_test
def test_itemcategory_dict() -> bool:
    a = ro.ItemCategoryREST()
    mydict = a.get_json_key_limits()
    assert mydict == {"name": 80}


@pytest.mark.ado_test
def test_itemcategory_url() -> bool:
    a = ro.ItemCategoryREST()
    success = False
    try:
        a.get_url_data()
    except ValueError:
        success = True
    assert success


@pytest.mark.ado_test
def test_category() -> bool:
    a = ro.ItemREST()
    one = a._validate_and_get_category(category="test")
    two = a._validate_and_get_category(category=ro.ItemCategoryREST())
    a.add_category(category=ro.ItemCategoryREST())
    a.remove_category(category=ro.ItemCategoryREST())
    a.update_api_version(new_api_version=2)
    a.get_payload_content()
    a.get_payload_content(as_list=True)
    a.set_payload_none()
    a.set_payload_string(s="aa")
    a.validate_tree_value(["a", "b"])
    succ = False
    try:
        a.validate_tree(t=0)
    except ValueError as e:
        succ = "must be a list" in str(e)
    succ_two = False
    try:
        a.validate_tree(t=[0])
    except ValueError as e:
        succ_two = "must be a list of dictionaries" in str(e)
    succ_a = succ and succ_two
    assert one == "test" and two == "" and a.is_file_protocol() is False and succ_a


@pytest.mark.ado_test
def test_factory() -> bool:
    a = ro.TemplateREST()
    assert isinstance(
        a.factory(json_data={"report_type": "templ:Layout"}), ro.LayoutREST
    ) and isinstance(a.factory(json_data={}), ro.TemplateREST)


@pytest.mark.ado_test
def test_templaterest() -> bool:
    a = ro.TemplateREST()
    a.reorder_children()
    _ = a.get_json_keys()
    _ = a.get_json_key_limits()
    assert len(a.get_url_data()) == 2


@pytest.mark.ado_test
def test_templaterest_params() -> bool:
    a = ro.TemplateREST()
    a.add_params()
    succ = False
    try:
        a.add_params(d=0)
    except ValueError as e:
        succ = "input must be a dictionary" in str(e)
    succ_two = False
    try:
        a.set_params(d=0)
    except ValueError as e:
        succ_two = "input must be a dictionary" in str(e)
    a.set_params(d={"b": 2})
    a.add_params(d={"a": 1})
    assert a.get_params() == {"b": 2, "a": 1} and succ and succ_two


@pytest.mark.ado_test
def test_templaterest_sort() -> bool:
    a = ro.TemplateREST()
    succ = a.get_sort_fields() == []
    a.add_params(d={"sort_fields": [1, 2, 3]})
    a.set_property()
    succ_three = False
    try:
        a.set_params(d=0)
    except ValueError as e:
        succ_three = "input must be a dictionary" in str(e)
    a.set_property(property={"a": 1})
    a.add_property(property={"b": 2})
    succ_four = a.get_sort_fields() == [1, 2, 3]
    succ_five = a.get_property() == {"a": 1, "b": 2}
    assert succ and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_templaterest_fields() -> bool:
    a = ro.TemplateREST()
    succ_three = a.get_sort_selection() == ""
    succ = False
    try:
        a.set_sort_fields(sort_field=0)
    except ValueError as e:
        succ = "sorting filter is not a list" in str(e)
    a.set_sort_fields(sort_field=["a", "c", "b"])
    a.add_sort_fields(sort_field=["e"])
    succ_two = False
    try:
        a.add_sort_fields(sort_field=0)
    except ValueError as e:
        succ_two = "sorting filter is not a list" in str(e)
    succ_four = False
    try:
        a.set_sort_selection(value=0)
    except ValueError as e:
        succ_four = "sort selection input should be a string" in str(e)
    succ_five = False
    try:
        a.set_sort_selection(value="abc")
    except ValueError as e:
        succ_five = "not among the acceptable inputs" in str(e)
    a.set_sort_selection()
    succ_a = a.get_sort_selection() == "all" and succ and succ_two and succ_three
    assert succ_a and succ_four and succ_five


@pytest.mark.ado_test
def test_templaterest_filter() -> bool:
    a = ro.TemplateREST()
    strone = "firstfilter"
    strtwo = "myfilter"
    succ_three = a.get_filter_mode() == "items"
    succ = False
    try:
        a.set_filter(filter_str=0)
    except ValueError as e:
        succ = "filter value should be a string" in str(e)
    a.set_filter(filter_str=strone)
    succ_two = False
    try:
        a.add_filter(filter_str=0)
    except ValueError as e:
        succ_two = "filter value should be a string" in str(e)
    a.add_filter(filter_str=strtwo)
    a.set_filter_mode()
    succ_four = False
    try:
        a.set_filter_mode(value=0)
    except ValueError as e:
        succ_four = "filter mode input should be a string" in str(e)
    succ_five = False
    try:
        a.set_filter_mode(value="abc")
    except ValueError as e:
        succ_five = "filter mode not among the" in str(e)
    succ_a = (
        a.get_filter() == strone + strtwo and a.get_html() == "" and a.get_filter_mode() == "items"
    )
    assert succ_a and succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_layout_col() -> bool:
    a = ro.LayoutREST()
    one = a.get_column_count()
    success = False
    try:
        a.set_column_count(value="aa")
    except ValueError as e:
        success = "input should be an integer" in str(e)
    success_two = False
    try:
        a.set_column_count(value=-1)
    except ValueError as e:
        success_two = "input should be larger than" in str(e)
    a.set_column_count(value=3)
    assert one == 1 and success and success_two


@pytest.mark.ado_test
def test_layout_col_width() -> bool:
    a = ro.LayoutREST()
    one = a.get_column_widths()
    success = False
    try:
        a.set_column_widths(value=3)
    except ValueError as e:
        success = "input should be a list" in str(e)
    a.set_column_widths(value=[1, 2])
    assert one == [1.0] and success and a.get_column_widths() == [1, 2]


@pytest.mark.ado_test
def test_layout_html() -> bool:
    a = ro.LayoutREST()
    a.set_html(value="onetwo")
    success = False
    try:
        a.set_html(value=4)
    except ValueError as e:
        success = "input needs to be a string" in str(e)
    assert success


@pytest.mark.ado_test
def test_set_comments() -> None:
    a = ro.LayoutREST()
    a.set_comments(value="lololol")
    success = False
    try:
        a.set_comments(value=4)
    except ValueError as e:
        success = "input needs to be a string" in str(e)
    assert success


@pytest.mark.ado_test
def test_layout_transport() -> bool:
    a = ro.LayoutREST()
    zero = a.get_transpose()
    success = False
    try:
        a.set_transpose(value=3)
    except ValueError:
        success = True
    successtwo = False
    try:
        a.set_transpose(value=0.2)
    except ValueError:
        successtwo = True
    a.set_transpose(value=1)
    a.set_html(value="aa")
    res = a.get_transpose()
    assert 0 == zero and success and successtwo and res == "aa"


@pytest.mark.ado_test
def test_layout_skip() -> bool:
    a = ro.LayoutREST()
    zero = a.get_skip()
    success = False
    try:
        a.set_skip(value=1.2)
    except ValueError as e:
        success = "input needs to be an integer" in str(e)
    successtwo = False
    try:
        a.set_skip(value=4)
    except ValueError as e:
        successtwo = "needs to be either" in str(e)
    a.set_skip(value=1)
    one = a.get_skip()
    assert zero == 0 and success and successtwo and one == 1


@pytest.mark.ado_test
def test_gen() -> bool:
    a = ro.GeneratorREST()
    add = a.get_generated_items() == "add"
    success = False
    try:
        a.set_generated_items(value=1)
    except ValueError as e:
        success = "items should be a string" in str(e)
    successtwo = False
    try:
        a.set_generated_items(value="no")
    except ValueError as e:
        successtwo = "input should be add" in str(e)
    a.set_generated_items(value="add")
    addtwo = a.get_generated_items() == "add"
    assert add and success and successtwo and addtwo


@pytest.mark.ado_test
def test_gen_tags() -> bool:
    a = ro.GeneratorREST()
    one = a.get_append_tags()
    success = False
    try:
        a.set_append_tags(value=1)
    except ValueError as e:
        success = "value should be True" in str(e)
    a.set_append_tags(value=True)
    assert one and success


@pytest.mark.ado_test
def test_basic() -> bool:
    _ = ro.basicREST()
    assert True


@pytest.mark.ado_test
def test_panel() -> bool:
    a = ro.panelREST()
    one = a.get_panel_style() == ""
    success = False
    try:
        a.set_panel_style(value="aa")
    except ValueError as e:
        success = "panel style mode not among" in str(e)
    a.set_panel_style(value="panel")
    two = a.get_panel_style() == "panel"
    assert one and success and two


@pytest.mark.ado_test
def test_panel_link() -> bool:
    a = ro.panelREST()
    one = a.get_items_as_link() == 0
    success = False
    try:
        a.set_items_as_link(value=1.2)
    except ValueError as e:
        success = "should be an integer" in str(e)
    successtwo = False
    try:
        a.set_items_as_link(value=5)
    except ValueError as e:
        successtwo = "not among the acceptable values" in str(e)
    a.set_items_as_link(value=1)
    two = a.get_items_as_link() == 1
    assert one and success and successtwo and two


@pytest.mark.ado_test
def test_box() -> bool:
    a = ro.boxREST()
    one = a.get_children_layout() == {}
    success = False
    try:
        a.set_child_position(value=1)
    except ValueError as e:
        success = "hild position should be a list" in str(e)
    successtwo = False
    try:
        a.set_child_position()
    except ValueError as e:
        successtwo = "is not a valid guid" in str(e)
    successthree = False
    try:
        a.set_child_position(value=[1])
    except ValueError as e:
        successthree = "position should contain 4 values" in str(e)
    successfour = False
    try:
        a.set_child_position(value=[1, 1, 1, 0.3])
    except ValueError as e:
        successfour = "array should contain only integers" in str(e)
    a.set_child_position(value=[1, 1, 1, 1], guid=str(uuid.uuid1()))
    success_seven = type(a.get_children_layout()) is dict
    successfive = False
    try:
        a.set_child_clip(clip=0)
    except ValueError as e:
        successfive = "should be a string" in str(e)
    successsix = False
    try:
        a.set_child_clip(clip="a")
    except ValueError as e:
        successsix = "not among the accepted values" in str(e)
    a.set_child_clip(guid=str(uuid.uuid1()))
    succ_a = success and successtwo and successthree
    succ_b = successfour and successfive and successsix and success_seven
    assert one and succ_a and succ_b


@pytest.mark.ado_test
def test_tabs() -> bool:
    _ = ro.tabsREST()
    assert True


@pytest.mark.ado_test
def test_carosel() -> bool:
    a = ro.carouselREST()
    one = a.get_animated() == 0
    success = False
    try:
        a.set_animated(value=1.2)
    except ValueError as e:
        success = "Should be an integer" in str(e)
    a.set_animated(value=1)
    two = a.get_animated() == 1
    assert one and success and two


@pytest.mark.ado_test
def test_carosel_dot() -> bool:
    a = ro.carouselREST()
    one = a.get_slide_dots() == 20
    success = False
    try:
        a.set_slide_dots(value=3.2)
    except ValueError as e:
        success = "Should be an integer" in str(e)
    a.set_slide_dots(value=2)
    two = a.get_slide_dots() == 2
    assert one and success and two


@pytest.mark.ado_test
def test_slider() -> bool:
    a = ro.sliderREST()
    succ = a.get_map_to_slider() == []
    a.set_map_to_slider()
    succ_two = False
    try:
        a.set_map_to_slider(value=1)
    except ValueError as e:
        succ_two = "Should be a list" in str(e)
    succ_three = False
    try:
        a.set_map_to_slider(value=["aa"])
    except IndexError as e:
        succ_three = "list index out of range" in str(e)
    a.set_map_to_slider(value=["none|text_up"])
    succ_four = False
    try:
        a.add_map_to_slider(value=3)
    except ValueError as e:
        succ_four = "Should be a list" in str(e)
    a.add_map_to_slider(value=["none|text_up"])
    succ_five = a.get_map_to_slider() == ["none|text_up", "none|text_up"]
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_foot_head() -> bool:
    _ = ro.footerREST()
    _ = ro.headerREST()
    _ = ro.tagpropsREST()
    assert True


@pytest.mark.ado_test
def test_iterator() -> bool:
    a = ro.iteratorREST()
    succ = a.get_iteration_tags() == ["", ""]
    a.set_iteration_tags()
    succ_two = False
    try:
        a.set_iteration_tags(value=1)
    except ValueError as e:
        succ_two = "Error: input needs to be a list" in str(e)
    succ_three = False
    try:
        a.set_iteration_tags(value=[])
    except ValueError as e:
        succ_three = "needs to contain 2 elements" in str(e)
    succ_four = False
    try:
        a.set_iteration_tags(value=[1, 1])
    except ValueError as e:
        succ_four = "need to be strings" in str(e)
    a.set_iteration_tags(value=["tag", "a"])
    succ_five = a.get_iteration_tags() == ["tag", "a"]
    a.set_iteration_tags(value=["", ""])
    succ_six = a.get_iteration_tags() == ["", ""]
    a.set_iteration_tags(value=["tag", "a"])
    succ_seven = a.get_sort_tag() == [True, False]
    a.set_iteration_tags(value=["sort", "reverse_sort"])
    succ_eight = a.get_sort_tag() == [True, False]
    a.set_sort_tag()
    succ_nine = False
    try:
        a.set_sort_tag(value=1)
    except ValueError as e:
        succ_nine = "input needs to be a list" in str(e)
    succ_ten = False
    try:
        a.set_sort_tag(value=[1])
    except ValueError as e:
        succ_ten = "contain 2 elements" in str(e)
    succ_eleven = False
    try:
        a.set_sort_tag(value=[1, 1])
    except ValueError as e:
        succ_eleven = "need to be True/False" in str(e)
    a.set_sort_tag(value=[False, True])
    succ_twelve = a.get_sort_tag() == [False, False]
    succ_a = succ and succ_two + succ_three + succ_four + succ_five
    succ_b = succ_six + succ_seven + succ_eight + succ_nine
    succ_c = succ_ten + succ_eleven + succ_twelve
    assert succ_a and succ_b and succ_c


@pytest.mark.ado_test
def test_toc() -> bool:
    a = ro.tocREST()
    succ = a.get_toc() is None
    succ_two = False
    try:
        a.set_toc(option="a")
    except ValueError as e:
        succ_two = "needs to be one of the accepted values" in str(e)
    a.set_toc(option="figure")
    succ_three = a.get_toc() == "figure"
    a.set_toc(option="toc")
    succ_four = a.get_toc() == "toc"
    a.set_toc(option="table")
    succ_five = a.get_toc() == "table"
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_link() -> bool:
    a = ro.reportlinkREST()
    a.get_report_link()
    a.set_report_link()
    a.set_report_link(link=str(uuid.uuid1()))
    succ = type(a.get_report_link()) is str
    succ_two = False
    try:
        a.set_report_link(link="aa")
    except ValueError as e:
        succ_two = "input guid is not" in str(e)
    assert succ and succ_two


@pytest.mark.ado_test
def test_table_merge() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_merging_param() == "row"
    succ_two = False
    try:
        a.set_merging_param(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    succ_three = False
    try:
        a.set_merging_param(value="a")
    except ValueError as e:
        succ_three = "input should be either row or column" in str(e)
    a.set_merging_param(value="column")
    succ_four = a.get_merging_param() == "column"
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablemerge_title() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_table_name() == ""
    succ_two = False
    try:
        a.set_table_name(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_table_name(value="a")
    succ_three = a.get_table_name() == "a"
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_tablemerge_source() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_sources() == ["*|duplicate"]
    a.set_sources()
    succ_two = False
    try:
        a.set_sources(value=["a|b"])
    except ValueError as e:
        succ_two = "input does not contain one of the acceptable conditions" in str(e)
    succ_three = False
    try:
        a.set_sources(value=0)
    except ValueError as e:
        succ_three = "input should be a list" in str(e)
    a.set_sources(value=["merge|rename_tag"])
    a.add_sources()
    succ_four = False
    try:
        a.add_sources(value=0)
    except ValueError as e:
        succ_four = "input should be a list" in str(e)
    succ_five = False
    try:
        a.add_sources(value=["a|b"])
    except ValueError as e:
        succ_five = "input does not contain one of the acceptable conditions" in str(e)
    a.add_sources(value=["|merge"])
    succ_six = a.get_sources() == ["merge|rename_tag", "", "|merge"]
    succ_a = succ and succ_two and succ_three
    succ_b = succ_four and succ_five and succ_six
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablemerge_tag() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_rename_tag() == ""
    succ_two = True
    try:
        a.set_rename_tag(value=0)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_rename_tag(value="")
    a.set_rename_tag(value="a")
    succ_three = a.get_rename_tag() == "a"
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_tablemerge_labels() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_use_labels() == 1
    succ_two = False
    try:
        a.set_use_labels(value="a")
    except ValueError as e:
        succ_two = "input should be an integer" in str(e)
    succ_three = False
    try:
        a.set_use_labels(value=3)
    except ValueError as e:
        succ_three = "the input should be 0/1" in str(e)
    a.set_use_labels(value=0)
    succ_four = a.get_use_labels() == 0
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablemerge_setids() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_use_ids() == ""
    a.params = '{"merge_params": {"column_labels_as_ids": 1}}'
    succ_two = a.get_use_ids() == ""
    a.params = '{"merge_params": {"column_id_row": "column"}}'
    succ_three = a.get_use_ids() == "column"
    succ_four = False
    try:
        a.set_use_ids(value=0)
    except ValueError as e:
        succ_four = "input should be a string" in str(e)
    a.params = "{}"
    succ_five = False
    try:
        a.set_use_ids(value="a")
    except KeyError:
        succ_five = True
    a.params = '{"merge_params": {"column_labels_as_ids": 1, "merge_type":"column", "column_id_row": "column"}}'
    succ_six = False
    try:
        a.set_use_ids(value="a")
    except ValueError as e:
        succ_six = "can not set the Column" in str(e)
    a.params = '{"merge_params": {"column_labels_as_ids": 1, "merge_type":"row", "column_id_row": "column"}}'
    succ_seven = False
    try:
        a.set_use_ids(value="a")
    except ValueError as e:
        succ_seven = "can not set the Row" in str(e)
    a.params = '{"merge_params": {"column_labels_as_ids": 0, "merge_type":"row", "column_id_row": "column"}}'
    a.set_use_ids(value="a")
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablemerge_ids_one() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_id_selection() == "all"
    succ_two = False
    try:
        a.set_id_selection(value=0)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    succ_three = False
    try:
        a.set_id_selection(value="a")
    except ValueError as e:
        succ_three = "input should be one of all / intersect / select" in str(e)
    a.set_id_selection(value="select")
    succ_four = a.get_id_selection() == "select"
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablemerge_ids() -> bool:
    a = ro.tablemergeREST()
    a.params = json.dumps({"merge_params": {"merge_type": "0", "column_merge": "all"}})
    a.set_ids()
    a.params = json.dumps({"merge_params": {"merge_type": "row", "column_merge": "all"}})
    succ_eight = False
    try:
        a.set_ids()
    except ValueError as e:
        succ_eight = "not set column IDs if the Column" in str(e)
    a.params = json.dumps({"merge_params": {"merge_type": "column", "column_merge": "all"}})
    succ_nine = False
    try:
        a.set_ids()
    except ValueError as e:
        succ_nine = "can not set row IDs if the Row ID" in str(e)
    a.params = json.dumps({"merge_params": {"merge_type": "0", "column_merge": "all"}})
    succ = False
    try:
        a.set_ids(value=0)
    except ValueError as e:
        succ = "input should be a list" in str(e)
    succ_two = False
    try:
        a.set_ids(value=["a"])
    except ValueError as e:
        succ_two = "input should be a list of integers only" in str(e)
    a.set_ids(value=[0, 1])
    succ_three = a.get_ids() == []
    a.params = '{"merge_params": {"merge_type": "row", "column_merge": "all", "selected_column_ids": "0, 1, "}}'
    _ = a.get_ids()
    succ_four = False
    try:
        a.add_ids()
    except ValueError as e:
        succ_four = "not add column IDs if the Column ID" in str(e)
    a.params = '{"merge_params": {"merge_type": "column", "column_merge": "all", "selected_column_ids": "0, 1, "}}'
    succ_five = False
    try:
        a.add_ids()
    except ValueError as e:
        succ_five = "not add row IDs if the Row ID" in str(e)
    a.params = '{"merge_params": {"merge_type": "0", "column_merge": "all", "selected_column_ids": "0, 1, "}}'
    succ_six = False
    try:
        a.add_ids(value=0)
    except ValueError as e:
        succ_six = "input should be a list" in str(e)
    succ_seven = False
    try:
        a.add_ids(value=["1"])
    except ValueError as e:
        succ_seven = "input should be a list of integers only" in str(e)
    succ_a = succ and succ_two and succ_three and succ_four and succ_five
    succ_b = succ_six and succ_seven and succ_eight and succ_nine
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablemerge_unknown() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_unknown_value() == "nan"
    succ_two = False
    try:
        a.set_unknown_value(value=0)
    except ValueError as e:
        succ_two = "unknown value should be a string" in str(e)
    a.set_unknown_value(value="0")
    succ_three = a.get_unknown_value() == "0"
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_tablemerge_transp() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_table_transpose() == 0
    succ_two = False
    try:
        a.set_table_transpose(value="1")
    except ValueError as e:
        succ_two = "transpose input should be integer" in str(e)
    succ_three = False
    try:
        a.set_table_transpose(value=3)
    except ValueError as e:
        succ_three = "value should be 0 or 1" in str(e)
    a.set_table_transpose(value=1)
    succ_four = a.get_table_transpose() == 1
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablemerge_numeric() -> bool:
    a = ro.tablemergeREST()
    succ = a.get_numeric_output() == 0
    succ_two = False
    try:
        a.set_numeric_output(value="1")
    except ValueError as e:
        succ_two = "the numeric output should be integer" in str(e)
    succ_three = False
    try:
        a.set_numeric_output(value=5)
    except ValueError as e:
        succ_three = "input value should be 0 or 1" in str(e)
    a.set_numeric_output(value=1)
    succ_four = a.get_numeric_output() == 1
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablemerge_nameparam() -> bool:
    a = ro.tablereduceREST()
    succ = a.get_reduce_param() == "row"
    succ_two = False
    try:
        a.set_reduce_param(value=0)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    succ_three = False
    try:
        a.set_reduce_param(value="a")
    except ValueError as e:
        succ_three = "input should be either row or column" in str(e)
    a.set_reduce_param(value="column")
    succ_four = a.get_reduce_param() == "column"
    succ_five = a.get_table_name() == ""
    succ_six = False
    try:
        a.set_table_name(value=1)
    except ValueError as e:
        succ_six = "input should be a string" in str(e)
    a.set_table_name(value="abc")
    succ_seven = a.get_table_name() == "abc"
    succ_a = succ and succ_two and succ_three and succ_four
    assert succ_a and succ_five and succ_six and succ_seven


@pytest.mark.ado_test
def test_tablemerge_operation() -> bool:
    a = ro.tablereduceREST()
    succ = a.get_operations() == []
    a.add_operation()
    succ_two = False
    try:
        a.add_operation(name="a")
    except ValueError as e:
        succ_two = "should be a list of strings" in str(e)
    succ_three = False
    try:
        a.add_operation(name=[1])
    except ValueError as e:
        succ_three = "should all be strings" in str(e)
    succ_four = False
    try:
        a.add_operation(unique="a")
    except ValueError as e:
        succ_four = "input should be True/False" in str(e)
    succ_five = False
    try:
        a.add_operation(output_name=1)
    except ValueError as e:
        succ_five = "output_name should be a string" in str(e)
    succ_six = False
    try:
        a.add_operation(existing=1)
    except ValueError as e:
        succ_six = "existing should be True/False" in str(e)
    succ_seven = False
    try:
        a.add_operation(select_names=1)
    except ValueError as e:
        succ_seven = "select_names should be a string" in str(e)
    succ_eight = False
    try:
        a.add_operation(operation=1)
    except ValueError as e:
        succ_eight = "operation should be a string" in str(e)
    succ_nine = False
    try:
        a.add_operation(operation="a")
    except ValueError as e:
        succ_nine = "operation not among the acceptable values" in str(e)
    a.add_operation(name=["a"])
    a.add_operation(name=["b"], existing=False)
    succ_ten = len(a.get_operations()) == 3
    a.delete_operation()
    succ_eleven = False
    try:
        a.delete_operation(name="a")
    except ValueError as e:
        succ_eleven = "need to pass the operation" in str(e)
    a.delete_operation(name=["a", "b"])
    succ_a = succ and succ_two and succ_three and succ_four and succ_five and succ_six
    succ_b = succ_seven and succ_eight and succ_nine and succ_ten and succ_eleven
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablemerge_transpose() -> bool:
    a = ro.tablereduceREST()
    succ = a.get_table_transpose() == 0
    succ_two = False
    try:
        a.set_table_transpose(value="a")
    except ValueError as e:
        succ_two = "the transpose input should be integer" in str(e)
    succ_three = False
    try:
        a.set_table_transpose(value=3)
    except ValueError as e:
        succ_three = "input value should be 0 or 1" in str(e)
    succ_four = False
    try:
        a.set_table_transpose(value=1.2)
    except ValueError as e:
        succ_four = "transpose input should be integer" in str(e)
    a.set_table_transpose(value=1)
    succ_five = a.get_table_transpose() == 1
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_tablereduce_numeric() -> bool:
    a = ro.tablereduceREST()
    succ = a.get_numeric_output() == 0
    succ_two = False
    try:
        a.set_numeric_output(value="a")
    except ValueError as e:
        succ_two = "numeric output should be integer" in str(e)
    succ_three = False
    try:
        a.set_numeric_output(value=4)
    except ValueError as e:
        succ_three = "input value should be 0 or 1" in str(e)
    a.set_numeric_output(value=1)
    succ_four = a.get_numeric_output() == 1
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablerowcol() -> bool:
    a = ro.tablerowcolumnfilterREST()
    a = ro.tablerowcolumnfilterREST()
    succ = a.get_table_name() == ""
    succ_two = False
    try:
        a.set_table_name(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_table_name(value="a")
    succ_three = a.get_filter_rows() == ["*"]
    a.set_filter_rows()
    succ_four = False
    try:
        a.set_filter_rows(value="a")
    except ValueError as e:
        succ_four = "input should be a list" in str(e)
    succ_five = False
    try:
        a.set_filter_rows(value=[1])
    except ValueError as e:
        succ_five = "all the elements in the input list should be strings" in str(e)
    a.set_filter_rows(value=["a"])
    succ_six = a.get_filter_rows() == ["a"]
    a.add_filter_rows()
    succ_seven = False
    try:
        a.add_filter_rows(value="a")
    except ValueError as e:
        succ_seven = "input should be a list" in str(e)
    succ_eight = False
    try:
        a.add_filter_rows(value=[1])
    except ValueError as e:
        succ_eight = "the input list should be strings" in str(e)
    a.add_filter_rows(value=["b"])
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven and succ_eight
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablerowcol_col() -> bool:
    a = ro.tablerowcolumnfilterREST()
    succ = a.get_filter_columns() == ["*"]
    a.set_filter_columns()
    succ_two = False
    try:
        a.set_filter_columns(value=1)
    except ValueError as e:
        succ_two = "input should be a list" in str(e)
    succ_three = False
    try:
        a.set_filter_columns(value=[1])
    except ValueError as e:
        succ_three = "input list should be strings" in str(e)
    a.set_filter_columns(value=["a"])
    a.add_filter_columns()
    succ_four = False
    try:
        a.add_filter_columns(value=1)
    except ValueError as e:
        succ_four = "input should be a list" in str(e)
    succ_five = False
    try:
        a.add_filter_columns(value=[1])
    except ValueError as e:
        succ_five = "list should be strings" in str(e)
    a.add_filter_columns(value=["b"])
    succ_six = a.get_filter_columns() == ["a", "*", "b"]
    assert succ and succ_two and succ_three and succ_four and succ_five and succ_six


@pytest.mark.ado_test
def test_tablerowcol_invertsort() -> bool:
    a = ro.tablerowcolumnfilterREST()
    succ = a.get_invert() == 0
    succ_two = False
    try:
        a.set_invert(value="a")
    except ValueError as e:
        succ_two = "invert input should be integer or True/False" in str(e)
    succ_three = False
    try:
        a.set_invert(value=5)
    except ValueError as e:
        succ_three = "integer input value should be 0 or 1" in str(e)
    a.set_invert(value=1)
    succ_four = a.get_invert() == 1
    succ_five = a.get_sort() == 0
    succ_six = False
    try:
        a.set_sort(value="1")
    except ValueError as e:
        succ_six = "sort input should be integer or True/False" in str(e)
    succ_seven = False
    try:
        a.set_sort(value=4)
    except ValueError as e:
        succ_seven = "integer input value should be 0 or 1" in str(e)
    a.set_sort(value=1)
    succ_eight = a.get_sort() == 1
    a.set_invert(value=True)
    succ_nine = False
    try:
        a.set_sort(value=1)
    except ValueError as e:
        succ_nine = "sort can not be set if the invert toggle is ON" in str(e)
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven and succ_eight and succ_nine
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablerowcol_transp() -> bool:
    a = ro.tablerowcolumnfilterREST()
    succ = a.get_table_transpose() == 0
    succ_two = False
    try:
        a.set_table_transpose(value="a")
    except ValueError as e:
        succ_two = "the transpose input should be integer or True/False" in str(e)
    succ_three = False
    try:
        a.set_table_transpose(value=5)
    except ValueError as e:
        succ_three = "integer input value should be 0 or 1" in str(e)
    a.set_table_transpose(value=True)
    succ_four = a.get_table_transpose()
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_tablevaluefilter() -> bool:
    a = ro.tablevaluefilterREST()
    succ = a.get_table_name() == ""
    succ_two = False
    try:
        a.set_table_name(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_table_name(value="a")
    succ_three = a.get_table_name() == "a"
    succ_four = a.get_filter_by() == ["column", "0"]
    a.set_filter_by()
    succ_five = False
    try:
        a.set_filter_by(value="a")
    except ValueError as e:
        succ_five = "input should be a list" in str(e)
    succ_six = False
    try:
        a.set_filter_by(value=[])
    except ValueError as e:
        succ_six = "input list should contain 2 values" in str(e)
    succ_seven = False
    try:
        a.set_filter_by(value=["a", "0"])
    except ValueError as e:
        succ_seven = "first input should be row / column" in str(e)
    succ_eight = False
    try:
        a.set_filter_by(value=["row", 0])
    except ValueError as e:
        succ_eight = "second input should be a str" in str(e)
    a.set_filter_by(value=["row", "0"])
    succ_nine = a.get_filter_by() == ["row", "0"]
    succ_a = succ and succ_two and succ_three and succ_four and succ_five
    succ_b = succ_six and succ_seven and succ_eight and succ_nine
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablevaluefilter_filter() -> bool:
    a = ro.tablevaluefilterREST()
    a.get_filter()
    a.set_filter()
    succ = False
    try:
        a.set_filter(value="a")
    except ValueError as e:
        succ = "input should be a list" in str(e)
    succ_two = False
    try:
        a.set_filter(value=[])
    except ValueError as e:
        succ_two = "list input is too short" in str(e)
    succ_three = False
    try:
        a.set_filter(value=["range", 1])
    except ValueError as e:
        succ_three = "input should contain 3 elements" in str(e)
    succ_four = False
    try:
        a.set_filter(value=["range", 1, 2])
    except ValueError as e:
        succ_four = "all input elements should be strings" in str(e)
    a.set_filter(value=["range", "a", "b"])
    succ_five = a.get_filter()[0] == "range"
    succ_six = False
    try:
        a.set_filter(value=["specific", "a", "b"])
    except ValueError as e:
        succ_six = "input should contain 2 elements" in str(e)
    succ_seven = False
    try:
        a.set_filter(value=["specific", "a"])
    except ValueError as e:
        succ_seven = "second input should be a list" in str(e)
    succ_eight = False
    try:
        a.set_filter(value=["specific", [1, 2]])
    except ValueError as e:
        succ_eight = "specific value(s) should be string" in str(e)
    a.set_filter(value=["specific", ["a", "b"]])
    succ_nine = a.get_filter()[0] == "specific"
    succ_ten = False
    try:
        a.set_filter(value=["top_percentage", "a", "b"])
    except ValueError as e:
        succ_ten = "first input is not among the acceptable values" in str(e)
    succ_eleven = False
    try:
        a.set_filter(value=["top_percent", "a", "b"])
    except ValueError as e:
        succ_eleven = "input should contain 2 elements" in str(e)
    succ_twelve = False
    try:
        a.set_filter(value=["top_percent", "a"])
    except ValueError as e:
        succ_twelve = "second input should be a float" in str(e)
    succ_thirteen = False
    try:
        a.set_filter(value=["top_percent", 110])
    except ValueError as e:
        succ_thirteen = "percentage should be in the (0,100) range" in str(e)
    a.set_filter(value=["top_percent", 10])
    succ_fourteen = a.get_filter()[0] == "top_percent"
    succ_fifteen = False
    try:
        a.set_filter(value=["top_count", 10, 10])
    except ValueError as e:
        succ_fifteen = "input should contain 2 elements" in str(e)
    succ_sixteen = False
    try:
        a.set_filter(value=["top_count", "a"])
    except ValueError as e:
        succ_sixteen = "second input should be an int" in str(e)
    a.set_filter(value=["top_count", 3])
    succ_seventeen = a.get_filter()[0] == "top_count"
    succ_eighteen = False
    try:
        a.set_filter(value=["bot_percent", 3, 3])
    except ValueError as e:
        succ_eighteen = "input should contain 2 elements" in str(e)
    succ_nineteen = False
    try:
        a.set_filter(value=["bot_percent", "a"])
    except ValueError as e:
        succ_nineteen = "the second input should be a float" in str(e)
    succ_twenty = False
    try:
        a.set_filter(value=["bot_percent", 110])
    except ValueError as e:
        succ_twenty = "percentage should be in the (0,100) range" in str(e)
    a.set_filter(value=["bot_percent", 10])
    succ_twentyone = a.get_filter()[0] == "bot_percent"
    succ_twentytwo = False
    try:
        a.set_filter(value=["bot_count", 1, 1])
    except ValueError as e:
        succ_twentytwo = "input should contain 2 elements" in str(e)
    succ_twentythree = False
    try:
        a.set_filter(value=["bot_count", "a"])
    except ValueError as e:
        succ_twentythree = "second input should be an int" in str(e)
    a.set_filter(value=["bot_count", 3])
    succ_twentyfour = a.get_filter()[0] == "bot_count"
    succ_a = succ + succ_two + succ_three + succ_four + succ_five + succ_six
    succ_b = succ_seven + succ_eight + succ_nine + succ_ten + succ_eleven
    succ_c = succ_twelve + succ_thirteen + succ_fourteen + succ_fifteen
    succ_d = succ_sixteen + succ_seventeen + succ_eighteen + succ_nineteen
    succ_e = succ_twenty + succ_twentyone + succ_twentytwo
    succ_f = succ_twentythree + succ_twentyfour
    assert succ_a + succ_b + succ_c + succ_d + succ_e + succ_f


@pytest.mark.ado_test
def test_tablevaluefilter_filterparams() -> bool:
    a = ro.tablevaluefilterREST()
    a.params = '{"filter": "specific"}'
    succ_one = a.get_filter() == ["specific", ["*"]]
    a.params = '{"filter": "range"}'
    succ_two = a.get_filter() == ["range", "", ""]
    a.params = '{"filter": "top_percent"}'
    succ_three = a.get_filter() == ["top_percent", 10.0]
    a.params = '{"filter": "top_count"}'
    succ_four = a.get_filter() == ["top_count", 10]
    a.params = '{"filter": "bot_percent"}'
    succ_five = a.get_filter() == ["bot_percent", 10.0]
    a.params = '{"filter": "bot_count"}'
    succ_six = a.get_filter() == ["bot_count", 10]
    assert succ_one and succ_two and succ_three and succ_four and succ_five and succ_six


@pytest.mark.ado_test
def test_tablevaluefilter_invertdate() -> bool:
    a = ro.tablevaluefilterREST()
    succ = a.get_invert_filter() == 0
    succ_two = False
    try:
        a.set_invert_filter(value="a")
    except ValueError as e:
        succ_two = "invert input should be integer or True/False" in str(e)
    succ_three = False
    try:
        a.set_invert_filter(value=3)
    except ValueError as e:
        succ_three = "integer input value should be 0 or 1" in str(e)
    a.set_invert_filter(value=1)
    succ_four = a.get_invert_filter() == 1
    succ_five = a.get_values_as_dates() == 0
    succ_six = False
    try:
        a.set_values_as_dates(value="a")
    except ValueError as e:
        succ_six = "values as dates input should be integer or True/False" in str(e)
    succ_seven = False
    try:
        a.set_values_as_dates(value=4)
    except ValueError as e:
        succ_seven = "integer input value should be 0 or 1" in str(e)
    a.set_values_as_dates(value=1)
    succ_eight = a.get_values_as_dates() == 1
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven and succ_eight
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_tablesort() -> bool:
    a = ro.tablesortfilterREST()
    succ = a.get_table_name() == "sorted table"
    succ_two = False
    try:
        a.set_table_name(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_table_name(value="a")
    succ_three = a.get_table_name() == "a"
    succ_four = a.get_sort_rows() == []
    a.set_sort_rows()
    succ_five = False
    try:
        a.set_sort_rows(value=1)
    except ValueError as e:
        succ_five = "input should be a list" in str(e)
    succ_six = False
    try:
        a.set_sort_rows(value=[1])
    except ValueError as e:
        succ_six = "all the elements should be string" in str(e)
    succ_seven = False
    try:
        a.set_sort_rows(value=["a"])
    except ValueError as e:
        succ_seven = "first character should be + or -" in str(e)
    a.set_sort_rows(value=["+"])
    succ_eight = a.get_sort_rows() == ["+"]
    a.add_sort_rows()
    succ_nine = False
    try:
        a.add_sort_rows(value="a")
    except ValueError as e:
        succ_nine = "input should be a list" in str(e)
    succ_ten = False
    try:
        a.add_sort_rows(value=[1])
    except ValueError as e:
        succ_ten = "all the elements should be string" in str(e)
    succ_eleven = False
    try:
        a.add_sort_rows(value=["a"])
    except ValueError as e:
        succ_eleven = "first character should be + or -" in str(e)
    a.add_sort_rows(value=["-"])
    succ_twelve = a.get_sort_rows() == ["+", "-"]
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven and succ_eight
    succ_c = succ_nine and succ_ten and succ_eleven and succ_twelve
    assert succ_a and succ_b and succ_c


@pytest.mark.ado_test
def test_tablesort_column() -> bool:
    a = ro.tablesortfilterREST()
    succ = a.get_sort_columns() == []
    a.set_sort_columns()
    succ_two = False
    try:
        a.set_sort_columns(value="a")
    except ValueError as e:
        succ_two = "input should be a list" in str(e)
    succ_three = False
    try:
        a.set_sort_columns(value=[1])
    except ValueError as e:
        succ_three = "all the elements should be string" in str(e)
    succ_four = False
    try:
        a.set_sort_columns(value=["a"])
    except ValueError as e:
        succ_four = "first character should be + or -" in str(e)
    a.set_sort_columns(value=["+"])
    a.add_sort_columns()
    succ_five = False
    try:
        a.add_sort_columns(value=[1])
    except ValueError as e:
        succ_five = "all the elements should be string" in str(e)
    succ_six = False
    try:
        a.add_sort_columns(value=["a"])
    except ValueError as e:
        succ_six = "the first character should be + or -" in str(e)
    a.add_sort_columns(value=["-"])
    succ_seven = a.get_sort_columns() == ["+", "-"]
    succ_a = succ and succ_two and succ_three
    succ_b = succ_four and succ_five and succ_six and succ_seven
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_treerule() -> bool:
    a = ro.treemergeREST()
    succ = a.get_merge_rule() == "all"
    succ_two = False
    try:
        a.set_merge_rule(value="a")
    except ValueError as e:
        succ_two = "legal match rules are: 'all', 'common', 'first'" in str(e)
    a.set_merge_rule(value="first")
    succ_three = False
    try:
        a.set_match_rule(value="a")
    except ValueError as e:
        succ_three = "legal match rules are: 'key', 'name', 'both'" in str(e)
    a.set_match_rule(value="name")
    succ_four = a.get_match_rule() == "name"
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_treevalue() -> bool:
    a = ro.treemergeREST()
    succ = False
    try:
        a.set_tree_name(value=1)
    except ValueError as e:
        succ = "the input should be a string" in str(e)
    a.set_tree_name(value="a")
    succ_two = a.get_tree_name() == "a"
    succ_three = False
    try:
        a.set_fill_value(value=1)
    except ValueError as e:
        succ_three = "input should be a string" in str(e)
    a.set_fill_value(value="abc")
    succ_four = a.get_fill_value() == "abc"
    succ_five = False
    try:
        a.set_header_tag(value=1)
    except ValueError as e:
        succ_five = "input should be a string" in str(e)
    a.set_header_tag(value="abcde")
    succ_six = a.get_header_tag() == "abcde"
    succ_a = succ and succ_two and succ_three
    succ_b = succ_four and succ_five and succ_six
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_sqlite_name() -> bool:
    a = ro.sqlqueriesREST()
    succ = a.get_db_type() == "SQLite"
    succ_two = False
    try:
        a.set_db_type(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    succ_three = False
    try:
        a.set_db_type(value="a")
    except ValueError as e:
        succ_three = "input should be SQLite or PostgreSQL" in str(e)
    a.set_db_type(value="PostgreSQL")
    succ_four = a.get_db_type() == "PostgreSQL"
    succ_five = a.get_sqlite_name() == ""
    succ_six = False
    try:
        a.set_sqlite_name(value=1)
    except ValueError as e:
        succ_six = "input should be a string" in str(e)
    succ_seven = False
    try:
        a.set_sqlite_name(value="a")
    except ValueError as e:
        succ_seven = "can not set SQLite database" in str(e)
    a.set_db_type()
    a.set_sqlite_name(value="a")
    succ_eight = a.get_sqlite_name() == "a"
    succ_a = succ and succ_two and succ_three and succ_four
    succ_b = succ_five and succ_six and succ_seven and succ_eight
    assert succ_a and succ_b


@pytest.mark.ado_test
def test_sqlite_postgre() -> bool:
    a = ro.sqlqueriesREST()
    a.set_db_type(value="SQLite")
    succ = type(a.get_postgre()) is dict
    succ_five = False
    try:
        a.set_postgre()
    except ValueError as e:
        succ_five = "can not set PostgreSQL database" in str(e)
    a.set_db_type(value="PostgreSQL")
    a.set_postgre()
    a.set_postgre(value={})
    succ_two = False
    try:
        a.set_postgre(value=1)
    except ValueError as e:
        succ_two = "input should be a dictionary" in str(e)
    my_dict = {"database": "a", "hostname": "b", "port": "123", "username": "c", "password": "d"}
    a.set_postgre(value=my_dict)
    succ_three = a.get_postgre() == my_dict
    succ_four = "Could not validate connection" in a.validate()[1]
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_squile_query() -> bool:
    a = ro.sqlqueriesREST()
    succ = a.get_query() == ""
    succ_two = False
    try:
        a.set_query(value=1)
    except ValueError as e:
        succ_two = "input should be a string" in str(e)
    a.set_query(value="aa")
    succ_three = a.get_query() == "aa"
    succ_four = "file is not a valid" in a.validate()[1]
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_pptx() -> bool:
    a = ro.pptxREST()
    a.input_pptx = "a"
    succ = a.input_pptx == "a"
    a.use_all_slides = 1
    succ_two = a.use_all_slides == 1
    a.output_pptx = "b"
    succ_three = a.output_pptx == "b"
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_pptx_slide() -> bool:
    a = ro.pptxslideREST()
    a.source_slide = "a"
    assert a.source_slide == "a"


@pytest.mark.ado_test
def test_datafilter() -> bool:
    a = ro.datafilterREST()
    a.filter_types = "a"
    assert a.filter_types == "a"
    a.filter_checkbox = "b"
    assert a.filter_checkbox == "b"
    a.filter_slider = "c"
    assert a.filter_slider == "c"
    a.filter_input = "d"
    assert a.filter_input == "d"
    a.filter_dropdown = "e"
    assert a.filter_dropdown == "e"
    a.filter_numeric_step = "f"
    assert a.filter_numeric_step == "f"
    a.filter_single_dropdown = "g"
    assert a.filter_single_dropdown == "g"


@pytest.mark.ado_test
def test_unit_template() -> bool:
    a = ro.Template()
    succ = a.get_template_object(guid="a") is None
    a = ro.Template(initial_data={"a": 1})
    succ_two = a.get_template_object(guid="a") is None
    succ_three = a.get_params() == {}
    a.set_params()
    succ_four = False
    try:
        a.set_params(d="a")
    except ValueError as e:
        succ_four = "input must be a dictionary" in str(e)
    a.change_type(t=a.report_type)
    a.from_json(json_dict={"a": "b", "c": b"d"})
    a.get_parent_object()
    assert succ and succ_two and succ_three and succ_four


@pytest.mark.ado_test
def test_unit_base() -> bool:
    a = ro.BaseRESTObject()
    succ_two = a.add_quotes(s=" 'abc' ") == "' 'abc' '"
    a.rebuild_tags(v=["abc=cdef"])
    a.add_tag(tag="a")
    a.rem_tag(tag="abc")
    a = ro.ItemREST()
    succ_three = isinstance(a._validate_and_get_categories(categories=[]), set)
    succ_four = False
    try:
        a._validate_and_get_category(category=0)
    except ValueError as e:
        succ_four = "has to be a valid string or an ItemCategoryREST" in str(e)
    assert succ_two and succ_three and succ_four


def test_item_payload(adr_service_query) -> bool:
    try:
        for i in adr_service_query.query():
            _ = i.item.get_payload_content(as_list=True)
        succ = True
    except Exception:
        succ = False
    adr_service_query.stop()
    assert succ
