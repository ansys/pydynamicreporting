from dataclasses import field
from datetime import datetime
import json
import os
import uuid

from django.template.loader import render_to_string
from django.utils import timezone

from ..constants import JSON_ATTR_KEYS
from ..exceptions import ADRException, TemplateDoesNotExist, TemplateReorderOutOfBounds
from .base import BaseModel, StrEnum


class ReportType(StrEnum):
    DEFAULT = ""
    # Layouts
    BASIC_LAYOUT = "Layout:basic"
    PANEL_LAYOUT = "Layout:panel"
    BOX_LAYOUT = "Layout:box"
    TABS_LAYOUT = "Layout:tabs"
    CAROUSEL_LAYOUT = "Layout:carousel"
    SLIDER_LAYOUT = "Layout:slider"
    FOOTER_LAYOUT = "Layout:footer"
    HEADER_LAYOUT = "Layout:header"
    ITERATOR_LAYOUT = "Layout:iterator"
    TAG_PROPS_LAYOUT = "Layout:tagprops"
    TOC_LAYOUT = "Layout:toc"
    REPORT_LINK_LAYOUT = "Layout:reportlink"
    PPTX_LAYOUT = "Layout:pptx"
    PPTX_SLIDE_LAYOUT = "Layout:pptxslide"
    DATA_FILTER_LAYOUT = "Layout:datafilter"
    USER_DEFINED_LAYOUT = "Layout:userdefined"
    # Generators
    TABLE_MERGE_GENERATOR = "Generator:tablemerge"
    TABLE_REDUCE_GENERATOR = "Generator:tablereduce"
    TABLE_MAP_GENERATOR = "Generator:tablemap"
    TABLE_ROW_COLUMN_FILTER_GENERATOR = "Generator:tablerowcolumnfilter"
    TABLE_VALUE_FILTER_GENERATOR = "Generator:tablevaluefilter"
    TABLE_SORT_FILTER_GENERATOR = "Generator:tablesortfilter"
    TREE_MERGE_GENERATOR = "Generator:treemerge"
    SQL_QUERIES_GENERATOR = "Generator:sqlqueries"
    ITEMS_COMPARISON_GENERATOR = "Generator:itemscomparison"
    STATISTICAL_GENERATOR = "Generator:statistical"
    ITERATOR_GENERATOR = "Generator:iterator"


