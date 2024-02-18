from dataclasses import dataclass, field
from typing import Type

from .base import BaseModel
from .report_framework.utils import get_render_error_html


@dataclass(repr=False)
class Template(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: Type['Template'] = field(compare=False, kw_only=True, default=None)
    children: list = field(compare=False, kw_only=True, default_factory=list)
    children_order: str = field(compare=False, kw_only=True, default="")
    master: bool = field(compare=False, kw_only=True, default=True)
    _type: str = field(init=False, compare=False, default="")

    @property
    def type(self):
        return self._type

    def post_init(self):
        from .reports.models import Template as TemplateModel
        self._orm_instance = TemplateModel()

    @staticmethod
    def get(**kwargs):
        from .reports.models import Template as TemplateModel
        return TemplateModel.objects.get(**kwargs)

    @staticmethod
    def create(**kwargs):
        from .reports.models import Template as TemplateModel
        return TemplateModel.objects.create(**kwargs)

    def save(self):
        # todo
        self._orm_instance.save()

    def delete(self):
        # todo: delete children, parents
        pass

    def render(self, ctx):
        if "request" not in ctx:
            ctx["request"] = None
        try:
            return self._orm_instance.render(ctx)
        except Exception as e:
            return get_render_error_html(e, target='report', guid=self.guid)

    def export(self):
        ...

    def set_filter(self):
        ...

    def set_params(self):
        ...


@dataclass(repr=False)
class Layout(Template):

    def render(self):
        pass


@dataclass(repr=False)
class BasicLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class PanelLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class BoxLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class TabLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class CarouselLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class SliderLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class FooterLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class HeaderLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class IteratorLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class TagPropertyLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class TOCLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class ReportLinkLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class PPTXLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class PPTXSlideLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class DataFilterLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class UserDefinedLayout(Layout):

    def render(self):
        pass


@dataclass(repr=False)
class Generator(Template):

    def render(self):
        pass


@dataclass(repr=False)
class TableMergeGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class TableReduceGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class TableMergeRCFilterGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class TableMergeValueFilterGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class TableSortFilterGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class TreeMergeGenerator(Generator):

    def render(self):
        pass


@dataclass(repr=False)
class SQLQueryGenerator(Generator):

    def render(self):
        pass
