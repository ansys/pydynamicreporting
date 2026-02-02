# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Serverless ADR template models and layout/generator definitions.

This module defines the template hierarchy used by the serverless ADR API:

* :class:`Template` – abstract base class for all layouts and generators.
* :class:`Layout` and its subclasses – visual layout blocks such as panels,
  boxes, tabs, carousels, sliders, headers, footers, and PPTX layouts.
* :class:`Generator` and its subclasses – data transformation nodes such as
  table merge/reduce, tree merge, SQL queries, and statistical generators.

Templates are persisted via the underlying Django ORM model
``reports.models.Template`` and carry their configuration in a JSON-encoded
``params`` field.
"""

from dataclasses import field
from datetime import datetime
import json
import os
import shlex
import uuid

from django.template.loader import render_to_string
from django.utils import timezone

from ..common_utils import check_dictionary_for_html
from ..constants import JSON_ATTR_KEYS
from ..exceptions import ADRException, TemplateDoesNotExist, TemplateReorderOutOfBounds
from .base import BaseModel, StrEnum


class ReportType(StrEnum):
    """Enumeration of all supported template types.

    The values are the canonical type strings stored on the ORM model and
    used for dispatching to concrete :class:`Template` subclasses.
    """

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
    """Base class for all report templates.

    A :class:`Template` represents a node in the report definition tree.
    Templates are organized as parent/child hierarchies, carry a
    ``report_type`` discriminator used for subclass dispatch, and store
    their configuration in a JSON-encoded :attr:`params` payload.

    Concrete layouts and generators subclass :class:`Template` and define
    their own convenience properties to access over the JSON params.
    """

    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    """Template creation timestamp."""

    name: str = field(compare=False, kw_only=True, default="")
    """Human-readable name of the template."""

    params: str = field(compare=False, kw_only=True, default="{}")
    """JSON-encoded parameter dictionary backing this template configuration."""

    item_filter: str = field(compare=False, kw_only=True, default="")
    """Default ADR query string used to select items for this template."""

    parent: "Template" = field(compare=False, kw_only=True, default=None)
    """Parent template in the hierarchy, or ``None`` for a root template."""

    children: list["Template"] = field(compare=False, kw_only=True, default_factory=list)
    """Ordered list of child templates that form this template's subtree."""

    report_type: str = ReportType.DEFAULT  # todo: make this read-only
    """Canonical type string used for subclass dispatch and filtering."""

    _children_order: str = field(
        compare=False,
        init=False,
        default="",
    )
    """Serialized GUID order of :attr:`children`, used for persistence."""

    _master: bool = field(compare=False, init=False, default=True)
    """Whether this template is a root (master) template."""

    _properties: tuple[str] = tuple()
    """Class specific property names to be persisted under ``params['properties']``."""

    _orm_model: str = "reports.models.Template"
    """Dotted path to the underlying Django ORM model."""

    # Class-level registry of subclasses keyed by report_type
    _type_registry = {}

    def __init_subclass__(cls, **kwargs):
        """Register concrete subclasses in the type registry.

        Subclasses must define a unique :attr:`report_type` string. This
        registry is used by :meth:`Template.create` and :meth:`Template._from_db`
        to dispatch to the correct subclass.
        """
        super().__init_subclass__(**kwargs)
        Template._type_registry[cls.report_type] = cls

    def __post_init__(self):
        """Prevent direct instantiation of the abstract :class:`Template`.

        Only concrete subclasses (layouts/generators) should be instantiated.
        """
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
        """Recursively build a JSON-serializable template tree."""
        if guid_id_map is None:
            guid_id_map = {}

        # Assign an index to this template and build its key.
        guid_id_map[self.guid] = next_id
        curr_key = f"Template_{next_id}"
        next_id += 1

        # Copy selected attributes to the JSON payload.
        curr_data = {
            k: getattr(self, k) for k in JSON_ATTR_KEYS if getattr(self, k, None) is not None
        }

        # Normalized/derived fields.
        curr_data["params"] = self.get_params()
        curr_data["sort_selection"] = self.get_sort_selection()
        # Root templates get a fresh GUID in the JSON representation.
        curr_data["guid"] = str(uuid.uuid4()) if self.parent is None else None
        curr_data["parent"] = (
            None if self.parent is None else f"Template_{guid_id_map[self.parent.guid]}"
        )

        curr_data["children"] = []
        templates_data = {curr_key: curr_data}

        # Recurse over children and build their entries.
        for child in self.children:
            child_dict, guid_id_map, next_id = child._to_dict(next_id, guid_id_map)
            child_key = f"Template_{guid_id_map[child.guid]}"
            curr_data["children"].append(child_key)
            templates_data.update(child_dict)

        return templates_data, guid_id_map, next_id

    @property
    def type(self) -> str:
        """Alias for :attr:`report_type` for parity with items."""
        return self.report_type

    @property
    def children_order(self) -> str:
        """Comma-separated list of child GUIDs in desired order."""
        return self._children_order

    @property
    def master(self) -> bool:
        """Whether this template is a root (no parent)."""
        return self._master

    def save(self, **kwargs):
        """Save the template, enforcing parent/child invariants.

        This ensures:

        * If :attr:`parent` is set, it must already be saved.
        * All :attr:`children` must be :class:`Template` instances and saved.
        * :attr:`_children_order` is updated from :attr:`children`.
        * :attr:`_master` is derived from whether a parent is present.
        * Any configured :attr:`_properties` are merged into
          ``params['properties']`` before persisting.
        """
        if self.parent is not None and not self.parent.saved:
            raise self.parent.__class__.NotSaved(
                extra_detail="Failed to save template because its parent is not saved"
            )
        for child in self.children:
            if not isinstance(child, Template):
                raise TypeError(
                    f"Failed to save template because child '{child}' is not a Template object"
                )
            if not child.saved:
                raise child.__class__.NotSaved(
                    extra_detail="Failed to save template because its children are not saved"
                )

        # Keep the serialized children order in sync with the list content.
        self.update_children_order()
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
    def _from_db(cls, orm_instance, **kwargs):
        """Rebuild a :class:`Template` (or subclass) from an ORM instance.

        When called on :class:`Template` itself, this method determines
        the concrete subclass to use based on :attr:`report_type` and the
        :class:`ReportType` registry. For backward compatibility, plain
        names are prefixed with ``"Layout:"``.
        """
        # Dispatch to the correct subclass when called on the base Template.
        if cls is Template:
            # The type is stored as "Class:name" where Class is 'Layout' or 'Generator'.
            # Historically, the class prefix was omitted; assume 'Layout' for those.
            type_name = orm_instance.report_type
            if ":" not in type_name:
                type_name = "Layout:" + type_name
            # Get the class based on the type attribute
            templ_cls = cls._type_registry[type_name]
            obj = templ_cls._from_db(orm_instance, **kwargs)
        else:
            obj = super()._from_db(orm_instance, **kwargs)

        # Hydrate :attr:`_properties` fields from the stored property dict.
        props = obj.get_property()
        for prop in cls._properties:
            if prop in props:
                setattr(obj, prop, props[prop])
        return obj

    @classmethod
    def create(cls, **kwargs):
        """Factory-style creation that dispatches to the correct subclass.

        When invoked directly on :class:`Template`, the caller must supply
        a ``report_type`` kwarg matching one of the registered subclasses.
        Concrete subclasses inject their own :attr:`report_type` value.
        """
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
        """Normalize kwargs for typed query methods.

        The ``children`` kwarg cannot be used with :meth:`get` or
        :meth:`filter`, and type-scoped subclasses automatically inject a
        ``report_type`` filter.
        """
        if "children" in kwargs:
            raise ValueError("'children' kwarg is not supported for get and filter methods")
        return {"report_type": cls.report_type, **kwargs} if cls.report_type else kwargs

    @classmethod
    def get(cls, **kwargs):
        """Retrieve a single template, scoped by subclass :attr:`report_type`."""
        return super().get(**cls._validate_kwargs(**kwargs))

    @classmethod
    def filter(cls, **kwargs):
        """Return a collection of templates, scoped by subclass :attr:`report_type`."""
        return super().filter(**cls._validate_kwargs(**kwargs))

    @classmethod
    def find(cls, query: str = "", **kwargs):
        """Search for templates using an ADR query string.

        For typed subclasses, a ``t_types`` filter is not allowed in the
        query string; the subclass's :attr:`report_type` is injected
        automatically instead.
        """
        if cls is Template:
            return super().find(query=query, **kwargs)
        if "t_types|" in query:
            raise ADRException(
                extra_detail="The 't_types' filter is not allowed if using a subclass of Template"
            )
        query_string = f"A|t_types|cont|{cls.report_type};{query}"  # noqa: E702
        return super().find(query=query_string, **kwargs)

    def update_children_order(self) -> None:
        """Update :attr:`children_order` from the current :attr:`children` list.

        The order is stored as a comma-separated list of child GUIDs and
        is used to persist and later restore the ordering.
        """
        children_guids = [str(child.guid) for child in self.children]
        self._children_order = ",".join(children_guids)

    def reorder_children(self) -> None:
        """
        Reorder the children list based on the children_order string.
        """
        guid_to_child = {child.guid: child for child in self.children}
        sorted_guids = self.children_order.lower().split(",")
        reordered: list[Template] = []
        for guid in sorted_guids:
            if guid in guid_to_child:
                reordered.append(guid_to_child[guid])
        self.children = reordered

    def get_filter(self) -> str:
        """Return the raw item filter string."""
        return self.item_filter

    def set_filter(self, filter_str: str) -> None:
        """Replace the current item filter with ``filter_str``."""
        if not isinstance(filter_str, str):
            raise TypeError("filter value should be a string")
        self.item_filter = filter_str

    def add_filter(self, filter_str: str = "") -> None:
        """Append ``filter_str`` to the current item filter."""
        if not isinstance(filter_str, str):
            raise TypeError("filter value should be a string")
        self.item_filter += filter_str

    def get_params(self) -> dict:
        """Deserialize :attr:`params` into a Python dictionary."""
        return json.loads(self.params)

    def set_params(self, new_params: dict) -> None:
        """Replace the current params dictionary.

        Parameters
        ----------
        new_params : dict
            New parameter mapping to serialize. ``None`` is treated as
            an empty dict.
        """
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("input must be a dictionary")
        # Optional validation hook, controlled by environment.
        if os.getenv("ADR_VALIDATION_BETAFLAG_ANSYS") == "1":
            check_dictionary_for_html(new_params)
        self.params = json.dumps(new_params)

    def add_params(self, new_params: dict) -> None:
        """Merge ``new_params`` into the existing params dictionary."""
        if new_params is None:
            new_params = {}
        if not isinstance(new_params, dict):
            raise TypeError("input must be a dictionary")
        curr_params = self.get_params()
        self.set_params(curr_params | new_params)

    def get_property(self) -> dict:
        """Return the ``properties`` sub-dictionary from params (if present)."""
        return self.get_params().get("properties", {})

    def set_property(self, new_props: dict) -> None:
        """Replace the ``properties`` sub-dictionary with ``new_props``."""
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("input must be a dictionary")
        params = self.get_params()
        params["properties"] = new_props
        self.set_params(params)

    def add_property(self, new_props: dict) -> None:
        """Merge ``new_props`` into the existing ``properties`` sub-dictionary."""
        if new_props is None:
            new_props = {}
        if not isinstance(new_props, dict):
            raise TypeError("input must be a dictionary")
        params = self.get_params()
        curr_props = params.get("properties", {})
        params["properties"] = curr_props | new_props
        self.set_params(params)

    def add_properties(self, new_props: dict) -> None:
        """Alias for :meth:`add_property`."""
        self.add_property(new_props)

    def get_sort_fields(self) -> list:
        """Return the configured sort fields list, if any."""
        return self.get_params().get("sort_fields", [])

    def set_sort_fields(self, sort_field: list) -> None:
        """Set the full list of sort fields.

        Parameters
        ----------
        sort_field : list
            A list describing sorting criteria (field names, directions, etc.).
        """
        if not isinstance(sort_field, list):
            raise ValueError("sorting filter is not a list")
        params = self.get_params()
        params["sort_fields"] = sort_field
        self.set_params(params)

    def add_sort_fields(self, sort_field: list) -> None:
        """Extend the existing sort field list with ``sort_field``."""
        if not isinstance(sort_field, list):
            raise ValueError("sorting filter is not a list")
        params = self.get_params()
        params["sort_fields"].extend(sort_field)
        self.set_params(params)

    def get_sort_selection(self) -> str:
        """Return the sort selection mode (``'all'``, ``'first'``, or ``'last'``)."""
        return self.get_params().get("sort_selection", "")

    def set_sort_selection(self, value: str = "all") -> None:
        """Set the sort selection mode.

        Parameters
        ----------
        value : {"all", "first", "last"}
            Which subset of sorted items should be used downstream.
        """
        if not isinstance(value, str):
            raise ValueError("sort selection input should be a string")
        if value not in ("all", "first", "last"):
            raise ValueError("sort selection not among the acceptable inputs")
        params = self.get_params()
        params["sort_selection"] = value
        self.set_params(params)

    def get_filter_mode(self) -> str:
        """Return the filter mode (``'items'``, ``'root_replace'``, or ``'root_append'``)."""
        return self.get_params().get("filter_type", "items")

    def set_filter_mode(self, value: str = "items") -> None:
        """Set the filter mode.

        Parameters
        ----------
        value : {"items", "root_replace", "root_append"}
            How this template's filter affects the overall report tree.
        """
        if not isinstance(value, str):
            raise ValueError("filter mode input should be a string")
        if value not in ("items", "root_replace", "root_append"):
            raise ValueError("filter mode not among the acceptable inputs")
        params = self.get_params()
        params["filter_type"] = value
        self.set_params(params)

    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary for the full template tree."""
        templates_data, _, _ = self._to_dict()
        return templates_data

    def to_json(self, filename: str) -> None:
        """Dump the full template tree to a JSON file.

        Only root templates (no parent) can be exported. The resulting
        file is made read-only after writing.
        """
        if self.parent is not None:
            raise ADRException("Only root templates can be dumped to JSON files.")

        if not filename.endswith(".json"):
            filename += ".json"

        templates_data = self.to_dict()
        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(templates_data, json_file, indent=4)

        # Make the file read-only.
        os.chmod(filename, 0o444)

    def reorder_child(self, target_child_template: "Template", new_position: int) -> None:
        """Move a child template to a new position in :attr:`children`.

        Parameters
        ----------
        target_child_template : Template
            Child template instance to move.
        new_position : int
            New index in the children list.

        Raises
        ------
        TemplateReorderOutOfBounds
            If ``new_position`` is not within ``[0, len(children))``.
        TemplateDoesNotExist
            If the target template is not present in :attr:`children`.
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

    @staticmethod
    def _build_render_context(context, request):
        """Build the rendering context shared by HTML/PDF renderers.

        Adds page dimensions, DPI, and several date/time convenience
        fields on top of any user-supplied ``context``.
        """
        ctx = context or {}
        return {
            "request": request,
            "ansys_version": None,
            "plotly": int(ctx.get("plotly", 0)),
            "page_width": float(ctx.get("pwidth", "10.5")),
            "page_dpi": float(ctx.get("dpi", "96.")),
            "page_col_pixel_width": (float(ctx.get("pwidth", "10.5")) / 12.0)
            * float(ctx.get("dpi", "96.")),
            "date_date": datetime.now(timezone.get_current_timezone()).strftime("%x"),
            "date_datetime": datetime.now(timezone.get_current_timezone()).strftime("%c"),
            "date_iso": datetime.now(timezone.get_current_timezone()).isoformat(),
            "date_year": datetime.now(timezone.get_current_timezone()).year,
        }

    def render(self, *, context=None, item_filter: str = "", request=None) -> str:
        """Render the template to HTML.

        Parameters
        ----------
        context : dict, optional
            Additional context passed to the rendering engine.
        item_filter : str, optional
            ADR query string used to select :class:`Item` instances.
        request : HttpRequest, optional
            Django request object, if available.

        Returns
        -------
        str
            Rendered HTML string for the report.
        """
        ctx = self._build_render_context(context, request)
        try:
            from data.models import Item
            from reports.engine import TemplateEngine

            items = Item.find(query=item_filter)
            template_obj = self._orm_instance
            engine = template_obj.get_engine()
            # Properties that can change during iteration go into the global context.
            TemplateEngine.set_global_context({"page_number": 1, "root_template": template_obj})
            TemplateEngine.start_toc_session()
            # Render the report body.
            html = engine.render(items, ctx)
            # Append any generated TOC entries.
            html += TemplateEngine.end_toc_session()
            ctx["HTML"] = html
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report", guid=self.guid)

        return render_to_string("reports/report_display_simple.html", context=ctx, request=request)

    def render_pdf(self, *, context=None, item_filter: str = "", request=None) -> bytes:
        """Render the template to a PDF byte stream.

        Parameters
        ----------
        context : dict, optional
            Additional context passed to the rendering engine.
        item_filter : str, optional
            ADR query string used to select :class:`Item` instances.
        request : HttpRequest, optional
            Django request object, if available.

        Returns
        -------
        bytes
            PDF document bytes.

        Raises
        ------
        ADRException
            If rendering or PDF generation fails.
        """
        ctx = self._build_render_context(context, request)
        try:
            from data.models import Item
            from reports.engine import TemplateEngine
            from weasyprint import HTML

            items = Item.find(query=item_filter)
            template_obj = self._orm_instance
            engine = template_obj.get_engine()
            static_html = engine.dispatch_render("pdf", items, ctx)
            # Convert rendered HTML to PDF using WeasyPrint.
            return HTML(string=static_html).write_pdf()
        except Exception as e:
            raise ADRException(
                f"Failed to render PDF for template {self.name} ({self.guid}): {e}"
            ) from e


