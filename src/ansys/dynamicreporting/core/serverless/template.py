from dataclasses import field
from datetime import datetime
import json

from django.template.loader import render_to_string
from django.utils import timezone

from ..exceptions import ADRException
from .base import BaseModel


class Template(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="{}")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: "Template" = field(compare=False, kw_only=True, default=None)
    children: list["Template"] = field(compare=False, kw_only=True, default_factory=list)
    _children_order: str = field(
        compare=False, init=False, default=""
    )  # computed from self.children
    _master: bool = field(compare=False, init=False, default=True)
    report_type: str = ""
    _properties: tuple = tuple()  # todo: add properties of each type ref: report_objects
    _orm_model: str = "reports.models.Template"
    # Class-level registry of subclasses keyed by type
    _type_registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically register the subclass based on its type attribute
        Template._type_registry[cls.report_type] = cls

    def __post_init__(self):
        if self.report_type == "":
            raise TypeError("Cannot instantiate Template directly. Use Template.create()")
        super().__post_init__()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"

    @property
    def type(self):
        return self.report_type

    @type.setter
    def type(self, value):
        if not isinstance(value, str):
            raise ValueError(f"{value} must be a string")
        self.report_type = value

    @property
    def children_order(self):
        return self._children_order

    @property
    def master(self):
        return self._master

    def save(self, **kwargs):
        if self.parent is not None and not self.parent._saved:
            raise Template.NotSaved(
                extra_detail="Failed to save template because its parent is not saved"
            )
        children_order = []
        for child in self.children:
            if not isinstance(child, Template):
                raise TypeError(
                    f"Failed to save template because child '{child}' is not a Template object"
                )
            if not child._saved:
                raise Template.NotSaved(
                    extra_detail="Failed to save template because its children are not saved"
                )
            children_order.append(str(child.guid))
        self._children_order = ",".join(children_order)
        self._master = self.parent is None
        # set properties
        prop_dict = {}
        for prop in self._properties:
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
                templ_cls = cls._type_registry[kwargs.pop("report_type")]
            except KeyError:
                raise ADRException("The 'report_type' must be passed when using the Template class")
            return templ_cls.create(**kwargs)

        new_kwargs = {"report_type": cls.report_type, **kwargs}
        return super().create(**new_kwargs)

    @classmethod
    def get(cls, **kwargs):
        new_kwargs = {"report_type": cls.report_type, **kwargs} if cls.report_type else kwargs
        return super().get(**new_kwargs)

    @classmethod
    def get_or_create(cls, **kwargs):
        new_kwargs = {"report_type": cls.report_type, **kwargs} if cls.report_type else kwargs
        return super().get_or_create(**new_kwargs)

    @classmethod
    def filter(cls, **kwargs):
        new_kwargs = {"report_type": cls.report_type, **kwargs} if cls.report_type else kwargs
        return super().filter(**new_kwargs)

    @classmethod
    def find(cls, query="", **kwargs):
        if not cls.report_type:
            return super().find(query=query, **kwargs)
        if "t_types|cont" in query:
            raise ADRException(
                extra_detail="The 't_types' filter is not required if using a subclass of Template"
            )
        query_string = f"A|t_types|cont|{cls.report_type};{query}"  # noqa: E702
        return super().find(query=query_string, **kwargs)

    def reorder_children(self) -> None:
        guid_to_child = {str(child.guid): child for child in self.children}
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

    def render(self, context=None, request=None, item_filter="") -> str:
        if context is None:
            context = {}
        ctx = {**context, "request": request, "ansys_version": None}
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
            ctx["HTML"] = engine.render(items, ctx)
            # fill in any TOC entries
            ctx["HTML"] += TemplateEngine.end_toc_session()
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report", guid=self.guid)

        return render_to_string("reports/report_display_simple.html", context=ctx, request=request)


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
    report_type: str = "Layout:basic"


class PanelLayout(Layout):
    report_type: str = "Layout:panel"


class BoxLayout(Layout):
    report_type: str = "Layout:box"


class TabLayout(Layout):
    report_type: str = "Layout:tabs"


class CarouselLayout(Layout):
    report_type: str = "Layout:carousel"


class SliderLayout(Layout):
    report_type: str = "Layout:slider"


class FooterLayout(Layout):
    report_type: str = "Layout:footer"


class HeaderLayout(Layout):
    report_type: str = "Layout:header"


class IteratorLayout(Layout):
    report_type: str = "Layout:iterator"


class TagPropertyLayout(Layout):
    report_type: str = "Layout:tagprops"


class TOCLayout(Layout):
    report_type: str = "Layout:toc"


class ReportLinkLayout(Layout):
    report_type: str = "Layout:reportlink"


class PPTXLayout(Layout):
    report_type: str = "Layout:pptx"


class PPTXSlideLayout(Layout):
    report_type: str = "Layout:pptxslide"


class DataFilterLayout(Layout):
    report_type: str = "Layout:datafilter"


class UserDefinedLayout(Layout):
    report_type: str = "Layout:userdefined"


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
    report_type: str = "Generator:tablemerge"


class TableReduceGenerator(Generator):
    report_type: str = "Generator:tablereduce"


class TableMergeRCFilterGenerator(Generator):
    report_type: str = "Generator:tablerowcolumnfilter"


class TableMergeValueFilterGenerator(Generator):
    report_type: str = "Generator:tablevaluefilter"


class TableSortFilterGenerator(Generator):
    report_type: str = "Generator:tablesortfilter"


class TreeMergeGenerator(Generator):
    report_type: str = "Generator:treemerge"


class SQLQueryGenerator(Generator):
    report_type: str = "Generator:sqlqueries"


class ItemsComparisonGenerator(Generator):
    report_type: str = "Generator:itemscomparison"


class StatisticalGenerator(Generator):
    report_type: str = "Generator:statistical"


class IteratorGenerator(Generator):
    report_type: str = "Generator:iterator"
