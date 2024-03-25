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

from .engine import LayoutEngine, TemplateEngine, context_macros


class BasicTemplateEngine(LayoutEngine):
    '''Template output handler for the 'basic' report type

    Attributes in _params (all inherited by other classes):
    HTML - raw HTML text to insert before iterating on children/items
    column_widths - array of fractional column widths (converted to 12ths before using)
    column_count - number of equal size columns to use (column_widths trumps this)
    transpose - if 1, rotate the input items 90degrees clockwise before placing in cells
    '''

    @classmethod
    def report_type(cls):
        return "Layout:basic"


# register it with the core
TemplateEngine.register(BasicTemplateEngine)


# Page header template: does not really do anything right now
class HeaderTemplateEngine(LayoutEngine):
    '''Template output handler for the 'header' report type'''

    @classmethod
    def report_type(cls):
        return "Layout:header"


# register it with the core
TemplateEngine.register(HeaderTemplateEngine)


# Page footer template
class FooterTemplateEngine(LayoutEngine):
    '''Template output handler for the 'footer' report type'''

    @classmethod
    def report_type(cls):
        return "Layout:footer"

    @context_macros
    def render_template(self, items, context, **kwargs):
        # simple case that avoids the <br> that the normal rendering pipeline injects
        if (len(items) == 0) and (not self._params.get('HTML', '')):
            template_tag = ' nexus_template="{}"'.format(str(self.template.guid))
            s = f'<div {template_tag} style="break-after:page;"></div>\n'
        else:
            s = super().render_template(items, context, **kwargs)
            # insert a page-break (via CSS)
            s += '<div style="break-after:page;"></div>\n'
        # move to the next page number
        TemplateEngine.get_global_context()['page_number'] += 1
        return s


# register it with the core
TemplateEngine.register(FooterTemplateEngine)


# Box layout template
class BoxTemplateEngine(LayoutEngine):
    '''Template output handler for the 'box' report type.
    If passed items, it will handle them as the default template.  If passed
    template children, they will be rendered in boxes defined in the properties.'''

    @classmethod
    def report_type(cls):
        return "Layout:box"

    @context_macros
    def render_template(self, items, context, **kwargs):
        if len(self.children) == 0:
            return super().render_template(items, context, **kwargs)
        s = self.parse_HTML(context)
        s += self.parse_comments(context)
        # boxes is a dictionary keyed by template guids of [x,y,width,height,clipping_rule]
        # clipping_rule is one of: 'self', 'scroll', 'none'
        boxes = self._params.get('boxes', 0)
        # our size is the bounding box of our children
        child_layouts = self.get_child_layouts()
        dx = 0
        dy = 0
        for c in child_layouts:
            child_rect = boxes.get(str(c.template.guid), [0, 0, 320, 240, 'self'])
            dx = max(dx, child_rect[0] + child_rect[2])
            dy = max(dy, child_rect[1] + child_rect[3])
        name = 'box_template_' + str(TemplateEngine.get_unique_number(context))
        style = "width:{0:d}px;height:{1:d}px;".format(int(dx), int(dy))
        background = self.get_colorize_color()
        if background:
            style += background
        s += '<div id="' + name + '" style="padding:0 0;margin:0 0;' + style + '">\n'
        # by default, the browser increments the Y by the size of the div with each step
        # we track the sum of these values so they can be adjusted for with each child.
        prev = 0
        for c in child_layouts:
            child_rect = boxes.get(str(c.template.guid), [0, 0, 320, 240, 'self'])
            child_rect[1] -= prev
            prev += child_rect[3]
            style = "top:{1:d}px;left:{0:d}px;width:{2:d}px;height:{3:d}px;".format(
                int(child_rect[0]), int(child_rect[1]), int(child_rect[2]), int(child_rect[3]))
            if child_rect[4] == 'scroll':
                style += "overflow:scroll;"
            elif child_rect[4] == 'self':
                style += "overflow:hidden;"
            s += '<div style="padding:0 0;margin:0 0;position:relative;' + style + '">\n'
            s += c.render(items, context)
            s += '</div>\n'
        s += '</div>\n'
        return s


# register it with the core
TemplateEngine.register(BoxTemplateEngine)