class Layout(Template):
    """Base class for layout-style templates.

    Layouts control visual structure (columns, HTML fragments, comments,
    etc.) and typically have one or more child templates.
    """

    def get_column_count(self) -> int:
        """Return the number of columns in this layout."""
        return self.get_params().get("column_count", 1)

    def set_column_count(self, value: int) -> None:
        """Set the number of columns in this layout."""
        if not isinstance(value, int):
            raise ValueError("column count input should be an integer")
        if value <= 0:
            raise ValueError("column count input should be larger than 0")
        params = self.get_params()
        params["column_count"] = value
        self.set_params(params)

    def get_column_widths(self) -> list[float]:
        """Return the list of column width factors."""
        return self.get_params().get("column_widths", [1.0])

    def set_column_widths(self, value: list[float]) -> None:
        """Set the list of column width factors."""
        if not isinstance(value, list):
            raise ValueError("column widths input should be a list")
        if not all(isinstance(x, (int, float)) for x in value):
            raise ValueError("column widths input should be a list of integers or floats")
        if not all(x > 0 for x in value):
            raise ValueError("column widths input should be larger than 0")
        params = self.get_params()
        params["column_widths"] = value
        self.set_params(params)

    def get_html(self) -> str:
        """Return the raw HTML fragment stored on this layout."""
        return self.get_params().get("HTML", "")

    def set_html(self, value: str = "") -> None:
        """Set the HTML fragment for this layout."""
        if not isinstance(value, str):
            raise ValueError("input needs to be a string")
        params = self.get_params()
        params["HTML"] = value
        self.set_params(params)

    def get_comments(self) -> str:
        """Return any user comments associated with this layout."""
        return self.get_params().get("comments", "")

    def set_comments(self, value: str = "") -> None:
        """Set user comments for this layout."""
        if not isinstance(value, str):
            raise ValueError("input needs to be a string")
        params = self.get_params()
        params["comments"] = value
        self.set_params(params)

    def get_transpose(self) -> int:
        """Return the table transpose flag (0 or 1)."""
        return self.get_params().get("transpose", 0)

    def set_transpose(self, value: int = 0) -> None:
        """Set whether tabular data should be transposed (0 or 1)."""
        if not isinstance(value, int) or value not in (0, 1):
            raise ValueError("input needs to be either 0 or 1")
        params = self.get_params()
        params["transpose"] = value
        self.set_params(params)

    def get_skip(self) -> int:
        """Return the 'skip empty' flag (0 or 1)."""
        return self.get_params().get("skip_empty", 0)

    def set_skip(self, value: int = 0) -> None:
        """Set whether empty content should be skipped (0 or 1)."""
        if not isinstance(value, int) or value not in (0, 1):
            raise ValueError("input needs to be either 0 or 1")
        params = self.get_params()
        params["skip_empty"] = value
        self.set_params(params)