class Template(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="{}")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: "Template" = field(compare=False, kw_only=True, default=None)
    children: list["Template"] = field(compare=False, kw_only=True, default_factory=list)
    report_type: str = ReportType.DEFAULT  # todo: make this read-only
    _children_order: str = field(
        compare=False, init=False, default=""
    )  # computed from self.children
    _master: bool = field(compare=False, init=False, default=True)
    _properties: tuple = tuple()  # todo: add properties for each type ref: report_objects
    _orm_model: str = "reports.models.Template"
    # Class-level registry of subclasses keyed by type
    _type_registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically register the subclass based on its type attribute
        Template._type_registry[cls.report_type] = cls

    def __post_init__(self):
        if self.__class__ is Template:
            raise ADRException(
                "Cannot instantiate Template directly. Use the Template.create() method."
            )
        super().__post_init__()

    def _to_dict(
        self,
        next_id: int = 0,
        guid_id_map: dict[str, int] | None = None,
    ) -> tuple[dict, dict[str, int], int]:
        """
        Recursively build the template tree data structure.

        Returns:
            - templates_data: dict with full hierarchy of templates
            - guid_id_map: map of original GUIDs to template indices
            - next_id: the next available ID index after this subtree
        """
        if guid_id_map is None:
            guid_id_map = {}

        guid_id_map[self.guid] = next_id
        curr_key = f"Template_{next_id}"
        next_id += 1

        curr_data = {
            k: getattr(self, k) for k in JSON_ATTR_KEYS if getattr(self, k, None) is not None
        }

        curr_data["params"] = self.get_params()
        curr_data["sort_selection"] = self.get_sort_selection()
        curr_data["guid"] = str(uuid.uuid4()) if self.parent is None else None
        curr_data["parent"] = (
            None if self.parent is None else f"Template_{guid_id_map[self.parent.guid]}"
        )

        curr_data["children"] = []
        templates_data = {curr_key: curr_data}

        for child in self.children:
            child_dict, guid_id_map, next_id = child._to_dict(next_id, guid_id_map)
            child_key = f"Template_{guid_id_map[child.guid]}"
            curr_data["children"].append(child_key)
            templates_data.update(child_dict)

        return templates_data, guid_id_map, next_id

    @property
    def type(self):
        return self.report_type

    @property
    def children_order(self):
        return self._children_order

    @property
    def master(self):
        return self._master

    def save(self, **kwargs):
        if self.parent is not None and not self.parent.saved:
            raise self.parent.__class__.NotSaved(
                extra_detail="Failed to save template because its parent is not saved"
            )
        children_order = []
        for child in self.children:
            if not isinstance(child, Template):
                raise TypeError(
                    f"Failed to save template because child '{child}' is not a Template object"
                )
            if not child.saved:
                raise child.__class__.NotSaved(
                    extra_detail="Failed to save template because its children are not saved"
                )
            children_order.append(child.guid)
        self._children_order = ",".join(children_order)
        self._master = self.parent is None
        # set properties
        prop_dict = {}
        for prop in self.__class__._properties:
            value = getattr(self, prop, None)
            if value is not None:
                prop_dict[prop] = value
        if prop_dict:
            self.add_property(prop_dict)
        super().save(**kwargs)

    @classmethod
    def from_db(cls, orm_instance, **kwargs):
        # Create a new instance of the correct subclass
        if cls is Template:
            # the typename should be:  Class:Classname  where Class can be 'Layout' or 'Generator'
            # originally, there were no Class values, so for backward compatibility, we prefix
            # with 'Layout'...
            type_name = orm_instance.report_type
            if ":" not in type_name:
                type_name = "Layout:" + type_name
            # Get the class based on the type attribute
            templ_cls = cls._type_registry[type_name]
            obj = templ_cls.from_db(orm_instance, **kwargs)
        else:
            obj = super().from_db(orm_instance, **kwargs)
        # add relevant props from property dict.
        props = obj.get_property()
        for prop in cls._properties:
            if prop in props:
                setattr(obj, prop, props[prop])
        return obj

    @classmethod
    def create(cls, **kwargs):
        # Create a new instance of the correct subclass
        if cls is Template:
            # Get the class based on the type attribute
            try:
                type_name = kwargs.pop("report_type")
            except KeyError:
                raise ADRException("The 'report_type' must be passed when using the Template class")
            # Get the class based on the type attribute
            templ_cls = cls._type_registry[type_name]
            return templ_cls.create(**kwargs)

        new_kwargs = {"report_type": cls.report_type, **kwargs}
        return super().create(**new_kwargs)

    @classmethod
    def _validate_kwargs(cls, **kwargs):
        if "children" in kwargs:
            raise ValueError("'children' kwarg is not supported for get and filter methods")
        return {"report_type": cls.report_type, **kwargs} if cls.report_type else kwargs

    @classmethod
    def get(cls, **kwargs):
        return super().get(**cls._validate_kwargs(**kwargs))

    @classmethod
    def filter(cls, **kwargs):
        return super().filter(**cls._validate_kwargs(**kwargs))

    @classmethod
    def find(cls, query="", **kwargs):
        if cls is Template:
            return super().find(query=query, **kwargs)
        if "t_types|" in query:
            raise ADRException(
                extra_detail="The 't_types' filter is not allowed if using a subclass of Template"
            )
        query_string = f"A|t_types|cont|{cls.report_type};{query}"  # noqa: E702
        return super().find(query=query_string, **kwargs)

    def reorder_children(self) -> None:
        guid_to_child = {child.guid: child for child in self.children}
        sorted_guids = self.children_order.lower().split(",")
        # return the children based on the order of guids in children_order
        reordered = []
        for guid in sorted_guids:
            if guid in guid_to_child:
                reordered.append(guid_to_child[guid])
        self.children = reordered

    def get_filter(self):
        return self.item_filter

    def set_filter(self, filter_str):
        if not isinstance(filter_str, str):
            raise TypeError("filter value should be a string")
        self.item_filter = filter_str

    def add_filter(self, filter_str=""):
        if not isinstance(filter_str, str):
            raise TypeError("filter value should be a string")
        self.item_filter += filter_str

    def get_params(self) -> dict:
        return json.loads(self.params)

    def set_params(self, new_params: dict) -> None:
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("input must be a dictionary")
        self.params = json.dumps(new_params)

    def add_params(self, new_params: dict):
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("input must be a dictionary")
        curr_params = self.get_params()
        self.set_params(curr_params | new_params)

    def get_property(self):
        return self.get_params().get("properties", {})

    def set_property(self, new_props: dict):
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("input must be a dictionary")
        params = self.get_params()
        params["properties"] = new_props
        self.set_params(params)

    def add_property(self, new_props: dict):
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("input must be a dictionary")
        params = self.get_params()
        curr_props = params.get("properties", {})
        params["properties"] = curr_props | new_props
        self.set_params(params)

    def add_properties(self, new_props: dict) -> None:
        self.add_property(new_props)

    def get_sort_fields(self):
        return self.get_params().get("sort_fields", [])

    def set_sort_fields(self, sort_field):
        if not isinstance(sort_field, list):
            raise ValueError("sorting filter is not a list")
        params = self.get_params()
        params["sort_fields"] = sort_field
        self.set_params(params)

    def add_sort_fields(self, sort_field):
        if not isinstance(sort_field, list):
            raise ValueError("sorting filter is not a list")
        params = self.get_params()
        params["sort_fields"].extend(sort_field)
        self.set_params(params)

    def get_sort_selection(self):
        return self.get_params().get("sort_selection", "")

    def set_sort_selection(self, value="all"):
        if not isinstance(value, str):
            raise ValueError("sort selection input should be a string")
        if value not in ("all", "first", "last"):
            raise ValueError("sort selection not among the acceptable inputs")
        params = self.get_params()
        params["sort_selection"] = value
        self.set_params(params)

    def get_filter_mode(self):
        return self.get_params().get("filter_type", "items")

    def set_filter_mode(self, value="items"):
        if not isinstance(value, str):
            raise ValueError("filter mode input should be a string")
        if value not in ("items", "root_replace", "root_append"):
            raise ValueError("filter mode not among the acceptable inputs")
        params = self.get_params()
        params["filter_type"] = value
        self.set_params(params)

    def render(self, *, context=None, item_filter="", request=None) -> str:
        """
        Render the template to HTML.

        Parameters
        ----------
        context : dict, optional
            Context to be used in the template rendering. Defaults to an empty dictionary.
        item_filter : str, optional
            Filter string to be applied to the items. Defaults to an empty string.
        request : HttpRequest, optional
            The HTTP request object, used to provide additional context for rendering. Defaults to None.

        Returns
        -------
        str
            The rendered HTML string, or an error message if rendering fails.
        """
        if context is None:
            context = {}
        ctx = {
            "request": request,
            "ansys_version": None,
            "plotly": int(context.get("plotly", 0)),  # default referenced in the header via static
            "page_width": float(context.get("pwidth", "10.5")),
            "page_dpi": float(context.get("dpi", "96.")),
            "page_col_pixel_width": (float(context.get("pwidth", "10.5")) / 12.0)
            * float(context.get("dpi", "96.")),
            "date_date": datetime.now(timezone.get_current_timezone()).strftime("%x"),
            "date_datetime": datetime.now(timezone.get_current_timezone()).strftime("%c"),
            "date_iso": datetime.now(timezone.get_current_timezone()).isoformat(),
            "date_year": datetime.now(timezone.get_current_timezone()).year,
        }

        try:
            from data.models import Item
            from reports.engine import TemplateEngine

            template_obj = self._orm_instance
            engine = template_obj.get_engine()
            items = Item.find(query=item_filter)
            # properties that can change during iteration need to go on the class as well as globals
            TemplateEngine.set_global_context({"page_number": 1, "root_template": template_obj})
            TemplateEngine.start_toc_session()
            # Render the report
            html = engine.render(items, ctx)
            # fill in any TOC entries
            html += TemplateEngine.end_toc_session()
            ctx["HTML"] = html
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report", guid=self.guid)

        return render_to_string("reports/report_display_simple.html", context=ctx, request=request)

    def to_dict(self) -> dict:
        """
        Returns a JSON-serializable dictionary of the full template tree.
        """
        templates_data, _, _ = self._to_dict()
        return templates_data

    def to_json(self, filename: str) -> None:
        """
        Store the template as a JSON file.
        Only allow this action if this template is a root template.
        """
        if self.parent is not None:
            raise ADRException("Only root templates can be dumped to JSON files.")

        if not filename.endswith(".json"):
            filename += ".json"

        templates_data = self.to_dict()
        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(templates_data, json_file, indent=4)

        # Make the file read-only
        os.chmod(filename, 0o444)

    def reorder_child(self, target_child_template: "Template", new_position: int) -> None:
        """
        Reorder the target template in the `children` list to the specified position.

        Parameters
        ----------
        target_child_template : str | TemplateREST
            The child template to reorder. This can be either the GUID of the template (as a string)
            or a TemplateREST object.
        new_position : int
            The new position in the parent's children list where the template should be placed.

        Raises
        ------
        TemplateReorderOutOfBound
            If the specified position is out of bounds.
        TemplateDoesNotExist
            If the target_child_template is not found in the parent's children list.
        """
        children_size = len(self.children)
        if new_position < 0 or new_position >= children_size:
            raise TemplateReorderOutOfBounds(
                f"The specified position {new_position} is out of bounds. "
                f"Valid range: [0, {len(self.children)})"
            )

        target_guid = target_child_template.guid
        if target_child_template not in self.children:
            raise TemplateDoesNotExist(
                f"Template with GUID '{target_guid}' is not found in the parent's children list."
            )
        self.children.remove(target_child_template)
        self.children.insert(new_position, target_child_template)