# Tag properties
class TagPropertyTemplateEngine(LayoutEngine):
    '''For items selected by the filter this template does one thing:
    convert all of their tags into properties on the context then it passes
    all items to the child templates with the updated context'''

    def __init__(self, template_object):
        super().__init__(template_object)
        self._enable_toc_tracking = False

    @classmethod
    def report_type(cls):
        return "Layout:tagprops"

    def render(self, input_items, context, **kwargs):
        # filter the item list...
        items = self.filter_items(input_items, context)

        # sort the items (if need be)
        rules = self._params.get("sort_fields", [])
        if len(rules):
            items = TemplateEngine.sort_items(rules, items)

        # first, last, all selection
        sort_selection = self._params.get("sort_selection", "all")
        if sort_selection == 'first':
            items = items[:1]
        elif sort_selection == 'last':
            items = items[-1:]

        local_context = copy.copy(context)
        # ok, walk the remaining items and push their tags into context properties
        for i in items:
            # force the building of the item tag dictionary
            d = i.build_tag_dictionary()
            for key, value in d.items():
                local_context[key] = value

        # suppress our local filter and sorting operations
        tmp_filter = self.template.item_filter
        self.template.item_filter = ""
        tmp_sort_fields = self._params.get("sort_fields", [])
        self._params["sort_fields"] = []
        tmp_sort_selection = self._params.get("sort_selection", "all")
        self._params["sort_selection"] = "all"

        # do the actual rendering, passing the items on to the rendering engine
        html = super().render(input_items, local_context, **kwargs)

        # put the filter and sorting options back
        self.template.item_filter = tmp_filter
        self._params["sort_fields"] = tmp_sort_fields
        self._params["sort_selection"] = tmp_sort_selection

        return html


# register it with the core
TemplateEngine.register(TagPropertyTemplateEngine)


# Template to wrap user-defined content.
class UserDefinedTemplateEngine(LayoutEngine):
    '''This template generates a <div> that wraps a user-named <div> that an application
    can look for to inject application specific content into the DOM.  Children can be
    rendered before or after this template.  The template may be suppressed in printing/offline
    generation cases.  The inserted div will have the attribute "adr_userdefined_template"
    set to a user specified name after macro expansion (or 'unspecified').
    '''

    def __init__(self, template_object):
        super().__init__(template_object)
        # These local data members make it easier to subclass this template with
        # custom HTML and JavaScript in "serverless" ADR mode.
        self._local_html: str = ""
        self._local_javascript: str = ""

    @classmethod
    def report_type(cls):
        return "Layout:userdefined"

    @property
    def html(self) -> str:
        return self._local_html

    @html.setter
    def html(self, value: str) -> None:
        self._local_html = value

    @property
    def javascript(self) -> str:
        return self._local_javascript

    @javascript.setter
    def javascript(self, value: str) -> None:
        self._local_javascript = value

    @context_macros
    def render_template(self, items, context, **kwargs):
        # override some layout options:
        # - margin_line = 0 - we do not want any boundary
        # - margin_left,right,top,bottom = 0
        # - skip_html = True to avoid rendering user HTML in the template header
        local_context = copy.copy(context)
        local_context.update({"margin_line": 0,
                              "margin_right": 0,
                              "margin_left": 0,
                              "margin_top": 0,
                              "margin_bottom": 0,
                              "skip_html": True})

        # We always render the children, but might skip the user-defined <div>
        display_user_div = True
        interactive_only = self.get_default(local_context, 'interactive_only', 1, force_int=True)
        if interactive_only != 0:
            # If in PPTX/PDF/Export mode, do nothing
            if TemplateEngine.get_print_style():
                display_user_div = False

        before_children = self.get_default(local_context, 'before_children', 0, force_int=True)
        html = ""
        # if before children, do not render the children first
        if before_children == 0:
            html += super().render_template(items, local_context, **kwargs)
        if display_user_div:
            name_value = self.get_default(local_context, 'userdef_name', 'unspecified')
            name_value = TemplateEngine.context_expansion(name_value, local_context)
            html += f'<div adr_userdefined_template="{name_value}">'
            if self._local_html:
                html += self._local_html
            else:
                html += self.parse_HTML(local_context)
            if self._local_javascript:
                html += f"<script type='text/javascript'>\n{self._local_javascript}\n</script>\n"
            html += "</div>\n"
        # if before children, we have rendered the user content, now render the children
        if before_children != 0:
            html += super().render_template(items, local_context, **kwargs)

        return html


# register it with the core
TemplateEngine.register(UserDefinedTemplateEngine)