class BasicLayout(Layout):
    """Simple layout with no extra behavior."""

    report_type: str = ReportType.BASIC_LAYOUT


class PanelLayout(Layout):
    """Panel-style layout with optional callout styling and link rendering."""

    report_type: str = ReportType.PANEL_LAYOUT

    def get_panel_style(self) -> str:
        """Return the panel style for the layout."""
        return self.get_params().get("style", "")

    def set_panel_style(self, value: str = "panel") -> None:
        """Set the panel style for the layout."""
        if not isinstance(value, str):
            raise ValueError("Panel style mode input should be a string.")

        valid_styles = (
            "panel",
            "callout-default",
            "callout-danger",
            "callout-warning",
            "callout-success",
            "callout-info",
        )
        if value not in valid_styles:
            raise ValueError(f"Panel style mode not among the acceptable inputs: {valid_styles}")

        params = self.get_params()
        params["style"] = value
        self.set_params(params)

    def get_items_as_link(self) -> int:
        """Return whether items are displayed as links (0 or 1)."""
        return self.get_params().get("items_as_links", 0)

    def set_items_as_link(self, value: int = 0) -> None:
        """Set whether items are displayed as links (0 or 1)."""
        if not isinstance(value, int) or value not in (0, 1):
            raise ValueError("Input must be an integer, either 0 or 1.")

        params = self.get_params()
        params["items_as_links"] = value
        self.set_params(params)