class Layout(Template):
    def get_column_count(self):
        return self.get_params().get("column_count", 1)

    def set_column_count(self, value):
        if not isinstance(value, int):
            raise ValueError("column count input should be an integer")
        if value <= 0:
            raise ValueError("column count input should be larger than 0")
        params = self.get_params()
        params["column_count"] = value
        self.set_params(params)

    def get_column_widths(self):
        return self.get_params().get("column_widths", [1.0])

    def set_column_widths(self, value):
        if not isinstance(value, list):
            raise ValueError("column widths input should be a list")
        if not all(isinstance(x, (int, float)) for x in value):
            raise ValueError("column widths input should be a list of integers or floats")
        if not all(x > 0 for x in value):
            raise ValueError("column widths input should be larger than 0")
        params = self.get_params()
        params["column_widths"] = value
        self.set_params(params)

    def get_html(self):
        return self.get_params().get("HTML", "")

    def set_html(self, value=""):
        if not isinstance(value, str):
            raise ValueError("input needs to be a string")
        params = self.get_params()
        params["HTML"] = value
        self.set_params(params)

    def get_comments(self):
        return self.get_params().get("comments", "")

    def set_comments(self, value=""):
        if not isinstance(value, str):
            raise ValueError("input needs to be a string")
        params = self.get_params()
        params["comments"] = value
        self.set_params(params)

    def get_transpose(self):
        return self.get_params().get("transpose", 0)

    def set_transpose(self, value=0):
        if not isinstance(value, int):
            raise ValueError("input needs to be an integer")
        params = self.get_params()
        params["transpose"] = value
        self.set_params(params)

    def get_skip(self):
        return self.get_params().get("skip_empty", 0)

    def set_skip(self, value=0):
        if not isinstance(value, int) or value not in (0, 1):
            raise ValueError("input needs to be an integer (0 or 1)")
        params = self.get_params()
        params["skip_empty"] = value
        self.set_params(params)


