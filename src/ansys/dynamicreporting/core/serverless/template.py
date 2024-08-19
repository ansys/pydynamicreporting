from dataclasses import field
from datetime import datetime
import json
from typing import Optional

from django.template.loader import render_to_string
from django.utils import timezone

from .base import BaseModel


# todo: prevent instantiation
class Template(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: "Template" = field(compare=False, kw_only=True, default=None)
    children: list = field(compare=False, kw_only=True, default_factory=list)
    _children_order: str = field(
        compare=False, init=False, default=None
    )  # computed from self.children
    _master: bool = field(compare=False, init=False, default=None)  # computed from self.parent
    type: str = ""
    _properties: tuple = tuple()
    _orm_model: str = "reports.models.Template"

    @property
    def report_type(self):
        return self.type

    @property
    def children_order(self):
        return ",".join([str(child.guid) for child in self.children])

    @property
    def master(self):
        return self.parent is None

    def get_filter(self):
        return self.item_filter

    def set_filter(self, filter_str):
        if not isinstance(filter_str, str):
            raise TypeError("Error: filter value should be a string")
        self.item_filter = filter_str

    def add_filter(self, filter_str=""):
        if not isinstance(filter_str, str):
            raise TypeError("Error: filter value should be a string")
        self.item_filter += filter_str

    def get_params(self) -> dict:
        return json.loads(self.params)

    def set_params(self, new_params: dict) -> None:
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("Error: input must be a dictionary")
        self.params = json.dumps(new_params)

    def add_params(self, new_params: dict):
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("Error: input must be a dictionary")
        curr_params = json.loads(self.params)
        self.params = json.dumps(curr_params | new_params)

    def get_property(self):
        params = json.loads(self.params)
        return params.get("properties", {})

    def set_property(self, new_props: dict):
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("Error: input must be a dictionary")
        params = json.loads(self.params)
        params["properties"] = new_props
        self.params = json.dumps(params)

    def add_property(self, new_props: dict):
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("Error: input must be a dictionary")
        params = json.loads(self.params)
        curr_props = params.get("properties", {})
        params["properties"] = curr_props | new_props
        self.params = json.dumps(params)

    def save(self, **kwargs):
        if self.parent is not None and not self.parent._saved:
            raise Template.NotSaved(
                extra_detail="Failed to save template because its parent is not saved"
            )
        for child in self.children:
            if not child._saved:
                raise Template.NotSaved(
                    extra_detail="Failed to save template because its children are not saved"
                )
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
    def get(cls, **kwargs):
        new_kwargs = {"report_type": cls.type, **kwargs} if cls.type else kwargs
        obj = super().get(**new_kwargs)
        props = obj.get_property()
        for prop in cls._properties:
            if prop in props:
                setattr(obj, prop, props[prop])
        return obj

    @classmethod
    def filter(cls, **kwargs):
        new_kwargs = {"report_type": cls.type, **kwargs} if cls.type else kwargs
        return super().filter(**new_kwargs)

    def render(self, context=None, request=None, query=None) -> Optional[str]:
        if context is None:
            context = {}
        ctx = {**context, "request": request, "ansys_version": None}
        try:
            from data.models import Item
            from reports.engine import TemplateEngine

            template_obj = self._orm_instance
            engine = template_obj.get_engine()
            items = Item.find(query=query)
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
    pass


class BasicLayout(Layout):
    type: str = "Layout:basic"


class PanelLayout(Layout):
    type: str = "Layout:panel"


class BoxLayout(Layout):
    type: str = "Layout:box"


class TabLayout(Layout):
    type: str = "Layout:tabs"


class CarouselLayout(Layout):
    type: str = "Layout:carousel"


class SliderLayout(Layout):
    type: str = "Layout:slider"


class FooterLayout(Layout):
    type: str = "Layout:footer"


class HeaderLayout(Layout):
    type: str = "Layout:header"


class IteratorLayout(Layout):
    type: str = "Layout:iterator"


class TagPropertyLayout(Layout):
    type: str = "Layout:tagprops"


class TOCLayout(Layout):
    type: str = "Layout:toc"


class ReportLinkLayout(Layout):
    type: str = "Layout:reportlink"


class PPTXLayout(Layout):
    type: str = "Layout:pptx"


class PPTXSlideLayout(Layout):
    type: str = "Layout:pptxslide"


class DataFilterLayout(Layout):
    type: str = "Layout:datafilter"


class UserDefinedLayout(Layout):
    type: str = "Layout:userdefined"


class Generator(Template):
    pass


class TableMergeGenerator(Generator):
    type: str = "Generator:tablemerge"


class TableReduceGenerator(Generator):
    type: str = "Generator:tablereduce"


class TableMergeRCFilterGenerator(Generator):
    type: str = "Generator:tablerowcolumnfilter"


class TableMergeValueFilterGenerator(Generator):
    type: str = "Generator:tablevaluefilter"


class TableSortFilterGenerator(Generator):
    type: str = "Generator:tablesortfilter"


class TreeMergeGenerator(Generator):
    type: str = "Generator:treemerge"


class SQLQueryGenerator(Generator):
    type: str = "Generator:sqlqueries"