class BoxLayout(Layout):
    """Box layout where each child is positioned explicitly in a grid."""

    report_type: str = ReportType.BOX_LAYOUT

    def get_children_layout(self) -> dict:
        """Return the layout dictionary for all children.

        The mapping is ``guid -> [x, y, width, height, clip]``.
        """
        return self.get_params().get("boxes", {})

    def set_child_position(self, guid: str, value: list[int] | None = None) -> None:
        """Set the position ``[x, y, width, height]`` for a child GUID."""
        if value is None:
            value = [0, 0, 10, 10]

        if (
            not isinstance(value, list)
            or len(value) != 4
            or not all(isinstance(p, int) for p in value)
        ):
            raise ValueError("Position must be a list containing four integers.")

        try:
            uuid.UUID(guid, version=4)
        except (ValueError, TypeError):
            raise ValueError(f"Input guid '{guid}' is not a valid guid.")

        params = self.get_params()
        if "boxes" not in params:
            params["boxes"] = {}
        if guid not in params["boxes"]:
            params["boxes"][guid] = [0, 0, 0, 0, "self"]
        value = value.copy()  # avoid mutating the input list
        value.append(params["boxes"][guid][4])  # retain existing clip setting
        params["boxes"][guid] = value

        self.set_params(params)

    def set_child_clip(self, guid: str, clip: str = "self") -> None:
        """Set the clipping behavior for a child GUID.

        Parameters
        ----------
        guid : str
            Child template GUID.
        clip : {"self", "scroll", "none"}
            Clipping mode for the box.
        """
        valid_clips = ("self", "scroll", "none")
        if not isinstance(clip, str) or clip not in valid_clips:
            raise ValueError(f"Child clip parameter must be a string and one of {valid_clips}.")

        try:
            uuid.UUID(guid, version=4)
        except (ValueError, TypeError):
            raise ValueError(f"Input guid '{guid}' is not a valid guid.")

        params = self.get_params()
        if "boxes" not in params:
            params["boxes"] = {}
        if guid not in params["boxes"]:
            params["boxes"][guid] = [0, 0, 0, 0, "self"]
        position_values = params["boxes"][guid][0:4]  # retain existing position settings
        position_values.append(clip)
        params["boxes"][guid] = position_values
        self.set_params(params)