class BasicLayout(Layout):
    report_type: str = ReportType.BASIC_LAYOUT


class PanelLayout(Layout):
    report_type: str = ReportType.PANEL_LAYOUT


class BoxLayout(Layout):
    report_type: str = ReportType.BOX_LAYOUT


class TabLayout(Layout):
    report_type: str = ReportType.TABS_LAYOUT


class CarouselLayout(Layout):
    report_type: str = ReportType.CAROUSEL_LAYOUT


class SliderLayout(Layout):
    report_type: str = ReportType.SLIDER_LAYOUT


class FooterLayout(Layout):
    report_type: str = ReportType.FOOTER_LAYOUT


class HeaderLayout(Layout):
    report_type: str = ReportType.HEADER_LAYOUT


class IteratorLayout(Layout):
    report_type: str = ReportType.ITERATOR_LAYOUT


class TagPropertyLayout(Layout):
    report_type: str = ReportType.TAG_PROPS_LAYOUT


class TOCLayout(Layout):
    report_type: str = ReportType.TOC_LAYOUT


class ReportLinkLayout(Layout):
    report_type: str = ReportType.REPORT_LINK_LAYOUT


class PPTXLayout(Layout):
    report_type: str = ReportType.PPTX_LAYOUT
    _properties = ("input_pptx", "output_pptx", "use_all_slides")

    def render_pptx(self, *, context=None, item_filter="", request=None) -> bytes:
        """
        Render the template to PPTX. Only works for templates of type PPTXLayout.

        Parameters
        ----------
        context : dict, optional
            Context to be used in the template rendering. Defaults to an empty dictionary.
        item_filter : str, optional
            Filter string to be applied to the items. Defaults to an empty string.
        request : HttpRequest, optional
            The HTTP request object, used to provide additional context for rendering. Defaults to None.

        Returns
        -------
        bytes
            The rendered PPTX file as bytes

        Raises
        -------
        ADRException
            If rendering fails, an exception is raised with details about the failure.

        Example
        -------
        >>> template = PPTXLayout.get(guid="some-guid")
        >>> pptx_bytes = template.render_pptx(context={"key": "value"}, item_filter="some_filter", request=request)
        >>> with open("output.pptx", "wb") as f:
        ...     f.write(pptx_bytes)
        """
        if context is None:
            context = {}
        ctx = {**context, "request": request}
        try:
            from data.models import Item
            from reports.engine import TemplateEngine

            template_obj = self._orm_instance
            engine = template_obj.get_engine()
            items = Item.find(query=item_filter)
            return engine.dispatch_render("pptx", items, ctx)
        except Exception as e:
            raise ADRException(
                f"Failed to render PPTX for template {self.name} ({self.guid}): {e}"
            ) from e


