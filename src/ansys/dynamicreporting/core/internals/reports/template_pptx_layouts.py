#
# *************************************************************
#  Copyright 2022-2024 ANSYS, Inc.
#
#  Unauthorized use, distribution, or duplication is prohibited.
#
#  Restricted Rights Legend
#
#  Use, duplication, or disclosure of this
#  software and its documentation by the
#  Government is subject to restrictions as
#  set forth in subdivision [(b)(3)(ii)] of
#  the Rights in Technical Data and Computer
#  Software clause at 52.227-7013.
# *************************************************************
#
import copy
import uuid
from ..report_framework.utils import get_render_error_html, get_unsupported_error_html
from django.urls import reverse

from .engine import LayoutEngine, TemplateEngine
from .pptx_gen import PPTXGenerator, PPTXManager


class PPTXBaseTemplateEngine(LayoutEngine):
    """
    Parent template for the below PPTX based templates.
    DO NOT REGISTER!
    """

    def setup_context(self, context):
        # builds a context dict for the current template
        # from the global context dict
        local_context = copy.copy(context)
        # template properties
        template_props = self._params.get("properties", {})
        if template_props:
            local_context.update(template_props)
        local_context['template_name'] = self.template.name

        return local_context

    def setup_items(self, context, input_items):
        # filter the item list if requested
        apply_item_filter = context.get("apply_item_filter", False)
        if apply_item_filter:
            items = self.filter_items(input_items, context)
        else:
            items = input_items

        # Skip if no data items option
        if self.skip_empty(items):
            return None

        # sort the items (if need be)
        rules = self._params.get("sort_fields", [])
        if rules:
            items = TemplateEngine.sort_items(rules, items)

        # first, last, all selection
        sort_selection = self._params.get("sort_selection", "all")
        if sort_selection == 'first':
            items = items[:1]
        elif sort_selection == 'last':
            items = items[-1:]

        return items

    def setup_template(self, context, input_items):
        ctx = self.setup_context(context)
        return ctx, self.setup_items(ctx, input_items)

    def _render(self, input_items, context, apply_item_filter=True, **kwargs):
        return ""

    def render(self, input_items, context, apply_item_filter=True, **kwargs):
        # if trying to export, return an error
        if TemplateEngine.get_print_style() is not None:
            return get_unsupported_error_html('PPTX templates', TemplateEngine.get_print_style())
        try:
            return self._render(input_items, context, apply_item_filter, **kwargs)
        except Exception as e:
            return get_render_error_html(e, target='report', guid=self.template.guid)


class PPTXTemplateEngine(PPTXBaseTemplateEngine):
    """
    Generate a pptx file of items from an input file.
    """

    @classmethod
    def report_type(cls):
        return "Layout:pptx"

    def add_child(self, engine):
        # restrict to slide children for now.
        if not isinstance(engine, PPTXSlideTemplateEngine):
            raise Exception(f"PPTX Layout templates can only have children which are PPTX Slide Layout templates.")
        super().add_child(engine)

    @staticmethod
    def _convert_to_query(input_string):
        query = ""
        if input_string:
            # if its already a query
            if input_string.startswith("query="):
                query = input_string.replace("query=", "")
            else:  # straight-up name match
                query = f"A|i_name|eq|{input_string};"
        return query

    def _init_manager(self, ctx):
        from ..data.models import Item
        # get input pptx
        input_filename = self.get_default(ctx, 'input_pptx')
        # get the input item
        if not input_filename:
            raise Exception("PPTXTemplate does not have an input pptx file.")
        # get item
        input_file_item = Item.find(ctx['request'],
                                    query=self._convert_to_query(input_filename),
                                    sort_tag='date',
                                    reverse=1).first()
        if not input_file_item:
            raise Exception(f"The input pptx file item '{input_filename}' does not exist.")
        # get file
        input_file = input_file_item.get_payload_server_pathname()
        if not input_file.endswith(".pptx"):
            raise Exception(f"The input pptx file '{input_filename}' is not of the .pptx type.")

        # instantiate manager
        return PPTXManager(input_file)

    def render_pptx(self, input_items, context, apply_item_filter=True, **kwargs):
        context["apply_item_filter"] = apply_item_filter
        # filter and apply context
        ctx, items = self.setup_template(context, input_items)
        # skip if necessary
        if items is None:
            return b""

        try:
            pptx_mgr = self._init_manager(ctx)
            if not len(pptx_mgr.slides):
                raise Exception(f"The input pptx file does not have any slides")
            # generator returns file bytestream
            pptx_generator = PPTXGenerator(pptx_mgr)
            pptx_generator.generate_report(self, items, ctx)
            return pptx_generator.get_report_content()
        except Exception as e:
            raise Exception(f"PPTX render error: Failed to render the template '{self.name}': {e}")

    def _render(self, input_items, context, apply_item_filter=True, **kwargs):
        context["apply_item_filter"] = apply_item_filter
        # filter and apply context
        ctx = self.setup_context(context)
        # validate
        self._init_manager(ctx)
        # get output path
        default_output_filename = f"{self.name}_{uuid.uuid1()}.pptx"
        out_file = self.get_default(ctx, 'output_pptx', default=default_output_filename)
        if not out_file.endswith(".pptx"):
            raise Exception("The output filename is not of the .pptx type.")
        # CAVEAT: will not inherit items if used as a child template
        # todo: pass item filter as query into URL somehow.
        request = context["request"]
        q_dict = request.GET.copy()
        if self.parent is not None:
            query = q_dict.get("query", "")
            q_dict.clear()
            q_dict["view"] = self.template.guid
            q_dict["query"] = query
        # specify format for targeted rendering.
        q_dict["format"] = "pptx"
        q_dict["filename"] = out_file
        # return a url to a REST API that renders it as a downloadable file.
        url = f"{request.scheme}://{request.get_host()}{reverse('report_gen_api')}?{q_dict.urlencode(safe='/')}"
        # return html
        return f"""
                <p class="p-3 m-3">
                    <em>Exported pptx :</em>
                    <a class="btn btn-link" href="{url}" download="{out_file}">Download {out_file}</a>
                </p>
        """


# register it with the core
TemplateEngine.register(PPTXTemplateEngine)


class PPTXSlideTemplateEngine(PPTXBaseTemplateEngine):
    """
    Generate a pptx slide from a template.

    NOTE: Unlike other templates that render and return HTML,
    PPTX Slide Layout templates are used to represent a slide
    in a PPTX file and to get properties and filters specified
    by the user to build the parent PPTX Layout template (above).
    Hence, use of the render() method has been avoided here.
    """

    @classmethod
    def report_type(cls):
        return "Layout:pptxslide"

    def add_child(self, engine):
        # restrict to slide children for now.
        if not isinstance(engine, PPTXSlideTemplateEngine):
            raise Exception(f"PPTX Slide Layout templates can only have children which are other PPTX Slide Layout"
                            f" templates.")
        super().add_child(engine)

    def set_parent(self, parent):
        # restrict parents
        if not isinstance(parent, PPTXTemplateEngine | PPTXSlideTemplateEngine):
            raise Exception("PPTX Slide Layout templates can only be used as children of PPTX Layout templates"
                            " or other PPTX Slide Layout templates.")
        super().set_parent(parent)

    def _render(self, input_items, context, apply_item_filter=True, **kwargs):
        # this method is never actually called unless someone is trying to render
        # as HTML, which is not supported.
        raise Exception("PPTX Slide Layout templates can only be rendered as children of PPTX Layout templates"
                        " or other PPTX Slide Layout templates.")


# register it with the core
TemplateEngine.register(PPTXSlideTemplateEngine)