class TabLayout(Layout):
    """Tab-based layout that arranges children as tabs."""

    report_type: str = ReportType.TABS_LAYOUT


class CarouselLayout(Layout):
    """Carousel layout with optional animation and dot controls."""

    report_type: str = ReportType.CAROUSEL_LAYOUT

    # todo: convert set_ and get_ methods to properties
    def get_animated(self) -> int:
        """Return whether the carousel animates automatically (0 or 1)."""
        return self.get_params().get("animate", 0)

    def set_animated(self, value: int = 0) -> None:
        """Set whether the carousel animates automatically."""
        if not isinstance(value, int):
            raise ValueError("Animated input must be an integer.")

        params = self.get_params()
        params["animate"] = value
        self.set_params(params)

    def get_slide_dots(self) -> int:
        """Return the maximum number of slide indicator dots."""
        return self.get_params().get("maxdots", 20)

    def set_slide_dots(self, value: int = 20) -> None:
        """Set the maximum number of slide indicator dots."""
        if not isinstance(value, int):
            raise ValueError("Slide dots input must be an integer.")

        params = self.get_params()
        params["maxdots"] = value
        self.set_params(params)


class SliderLayout(Layout):
    """Slider layout that maps tags to slider controls."""

    report_type: str = ReportType.SLIDER_LAYOUT

    def _split_quoted_string_list(self, s: str) -> list[str]:
        """Split a comma-separated string into tokens, honoring quotes."""
        shlexer = shlex.shlex(s)
        shlexer.whitespace += ","
        shlexer.whitespace_split = True
        shlexer.commenters = ""

        tokens: list[str] = []
        while True:
            token = shlexer.get_token()
            if not token:
                break

            # Strip whitespace and quotes, then check if the result is empty.
            processed_token = token.strip().strip("'\"")
            if processed_token:
                tokens.append(processed_token)
        return tokens

    def get_map_to_slider(self) -> list[str]:
        """Return the list of tags mapped to slider controls."""
        slider_tags_str = self.get_params().get("slider_tags", "")
        if not slider_tags_str:
            return []
        return self._split_quoted_string_list(slider_tags_str)

    def _validate_slider_tags(self, tags: list[str]) -> None:
        """Validate the format and sort parameter for slider tags.

        Each tag must be of the form ``"<tag>|<sort>"`` where ``sort`` is
        one of the supported sort specifiers.
        """
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError("Input must be a list of strings.")

        valid_sorts = (
            "text_up",
            "text_down",
            "numeric_up",
            "numeric_down",
            "natural_up",
            "natural_down",
            "none",
        )
        for tag in tags:
            parts = tag.split("|")
            if len(parts) < 2 or parts[1] not in valid_sorts:
                raise ValueError(
                    f"The sorting parameter in tag '{tag}' is not supported. "
                    f"Must be one of {valid_sorts}"
                )

    def set_map_to_slider(self, value: list[str] | None = None) -> None:
        """Set the list of tags mapped to slider controls."""
        value_to_set = value or []
        self._validate_slider_tags(value_to_set)

        tags_str = ", ".join(repr(x) for x in value_to_set)

        params = self.get_params()
        params["slider_tags"] = tags_str
        self.set_params(params)

    def add_map_to_slider(self, value: list[str] | None = None) -> None:
        """Append tags to the existing slider mapping."""
        value_to_add = value or []
        self._validate_slider_tags(value_to_add)

        params = self.get_params()
        existing_tags = params.get("slider_tags", "")

        new_tags_str = ", ".join(repr(x) for x in value_to_add)

        if existing_tags:
            params["slider_tags"] = f"{existing_tags}, {new_tags_str}"
        else:
            params["slider_tags"] = new_tags_str

        self.set_params(params)