class PPTXSlideLayout(Layout):
    report_type: str = ReportType.PPTX_SLIDE_LAYOUT
    _properties = (
        "source_slide",
        "exclude_from_toc",
    )


class DataFilterLayout(Layout):
    report_type: str = ReportType.DATA_FILTER_LAYOUT


class UserDefinedLayout(Layout):
    report_type: str = ReportType.USER_DEFINED_LAYOUT


class Generator(Template):
    def get_generated_items(self):
        return self.get_params().get("generate_merge", "add")

    def set_generated_items(self, value):
        if not isinstance(value, str):
            raise ValueError("generated items should be a string")
        if value not in ("add", "replace"):
            raise ValueError("input should be add or replace")
        params = self.get_params()
        params["generate_merge"] = value
        self.set_params(params)

    def get_append_tags(self):
        return self.get_params().get("generate_appendtags", True)

    def set_append_tags(self, value=True):
        if not isinstance(value, bool):
            raise ValueError("value should be True / False")
        params = self.get_params()
        params["generate_appendtags"] = value
        self.set_params(params)


class TableMergeGenerator(Generator):
    report_type: str = ReportType.TABLE_MERGE_GENERATOR


class TableReduceGenerator(Generator):
    report_type: str = ReportType.TABLE_REDUCE_GENERATOR


class TableMapGenerator(Generator):
    report_type: str = ReportType.TABLE_MAP_GENERATOR


class TableMergeRCFilterGenerator(Generator):
    report_type: str = ReportType.TABLE_ROW_COLUMN_FILTER_GENERATOR


class TableMergeValueFilterGenerator(Generator):
    report_type: str = ReportType.TABLE_VALUE_FILTER_GENERATOR


class TableSortFilterGenerator(Generator):
    report_type: str = ReportType.TABLE_SORT_FILTER_GENERATOR


class TreeMergeGenerator(Generator):
    report_type: str = ReportType.TREE_MERGE_GENERATOR


class SQLQueryGenerator(Generator):
    report_type: str = ReportType.SQL_QUERIES_GENERATOR


class ItemsComparisonGenerator(Generator):
    report_type: str = ReportType.ITEMS_COMPARISON_GENERATOR


class StatisticalGenerator(Generator):
    report_type: str = ReportType.STATISTICAL_GENERATOR


class IteratorGenerator(Generator):
    report_type: str = ReportType.ITERATOR_GENERATOR
