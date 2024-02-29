import json
from dataclasses import dataclass, field
from datetime import datetime

from django.template.loader import render_to_string
from django.utils import timezone

from .base import BaseModel, require_model_import
from .report_framework.utils import get_render_error_html
from ..exceptions import ObjectNotSavedError


class Template(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: 'Template' = field(compare=False, kw_only=True, default=None)
    # todo: check if this is writable.
    children: list = field(compare=False, kw_only=True, default_factory=list)
    _children_order: str = field(compare=False, init=False, default="")  # computed from self.children
    _master: bool = field(compare=False, init=False, default=True)  # computed from self.parent
    _report_type: str = ""
    _properties: tuple = tuple()
    _orm_model: str = "reports.models.Template"

    @property
    def report_type(self):
        return self._report_type

    @property
    def type(self):
        return self._report_type

    @property
    def children_order(self):
        return self._children_order

    @property
    def master(self):
        return self._master

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
            raise ObjectNotSavedError(extra_detail="Failed to save template because its parent is not saved")
        for child in self.children:
            if not child._saved:
                raise ObjectNotSavedError(extra_detail="Failed to save template because its children are not saved")
            self._children_order += str(child.guid) + ","
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
    def get(cls, **kwargs):
        obj = super().get(**kwargs)
        props = obj.get_property()
        for prop in cls._properties:
            if prop in props:
                setattr(obj, prop, props[prop])
        return obj

    def render(self, context=None):
        if context is None:
            context = {}
        template_context = {**context}
        if "request" not in template_context:
            template_context["request"] = None
        try:
            template_context["HTML"] = self._orm_instance.render(template_context)
            return render_to_string('data/report_display_simple.html', template_context)
        except Exception as e:
            return get_render_error_html(e, target='report', guid=self.guid)


class Layout(Template):
    pass


class BasicLayout(Layout):
    _report_type: str = "Layout:basic"


class PanelLayout(Layout):
    _report_type: str = "Layout:panel"


class BoxLayout(Layout):
    _report_type: str = "Layout:panel"


class TabLayout(Layout):
    _report_type: str = "Layout:panel"


class CarouselLayout(Layout):
    _report_type: str = "Layout:panel"


class SliderLayout(Layout):
    _report_type: str = "Layout:panel"


class FooterLayout(Layout):
    _report_type: str = "Layout:panel"


class HeaderLayout(Layout):
    _report_type: str = "Layout:panel"


class IteratorLayout(Layout):
    _report_type: str = "Layout:panel"


class TagPropertyLayout(Layout):
    _report_type: str = "Layout:panel"


class TOCLayout(Layout):
    _report_type: str = "Layout:panel"


class ReportLinkLayout(Layout):
    _report_type: str = "Layout:panel"


class PPTXLayout(Layout):
    _report_type: str = "Layout:panel"


class PPTXSlideLayout(Layout):
    _report_type: str = "Layout:panel"


class DataFilterLayout(Layout):
    _report_type: str = "Layout:panel"


class UserDefinedLayout(Layout):
    _report_type: str = "Layout:panel"


class Generator(Template):

    def render(self):
        pass


class TableMergeGenerator(Generator):

    def render(self):
        pass


class TableReduceGenerator(Generator):

    def render(self):
        pass


class TableMergeRCFilterGenerator(Generator):

    def render(self):
        pass


class TableMergeValueFilterGenerator(Generator):

    def render(self):
        pass


class TableSortFilterGenerator(Generator):

    def render(self):
        pass


class TreeMergeGenerator(Generator):

    def render(self):
        pass


class SQLQueryGenerator(Generator):

    def render(self):
        pass