class FooterLayout(Layout):
    """Layout representing a page footer region."""

    report_type: str = ReportType.FOOTER_LAYOUT


class HeaderLayout(Layout):
    """Layout representing a page header region."""

    report_type: str = ReportType.HEADER_LAYOUT


class IteratorLayout(Layout):
    """Layout used as an iterator over items or templates."""

    report_type: str = ReportType.ITERATOR_LAYOUT


class TagPropertyLayout(Layout):
    """Layout that exposes item tags as properties."""

    report_type: str = ReportType.TAG_PROPS_LAYOUT


class TOCLayout(Layout):
    """Layout responsible for Table-of-Contents entries."""

    report_type: str = ReportType.TOC_LAYOUT


class ReportLinkLayout(Layout):
    """Layout that links to external or other ADR reports."""

    report_type: str = ReportType.REPORT_LINK_LAYOUT


class PPTXLayout(Layout):
    """Layout representing a full PPTX report definition."""

    report_type: str = ReportType.PPTX_LAYOUT
    _properties: tuple[str] = (
        "input_pptx",
        "output_pptx",
        "use_all_slides",
        "font_size",
        "html_font_scale",
    )

    def render_pptx(self, *, context=None, item_filter: str = "", request=None) -> bytes:
        """Render the template to a PPTX file (as bytes).

        Parameters
        ----------
        context : dict, optional
            Additional context used when rendering the PPTX template.
        item_filter : str, optional
            ADR query string used to select :class:`Item` instances.
        request : HttpRequest, optional
            Django request object, if available.

        Returns
        -------
        bytes
            The rendered PPTX file as a byte string.

        Raises
        ------
        ADRException
            If PPTX rendering fails.
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
    """Layout defining settings for an individual PPTX slide."""

    report_type: str = ReportType.PPTX_SLIDE_LAYOUT
    _properties: tuple[str] = (
        "source_slide",
        "exclude_from_toc",
    )


class DataFilterLayout(Layout):
    """Layout that exposes interactive data filtering controls."""

    report_type: str = ReportType.DATA_FILTER_LAYOUT
    _properties: tuple[str] = (
        "filter_types",
        "filter_checkbox",
        "filter_slider",
        "filter_input",
        "filter_dropdown",
        "filter_single_dropdown",
        "filter_numeric_step",
    )


class UserDefinedLayout(Layout):
    """Layout whose behavior is delegated to user-defined logic."""

    report_type: str = ReportType.USER_DEFINED_LAYOUT
    _properties: tuple[str] = (
        "interactive_only",
        "before_children",
        "userdef_name",
    )


class Generator(Template):
    """Base class for generator-style templates.

    Generators take input items and produce new derived items (for
    example merged, reduced, or transformed tables and trees).
    """

    def get_generated_items(self) -> str:
        """Return how generated items are merged into the stream.

        Returns either ``"add"`` (append new items) or ``"replace"`` (replace
        existing items).
        """
        return self.get_params().get("generate_merge", "add")

    def set_generated_items(self, value: str) -> None:
        """Set how generated items are merged into the stream.

        Parameters
        ----------
        value : {"add", "replace"}
            Merge strategy for generated items.
        """
        if not isinstance(value, str):
            raise ValueError("generated items should be a string")
        if value not in ("add", "replace"):
            raise ValueError("input should be add or replace")
        params = self.get_params()
        params["generate_merge"] = value
        self.set_params(params)

    def get_append_tags(self) -> bool:
        """Return whether original item tags are appended to generated items."""
        return self.get_params().get("generate_appendtags", True)

    def set_append_tags(self, value: bool = True) -> None:
        """Set whether original item tags are appended to generated items."""
        if not isinstance(value, bool):
            raise ValueError("value should be True / False")
        params = self.get_params()
        params["generate_appendtags"] = value
        self.set_params(params)


class TableMergeGenerator(Generator):
    """Generator that merges multiple tables into one."""

    report_type: str = ReportType.TABLE_MERGE_GENERATOR


class TableReduceGenerator(Generator):
    """Generator that reduces table data (for example aggregation)."""

    report_type: str = ReportType.TABLE_REDUCE_GENERATOR


class TableMapGenerator(Generator):
    """Generator that maps or transforms table values."""

    report_type: str = ReportType.TABLE_MAP_GENERATOR


class TableMergeRCFilterGenerator(Generator):
    """Generator that filters table rows/columns."""

    report_type: str = ReportType.TABLE_ROW_COLUMN_FILTER_GENERATOR


class TableMergeValueFilterGenerator(Generator):
    """Generator that filters table rows based on cell values."""

    report_type: str = ReportType.TABLE_VALUE_FILTER_GENERATOR


class TableSortFilterGenerator(Generator):
    """Generator that sorts table rows based on configured criteria."""

    report_type: str = ReportType.TABLE_SORT_FILTER_GENERATOR


class TreeMergeGenerator(Generator):
    """Generator that merges multiple tree structures."""

    report_type: str = ReportType.TREE_MERGE_GENERATOR


class SQLQueryGenerator(Generator):
    """Generator that produces items from SQL queries."""

    report_type: str = ReportType.SQL_QUERIES_GENERATOR


class ItemsComparisonGenerator(Generator):
    """Generator that compares items and outputs comparisons."""

    report_type: str = ReportType.ITEMS_COMPARISON_GENERATOR
    _properties: tuple[str] = (
        "chunk_size",
        "filters_table",
    )


class StatisticalGenerator(Generator):
    """Generator that performs statistical analyses on input items."""

    report_type: str = ReportType.STATISTICAL_GENERATOR


class IteratorGenerator(Generator):
    """Generator that iterates over subsets of items or templates."""

    report_type: str = ReportType.ITERATOR_GENERATOR
