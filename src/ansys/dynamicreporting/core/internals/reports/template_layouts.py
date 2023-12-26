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
import math
import os
import re
import uuid

import numpy
from ceireports.utils import get_render_error_html, get_unsupported_error_html
from data.conditional_format import ConditionalFormatting
from data.extremely_ugly_hacks import safe_unpickle
from data.templatetags.data_tags import split_quoted_string_list
from data.utils import decode_table_data, get_unique_id
from django.template.loader import render_to_string
from django.urls import reverse

from .engine import LayoutEngine, TemplateEngine, context_macros
from .pptx_gen import PPTXGenerator, PPTXManager


class BasicTemplateEngine(LayoutEngine):
    '''Template output handler for the 'basic' report type'''

    ''' Attributes in _params (all inherited by other classes):
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
    '''Template output handler for the 'box' report type.  If passed items, it will handle them as the
    default template.  If passed template children, they will be rendered in boxes defined in the properties.'''

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


# Carousel Layout
class CarouselTemplateEngine(LayoutEngine):
    '''Template that pushes out items in carousel form
    This template can only render children.  If passed any templates,
    they will be rendered instead.
    '''

    ''' Attributes in _params:
    animate - If non-zero, the carousel will animate at this rate.  The number is in msec.
    '''

    def __init__(self, template_object):
        super().__init__(template_object)

    @classmethod
    def report_type(cls):
        return "Layout:carousel"

    @context_macros
    def render_template(self, items, context, **kwargs):
        if len(self.children):
            return super().render_template(items, context, **kwargs)

        # ok, render all items...
        # parameters
        try:
            msec = int(self._params.get('animate', 0))
        except:
            msec = 0
        try:
            maxdots = int(self._params.get('maxdots', 0))
        except:
            maxdots = 0
        # here we go...
        s = self.parse_HTML(context)
        s += self.parse_comments(context)
        name = 'carousel_template_' + str(TemplateEngine.get_unique_number(context))
        if msec > 0:
            s += f'<div id="{name}" class="carousel slide" data-ride="carousel" data-interval="{str(msec)}">\n'
        else:
            s += f'<div id="{name}" class="carousel slide" data-ride="carousel" data-interval="false">\n'

        if len(items) < maxdots:
            s += '<ol class="carousel-indicators">\n'
            for idx in range(len(items)):
                s += f'<li data-target="#{name}" data-slide-to="{str(idx)}"'
                if idx == 0:
                    s += ' class="active"'
            s += '></li>\n</ol>\n'

        s += '<div class="carousel-inner">\n'
        for idx, item in enumerate(items):
            if idx == 0:
                s += '<div class="carousel-item active">\n'
            else:
                s += '<div class="carousel-item">\n'
            # Unclear why this is actually needed.  Item text should be legal utf-8 by definition...
            try:
                s += item.render(context)
            except Exception as e:
                s += get_render_error_html(e, target='item', guid=item.guid)
            s += '</div>\n'
        s += '</div>\n'

        s += f"""<a class="carousel-control-prev" href="#{name}" role="button" data-slide="prev" \n
                    style="background-image:none">\n
                    <span class="fas fa-chevron-left" aria-hidden="true"></span>\n
                    <span class="sr-only">Previous</span>\n
                </a>\n
                <a class="carousel-control-next" href="#{name}" role="button" data-slide="next" \n
                    style="background-image:none">\n
                    <span class="fas fa-chevron-right" aria-hidden="true"></span>\n
                    <span class="sr-only">Next</span>\n
                </a>\n
                """

        s += "<script>$('#" + name + \
             "').bind('slide.bs.carousel', function (e) { window.dispatchEvent(new Event('resize')); });</script>\n"
        s += '</div>\n'
        return s


# register it with the core
TemplateEngine.register(CarouselTemplateEngine)


# Iterator layout
class IteratorTemplateEngine(LayoutEngine):
    '''Template output handler for the 'iterator' report type'''

    @classmethod
    def report_type(cls):
        return "Layout:iterator"

    @context_macros
    def render_template(self, items, context, **kwargs):
        # Parameters
        tag = self._params.get('tag')
        # template editor. Possibility for mismatch.
        sort = self._params.get('sort', True)
        sort_reverse = self._params.get('reverse_sort', False)
        secondary_tag = self._params.get('secondary_tag', "")

        # Sort our items based on their tag
        if sort:
            items.sort(key=lambda i: i.search_tag(tag), reverse=sort_reverse)

        # Group the items by tag value.
        from collections import defaultdict
        groups = defaultdict(list)
        values = []
        for item in items:
            value = item.search_tag(tag)
            groups[value].append(item)
            if value not in values:
                values.append(value)

        # If we have a secondary sorting tag, sort each group by it.
        if secondary_tag:
            for value in values:
                groups[value].sort(key=lambda i: i.search_tag(secondary_tag))

        # Time to render
        s = "<div>\n"
        # some debug output
        if context.get("iterator_debug", None):
            s += str(self._params)
            s += '<p>The iterator will iterate over tag "%s".</p>' % tag
            if sort:
                s += '<p>The iterator will sort the items.</p>'
                if sort_reverse:
                    s += '<p>The sorting will be reversed.</p>'
            else:
                s += '<p>The iterator will not sort the items.</p>'

            if secondary_tag:
                s += '<p>The iterator will sort each group by secondary tag "%s".</p>' % secondary_tag

            s += "<p>This Iterator has %d items and %d template children</p>\n" % (len(items), len(self.children))

        # build up the child_item_context_blocks array of tuples (each tuple is a "cell" in this object's
        # column layout.
        child_item_context_blocks = list()
        layout_children = self.get_child_layouts()
        for value in values:
            # If we have children, pass the set of items to the children in turn.
            # If we don't, just ask our items to render themselves.
            group_items = groups[value]
            if context.get("iterator_debug", None):
                s += "Value = %s" % value
            local_context = copy.copy(context)
            local_context['iterator_value'] = str(value)
            if len(layout_children):
                child_item_context_blocks.append((layout_children, group_items, local_context))
            else:
                child_item_context_blocks.append((group_items, group_items, local_context))
        s += super().render_template(items, context, child_item_context_blocks=child_item_context_blocks, **kwargs)
        s += "</div>\n"
        return s


# register it with the core
TemplateEngine.register(IteratorTemplateEngine)


# Panel layout
class PanelTemplateEngine(LayoutEngine):
    '''Similar to the basic template, but places output in a panel with HTML contents in a header'''

    @classmethod
    def report_type(cls):
        return "Layout:panel"

    def block_header(self, items, context):
        style = self.get_margin_style(context)
        background = self.get_colorize_color()
        if background:
            style += background
        if len(style):
            style = 'style="{}"'.format(style)
        # panel block or callout
        template_div_id = f'{str(self.template.guid)}_{str(TemplateEngine.get_unique_number(context))}'
        opt = self._params.get('style', 'panel')
        out = self.get_margin_linebreak(context)
        panel_template_toggle = self.get_default(context, 'panel_template_toggle', 0, force_int=True)
        if TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF:  # If printing pdf, suppress expansion GUI
            panel_template_toggle = 0
        if panel_template_toggle == 1:
            out += f'<span class="panel-expander fas fa-minus" data-target-panel="#{template_div_id}-card-body">' \
                   f'</span>\n'
        if opt == 'panel':
            out += f'<div class="card" id="{template_div_id}" {style}>\n'
            # Raw HTML in the header
            s = self.parse_HTML(context)
            s += self.parse_comments(context)
            if s:
                out += '<div class="card-header">' + s + '</div>\n'
            # body
            out += f'<div class="card-body" id="{template_div_id}-card-body" {style}>\n'
        elif opt.startswith('callout'):
            out += f'<div class="bs-callout bs-{opt}" id="{template_div_id}" {style}>\n'
            # Raw HTML in the header
            s = self.parse_HTML(context)
            s += self.parse_comments(context)
            if s:
                out += '<div class="card-header">' + s + '</div>\n'
        return out

    def block_trailer(self, items, context):
        # panel block or callout
        opt = self._params.get('style', 'panel')
        out = ''
        if opt == 'panel':
            out = '</div>\n'
            out += '</div>\n'
        elif opt.startswith('callout'):
            out = '</div>\n'
        return out


# register it with the core
TemplateEngine.register(PanelTemplateEngine)


# Tag properties
class TagPropertyTemplateEngine(LayoutEngine):
    '''For items selected by the filter this template does one thing:
    (1) convert all of their tags into properties on the context
    then it passes all items to the child templates with the updated context'''

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


# link to another report using the filter as the filter for the report
class ReportLinkTemplateEngine(LayoutEngine):
    """
    This template provides three basic functions:
    1) it can generate a link to another report using item filter provided by this template
       as the initial search for the linked report.  In this mode, the linked template can be
       in a new web-page or embedded in an iframe in the current report.  In any case, the URL
       generated for the linked report will include the item filtering applied by this template
       instance.
    2) it can link to a 'service' instance.  The resulting service provides its own HTML skin
       to be rendered into an inline iframe or new web page.  The link can be displayed as an
       image button.  Any items coming into this template will not be filtered, but any image
       item will be used as the button image and any file items will be passed to the service
       instance.
    3) a "soft-link" to another template.  In this mode, the linked template will be treated
       the same as a child of this template.  Note: item filtering will be applied in this
       case.
    """

    def __init__(self, template_object):
        super().__init__(template_object)

    @classmethod
    def report_type(cls):
        return "Layout:reportlink"

    def get_target_template(self):
        report_guid = self._params.get("report_guid", "")
        if len(report_guid) > 0:
            report = self.template.find_guid(report_guid)
            return report
        return None

    def is_soft_link(self, context):
        # this is a little ugly as it is called by self.render() where the context
        # does not yet have the template properties merged into it...
        tmp = self.get_default(context, 'link_type', 3, force_int=True)
        # now override with any local property setting...
        local_properties = self._params.get("properties", dict())
        tmp = local_properties.get('link_type', tmp)
        try:
            link_type = int(tmp)
        except:
            link_type = 3
        return link_type == -1

    def render(self, input_items, context, **kwargs):
        # Soft-link to another template...
        report = self.get_target_template()
        if report and self.is_soft_link(context):
            engine = report.get_engine()
            self.add_child(engine)
            return super().render(input_items, context, **kwargs)
        # suppress the item filter application by the base class
        return super().render(input_items, context, apply_item_filter=False, **kwargs)

    @context_macros
    def render_template(self, input_items, context, **kwargs):
        # if trying to export linked templates, return an error
        if TemplateEngine.get_print_style():
            return get_unsupported_error_html('linked reports', TemplateEngine.get_print_style())

        # Soft-link to another template...
        report = self.get_target_template()
        if report and self.is_soft_link(context):
            return super().render_template(input_items, context, **kwargs)

        # build or embed a report as a link/iframe
        html = "<div>"
        # Common features and basic structure tags
        name = 'report_link_div_{}'.format(str(TemplateEngine.get_unique_number(context)))
        framename = 'report_frame_{}'.format(str(TemplateEngine.get_unique_number(context)))
        loadername = 'report_loader_{}'.format(str(TemplateEngine.get_unique_number(context)))
        buttonname = 'report_btn_' + str(TemplateEngine.get_unique_number(context))

        # button height (0=default, -1=button height, >0=fixed height
        link_proxy_height = self.get_default(context, "link_proxy_height", 0, force_int=True)

        # button type (and inline/new tab/window)
        link_type = self.get_default(context, 'link_type', 3, force_int=True)
        local_context = copy.copy(context)

        # 3 and higher are all inline cases (iframes)
        if link_type >= 3:
            local_context['usemenus'] = 'off'

        # we can be hosting a "service" (noVNC) or a report "ADR template"
        size_attribute = None
        base_url = ""
        service_name = self.get_default(context, "service_name", '')
        if len(service_name) > 0:
            # build up the URL for the service
            base_url = reverse('remote_applet_run')
            base_url += "?applet_name={}".format(service_name)
            # find any potential target file object
            # simple, image button
            for item in input_items:
                if item.type == 'file':
                    base_url += "&applet_target={}".format(item.guid)
                    break
            # GUI skin
            service_skin = self.get_default(context, "service_skin", '')
            if len(service_skin) > 0:
                base_url += "&applet_skin={}".format(service_skin)
            # Forced size
            service_size = self.get_default(context, "service_size", '')
            if len(service_size) > 0:
                try:
                    tmp = service_size.split('x')
                    tmp_w = int(tmp[0])
                    tmp_h = int(tmp[1])
                    if (tmp_w > 10) and (tmp_h > 10):
                        base_url += "&applet_size={}x{}".format(tmp_w, tmp_h)
                except:
                    size_attribute = "&applet_size="
            else:
                # we need to add the size to the URL (at runtime)
                size_attribute = "&applet_size="
            # Button text
            link_text = self.get_default(context, "link_text", service_name)
        else:
            # Build up the target URL for a sub-report
            report = self.get_target_template()
            if report:
                # Button text
                link_text = self.get_default(context, "link_text", report.name)
                report_filter = self.template.item_filter
                base_url = report.get_display_url(query=report_filter, context=local_context)

        if len(base_url) == 0:
            # TODO Error message about not being able to find the template target
            pass
        else:
            # 1 and 2 are simple buttons in the same page or a new tab
            if link_type == 2:
                html += f"""<div class="row mb-1 justify-content-start">\n
                                <a href="{base_url}" target="_blank">{link_text}</a>\n
                            </div>\n"""
            elif link_type == 1:
                html += f"""<div class="row mb-1 justify-content-start">\n
                                <a href="{base_url}" target="_self">{link_text}</a>\n
                            </div>\n"""
            elif link_type >= 3:
                # button
                script = "var fr=document.getElementById('{}');\n".format(framename)
                script += "var btn=document.getElementById('{}');\n".format(buttonname)
                script += "var ldr=document.getElementById('{}');\n".format(loadername)
                script += "var url = '{}';".format(base_url)
                if size_attribute is not None:
                    script += "url+='{}'+fr.parentNode.offsetWidth+'x'+fr.parentNode.offsetHeight;\n".format(
                        size_attribute)
                script += "btn.style.display='none';\n"
                script += "ldr.style.display='block';\n"
                script += "fr.style.display='block';\n"
                script += "document.getElementById('{}').src=url;\n ".format(framename)
                # link type 4 or 5 places the image from the first incoming image object in the button
                done = False
                if link_type == 5:
                    # simple, image button
                    for item in input_items:
                        if item.type == 'image':
                            style = 'style="margin: 0 auto; cursor: pointer;"'
                            style += ' class="img img-fluid"'
                            html += '<img id="{}" {} onclick="{}" src="{}"/>\n'.format(buttonname, style, script,
                                                                                       item.get_payload_file_url())
                            done = True
                            break
                if not done:
                    # this is a button that may have link text &| an image
                    button_style = 'style="float:left;" class="btn btn-space"'
                    # type 4 has an image
                    if link_type == 4:
                        for item in input_items:
                            if item.type == 'image':
                                link_text = '<img class="img img-fluid" src="{}">{}</img>'.format(
                                    item.get_payload_file_url(), link_text)
                                button_style = 'class="btn btn-space"'
                                break
                    html += '<button id="{}" {} onclick="{}">{}</button>\n'.format(buttonname, button_style,
                                                                                   script, link_text)
                # loader...
                html += '<div id="{}" style="display:none;">\n'.format(loadername)
                html += '<div style="float:left;" class="cei_loader"></div>\n'
                html += '<div><h4>&nbsp;&nbsp;Loading...</h4></div></div>\n'
                # iframe
                attrs = "allowfullscreen allowTransparency='false' scrolling='no' frameborder='0' "
                attrs += "style='width:100%; height:10px; display:none; margin:0;'"
                load_script = "var fr=document.getElementById('{}');\n".format(framename)
                load_script += "var btn=document.getElementById('{}');\n".format(buttonname)
                load_script += "document.getElementById('{}').style.display='none';\n".format(loadername)
                # load_script += "console.log('fbsh ' + fr.contentWindow.document.body.scrollHeight);\n"
                # load_script += "console.log('fboh ' + fr.contentWindow.document.body.offsetHeight);\n"
                # load_script += "console.log('desh ' + fr.contentWindow.document.documentElement.scrollHeight);\n"
                # load_script += "console.log('deoh ' + fr.contentWindow.document.documentElement.offsetHeight);\n"
                load_script += "if (fr.src.length == 0) {\n"
                load_script += "    fr.btn_height = btn.height;\n"
                load_script += "    return;\n"
                load_script += "};\n"
                if link_proxy_height == -1:
                    load_script += "fr.style.height=fr.btn_height + 'px';"
                elif link_proxy_height > 0:
                    load_script += "fr.style.height={}+'px';".format(link_proxy_height)
                else:
                    load_script += "fr.style.height=fr.contentWindow.document.documentElement.scrollHeight+'px';"
                html += "<iframe id='{}' {} onload=\"{}\"></iframe>\n".format(framename, attrs, load_script)
            else:
                html += '<a href="{}" style="float:left;">{}</a>\n'.format(base_url, link_text)
        html += "</div>"
        return html


# register it with the core
TemplateEngine.register(ReportLinkTemplateEngine)


# Tab layout
class TabTemplateEngine(LayoutEngine):
    '''Render all child templates in individual tabs'''

    def __init__(self, template_object):
        super().__init__(template_object)

    @classmethod
    def report_type(cls):
        return "Layout:tabs"

    @context_macros
    def render_template(self, items, context, **kwargs):
        # walk the children or items
        layout_children = self.get_child_layouts()
        if layout_children:
            out_list = layout_children
        else:
            out_list = items
        # inline or tabs
        # tabs by default
        inline = self.get_default(context, "inline_tabs", default=0, force_int=True)
        if TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF:
            inline = 1
        # here we go...
        s = self.parse_HTML(context)
        s += self.parse_comments(context)
        name = 'tab_template_' + str(TemplateEngine.get_unique_number(context))
        # build the tabs
        if inline == 0:
            s += '<div>\n'
            s += '<ul id="' + name + '" class="nav nav-tabs" data-tabs="' + name + '">\n'
        out_div_ids = list()
        for idx, template in enumerate(out_list):
            # if the child layout would be skipped, we need to know now...
            if layout_children:
                if template.skip_empty(template.filter_items(items, context)):
                    out_div_ids.append(None)
                    continue
            div_id = name + "_" + str(TemplateEngine.get_unique_number(context))
            out_div_ids.append(div_id)
            if inline == 0:
                active = ''
                aria_selected = "false"
                # first pane
                if idx == 0:
                    active = 'active'
                    aria_selected = "true"

                s += f'<li class="nav-item"> ' \
                     f'<a class="nav-link {active}" href="#{div_id}" ' \
                     f'data-toggle="tab" role="tab" aria-selected="{aria_selected}" ' \
                     f'aria-controls="{div_id}">' \
                     f'{template.name}</a>' \
                     f'</li>\n'
        if inline == 0:
            s += '</ul>\n'
            s += '<div class="tab-content">\n'
        for idx, (i, div_id) in enumerate(zip(out_list, out_div_ids)):
            if div_id is None:
                continue

            div_class = ""
            div_role = ""
            if inline == 0:
                div_class = 'class="tab-pane"'
                div_role = 'role="tabpanel"'
                # first panes only
                if idx == 0:
                    div_class = 'class="tab-pane show active"'

            s += f'<div {div_class} id="{div_id}" {div_role}>\n'

            if self.children:
                s += i.render(items, context)
            else:
                try:
                    s += i.render(context)
                except Exception as e:
                    s += get_render_error_html(e, target='item', guid=i.guid)
            s += '</div>\n'
        if inline == 0:
            s += '</div>\n'
        s += '</div>\n'
        if inline == 0:
            s += "<script>\n$('a[data-toggle=\"tab\"]').on('shown.bs.tab', function(e) {\n" + \
                 " window.dispatchEvent(new Event('resize'));\n});\n</script>\n"
        return s


# register it with the core
TemplateEngine.register(TabTemplateEngine)


# Tab layout
class TOCTemplateEngine(LayoutEngine):
    '''Compute and insert the table of contents, list of figures and list of tables'''

    @classmethod
    def report_type(cls):
        return "Layout:toc"

    @context_macros
    def render_template(self, items, context, **kwargs):
        # start with the layout engine default
        s = super().render_template(items, context, **kwargs)
        # select the type of TOC to insert a div for...
        if self._params.get('TOCitems', 0):
            unique_id = "TOC_item_list_{}".format(TemplateEngine.get_unique_number(context))
            s += "<div id='{}'></div>".format(unique_id)
            TemplateEngine.toc_itemlist_divs.append(unique_id)
        if self._params.get('TOCfigures', 0):
            unique_id = "TOC_figure_list_{}".format(TemplateEngine.get_unique_number(context))
            s += "<div id='{}'></div>".format(unique_id)
            TemplateEngine.toc_figurelist_divs.append(unique_id)
        if self._params.get('TOCtables', 0):
            unique_id = "TOC_table_list_{}".format(TemplateEngine.get_unique_number(context))
            s += "<div id='{}'></div>".format(unique_id)
            TemplateEngine.toc_tablelist_divs.append(unique_id)
        # these div's will get filled in later by javascript...
        return s


# register it with the core
TemplateEngine.register(TOCTemplateEngine)


class SliderTemplateEngine(LayoutEngine):
    '''Use Javascript tied to a slider to page in image payload contents for items'''

    def __init__(self, template_object):
        super().__init__(template_object)

    @classmethod
    def report_type(cls):
        return "Layout:slider"

    @context_macros
    def render_template(self, items, context, **kwargs):
        # get the list of keys to turn into sliders
        slider_tags = self._params.get('slider_tags', "")
        tags_and_rules = {}  # k,v pairs of tag names and sort rules
        tags_and_values = {}  # k,v pairs of tag names and set of all unique tag values from given item list.
        for tag_with_rule in split_quoted_string_list(slider_tags):
            if "|" in tag_with_rule:
                tag, sort_rule = tag_with_rule.split("|")
                if tag and sort_rule:
                    # init here. set ensures uniqueness
                    tags_and_values[tag] = set()
                    # add tag + rule data
                    tags_and_rules[tag] = sort_rule

        # deep image comparison
        deep_image_comparison = self.get_default(context, "deep_image_comparison", 0, force_int=True) == 1
        has_deep_image = False
        # build of a map of a combination of item tag values and corresponding images
        slider_image_map = {}
        # sometimes there can be more than one matching image for a combination,
        # so we use this to track (for all images globally).
        has_multiple_values = False
        # filter images out while also filling tags_and_values and slider_image_map at the same time
        images = []
        for item in items:
            if item.type == 'image':
                # add to images list
                images.append(item)
                # now search and pick up all possible tag values
                tag_values = []
                for tag in tags_and_values.keys():
                    tag_value = item.search_tag(tag)
                    if tag_value is not None:
                        tag_values.append(str(tag_value))
                        # add to set
                        tags_and_values[tag].add(tag_value)
                # Now build a map of possible slider position
                # combinations and their corresponding images
                # eg: {'2.0_plastic_solid': {'/a.img',} ...}
                slider_key = "_".join(tag_values)
                media_payload_url = item.get_payload_file_url()
                # disable deep image comparison if even one of them is not a tif.
                if os.path.splitext(media_payload_url)[1].lower() not in (".tif", ".tiff"):
                    deep_image_comparison = False
                else:
                    has_deep_image = True
                if slider_key in slider_image_map:
                    slider_image_map[slider_key].add(media_payload_url)
                    has_multiple_values = True
                else:
                    # init if not available
                    slider_image_map[slider_key] = {media_payload_url}

        image_comparison = self.get_default(context, "image_comparison", 0, force_int=True) == 1
        rgb_diff_comparison = self.get_default(context, "rgb_diff_comparison", 0, force_int=True) == 1
        # if trying to print HTML while using deep images, output error message.
        html_export = TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.HTML
        if html_export and has_deep_image:
            return get_unsupported_error_html('deep image sliders', TemplateEngine.PrintStyle.HTML)

        # parse HTML stored in params if any.
        html = self.parse_HTML(context)
        html += self.parse_comments(context)
        # if no images, we are done
        if not images:
            html += f"\n<div class='container mx-auto text-center'>\n"
            html += f"<p><b>No images selected for slider template '{self.name}'.  No display generated.</b></p>"
            html += "</div>\n"
            return html

        # get each sort rule and sort tag values appropriately.
        for tag, sort_rule in tags_and_rules.items():
            values = tags_and_values[tag]
            try:
                # type coercion according to the start of the rule string
                if sort_rule.startswith('numeric'):
                    values = [(float(value), value) for value in values]
                else:  # if its not numeric, its text -- default
                    values = [(str(value), value) for value in values]
                # 3. The actual sort rule.
                values = sorted(values, reverse=sort_rule.endswith('down'))
            except ValueError:
                values = [(value, value) for value in values]
            # note that sorting will cast the set to a list(to preserve sort order).
            # Also type coercion was only for sorting, so str 'em and set back.
            tags_and_values[tag] = [str(value[1]) for value in values]

        # tag names for other operations
        tags = list(tags_and_values.keys())

        slider_sections = []
        unique_id = TemplateEngine.get_unique_number(context)
        name = 'slider_template_' + str(unique_id)

        slider_section_1 = {
            'name': name,
            'unique_id': unique_id,
        }

        slider_xaxis_tag = None
        slider_yaxis_tag = None
        slide_xaxis_tag_index = None
        slide_yaxis_tag_index = None

        # header goes below the image
        # Note: there is an issue here where if the values in 'tags' are in the context, they will
        # be resolved right now, instead of at runtime. ignore_tags solves this.
        image_title = str(self.get_default(context, "image_title", "", ignore_tags=tags))

        # should the bars have text columns?
        value_width = self.get_default(context, "slider_title_width", 30, force_int=True)
        if value_width < 0:
            value_width = 0
        if value_width > 90:
            value_width = 90
        bar_width = 100 - value_width

        # get the justification
        slider_title_justification = self.get_default(context, "slider_title_justification", "left")

        common_slider_tags = []
        if image_comparison:
            common_slider_setting = self.get_default(context, "common_slider_tags", "")
            if common_slider_setting:
                for tag in common_slider_setting.strip("[]").split(","):
                    tag = tag.strip()
                    if tag:
                        common_slider_tags.append(tag)

        # controls - pan,zoom,etc.
        image_controls = self.get_default(context, "image_controls", 0, force_int=True) == 1

        # get axis tags before building slider_info
        if not image_controls and not image_comparison:
            # get the names of tags to be used for X & Y axis interaction as well as scaling
            slider_xaxis_tag = self.get_default(context, 'slider_xaxis_tag', "")
            slider_yaxis_tag = self.get_default(context, 'slider_yaxis_tag', "")

        slider_info = {}
        slider_titles = []
        # the sliders might start at some specific value...
        start_value_indices = []
        for idx, tag in enumerate(tags):
            slider_title = self.get_indexed_default(context, idx, "slider_title", default="{{%s}}" % tag,
                                                    ignore_tags=tags)
            slider_titles.append(slider_title)

            initial_value = self.get_indexed_default(context, idx, "initial_values", default=None)
            start = 0  # the index of the initial value for a slider, obtained from the list of available values.
            if initial_value is not None:
                # valid?
                if initial_value in tags_and_values[tag]:
                    start = tags_and_values[tag].index(initial_value)
            start_value_indices.append(start)

            # the tag that clicking and dragging on the image in the x axis will change the value for.
            # No slider will be displayed for this tag
            if tag == slider_xaxis_tag:
                slide_xaxis_tag_index = idx
                continue
            elif tag == slider_yaxis_tag:
                # the tag that clicking and dragging on the image in the y axis will change the value for.
                # No slider will be displayed for this tag
                slide_yaxis_tag_index = idx
                continue

            tag_info = {
                'index': idx,
                'start': start,
                'max': len(tags_and_values[tag]) - 1,
                'values': tags_and_values[tag]
            }

            show_nodes = self.get_indexed_default(context, idx, "show_nodes", default=0)
            try:
                show_nodes = int(show_nodes)
            except ValueError:
                show_nodes = 0
            if show_nodes == 1:
                tag_info['ticks'] = str(list(range(len(tags_and_values[tag]))))

            slider_info[tag] = tag_info

        slider_section_1.update({
            'image_title': image_title,
            'bar_width': bar_width,
            'value_width': value_width,
            'slider_title_justification': slider_title_justification,
            'slider_info': slider_info,
            'start_value_indices': start_value_indices,
        })

        # template id
        parent_num = TemplateEngine.get_unique_number(context)

        image_scale = ""
        image_class = ""
        image_style = 'style="display: none;"'
        if not image_controls and not image_comparison:
            # allow sizing, styling only if comparison and controls are off.
            img_width = self.get_default(context, "width", 800, force_int=True)
            if img_width > 1:
                image_scale += ' width="{}"'.format(img_width)
            img_height = self.get_default(context, "height", 600, force_int=True)
            if img_height > 1:
                image_scale += ' height="{}"'.format(img_height)
            if not image_scale:
                image_class = 'class="img-fluid"'
            # styling
            image_style = 'style="display: none; margin: 0 auto; justify-content:center;"'

            # enable catchall features.
            # override the catchall slider...
            first_image_only = self.get_default(context, "first_image_only", 0, force_int=True)
            if first_image_only:
                has_multiple_values = False
            slider_section_1.update({
                'has_multiple_values': has_multiple_values,
            })

            # both comparison and controls must be off for link and drag to work.
            # the link...
            image_link = self.get_default(context, 'image_link', 0, force_int=True)
            slider_section_1.update({
                'image_link': image_link
            })

            # image dragging
            slider_xaxis_scale = self.get_default(context, 'slider_xaxis_scale', 1.0, force_float=True)
            slider_yaxis_scale = self.get_default(context, 'slider_yaxis_scale', 1.0, force_float=True)
            slider_xaxis_clamp = self.get_default(context, 'slider_xaxis_clamp', 0, force_int=True)
            slider_yaxis_clamp = self.get_default(context, 'slider_yaxis_clamp', 0, force_int=True)
            if slide_xaxis_tag_index is not None:
                count = len(tags_and_values[slider_xaxis_tag])
                slider_section_1.update({
                    'slide_xaxis_tag_index': slide_xaxis_tag_index,
                    'slide_xaxis_tag_value_count': count,
                    'slider_xaxis_clamp': slider_xaxis_clamp,
                    'slider_xaxis_scale_total': int(math.ceil(slider_xaxis_scale)) * count
                })
            if slide_yaxis_tag_index is not None:
                count = len(tags_and_values[slider_yaxis_tag])
                slider_section_1.update({
                    'slide_yaxis_tag_index': slide_yaxis_tag_index,
                    'slide_yaxis_tag_value_count': count,
                    'slider_yaxis_clamp': slider_yaxis_clamp,
                    'slider_yaxis_scale_total': int(math.ceil(slider_yaxis_scale)) * count
                })
            slider_section_1.update({
                'slider_xaxis_scale': slider_xaxis_scale,
                'slider_yaxis_scale': slider_yaxis_scale,
            })
        else:
            image_class = f'class="img-{parent_num} img-disp-{parent_num}"'

        # scale, style
        slider_section_1.update({
            'image_scale': image_scale,
            'image_class': image_class,
            'image_style': image_style
        })

        if value_width:
            # map of tags and indices to display the titles
            title_tag_indices = []
            for idx, tag in enumerate(tags):
                if tag in common_slider_tags:
                    continue
                if idx == slide_xaxis_tag_index or idx == slide_yaxis_tag_index:
                    continue
                title_tag_indices.append(idx)

            slider_section_1.update({'title_tag_indices': title_tag_indices})

        template_context = {
            'tags_and_values': tags_and_values,
            'slider_titles': slider_titles,
            'slider_image_map': slider_image_map,
            'param_html': html,
            'parent_container_id': f'{str(self.template.guid)}_{TemplateEngine.get_unique_number(context)}',
            'parent_num': parent_num,
            'image_comparison': image_comparison,
            'image_controls': image_controls
        }

        slider_sections.append(slider_section_1)

        if image_comparison:
            # add a second section if comp is on.
            slider_section_2 = copy.deepcopy(slider_section_1)
            unique_id = TemplateEngine.get_unique_number(context)
            name = 'slider_template_' + str(unique_id)
            slider_section_2.update({
                'name': name,
                'unique_id': unique_id
            })

            slider_sections.append(slider_section_2)

            # common slider content
            if common_slider_tags:
                common_sliders = {}
                for tag in common_slider_tags:
                    tag_info = slider_info.get(tag)
                    if tag_info:
                        common_sliders.update({tag: tag_info})

                common_slider_value_width = self.get_default(context,
                                                             "common_slider_title_width",
                                                             20,
                                                             force_int=True)
                if common_slider_value_width < 0:
                    common_slider_value_width = 0
                if common_slider_value_width > 90:
                    common_slider_value_width = 90
                common_slider_bar_width = 100 - common_slider_value_width

                common_slider_title_justification = self.get_default(context,
                                                                     "common_slider_title_justification",
                                                                     "left")

                # add context for common sliders.
                template_context.update({
                    'common_sliders': common_sliders,
                    'common_slider_value_width': common_slider_value_width,
                    'common_slider_bar_width': common_slider_bar_width,
                    'common_slider_title_justification': common_slider_title_justification,
                })

            # get initial_values preset and monkey-patch section/slider info.
            # example:
            # [[3.8,Pressure_absolute],[1.4,Pressure_absolute]]
            sections_initial_values = self.get_default(context, "comparison_initial_values", "")
            if sections_initial_values and (
                    sections_initial_values.startswith('[') and sections_initial_values.endswith(']')
            ):
                sections_initial_values = sections_initial_values.strip('[]')
                # strip all whitespaces
                sections_initial_values = re.sub(r"\s+", "", sections_initial_values)
                # split at ],[
                sections_initial_values = re.split("\\],\\[", sections_initial_values)

                # enumerate list of section-wise values
                for sec_idx, initial_values in enumerate(sections_initial_values):
                    # skip empty values
                    if initial_values == '-':
                        continue
                    # eg: [3.8,Pressure_absolute]
                    initial_values = initial_values.split(',')
                    start_indices = []
                    # match with the available tags
                    for tag_idx, tag in enumerate(tags):
                        # eg: 3.8
                        initial_value = initial_values[tag_idx]
                        start = 0
                        if initial_value is not None:
                            # valid?
                            if initial_value in tags_and_values[tag]:
                                start = tags_and_values[tag].index(initial_value)
                        start_indices.append(start)
                        slider_sections[sec_idx]['slider_info'][tag]['start'] = start

                    slider_sections[sec_idx]['start_value_indices'] = start_indices

            # VIEW constants
            deep_views = {
                'CURRENT': 'this',
                'CURRENT_MINUS_OTHER': 'this-other',
                'OTHER_MINUS_CURRENT': 'other-this',
                'ABSOLUTE_VALUE': 'abs'
            }

            template_context.update({
                'deep_views': deep_views,
                'deep_image_comparison': deep_image_comparison,
            })

            if deep_image_comparison:
                # turn off rgb diff during deep comparison
                rgb_diff_comparison = False

                # initial palettes
                palettes = ConditionalFormatting().palettes
                template_context.update({
                    'color_palettes': dict(sorted(palettes.items())),
                    'default_bg_opacity': 0.1
                })

                section_presets = {}
                # comparison_initial_palettes
                # get initial_palette. These are section-wise palette settings that will be set when the page is loaded.
                # They must follow the order in allowed_palette_presets.
                # example:
                # [[30,-30,autumn,true,true,0.4],[30,-30,autumn,true,true,0.9]]
                comparison_palettes = self.get_default(context, "comparison_initial_palettes", default="")
                if comparison_palettes and (comparison_palettes.startswith('[') and comparison_palettes.endswith(']')):
                    comparison_palettes = comparison_palettes.strip('[]')
                    # strip all whitespaces
                    comparison_palettes = re.sub(r"\s+", "", comparison_palettes)
                    comparison_palettes = re.split('\\],\\[', comparison_palettes)

                    allowed_palette_presets = (
                        'userMax', 'userMin', 'palette',
                        'invertColors', 'hideBG', 'bgOpacity'
                    )
                    # run for each section
                    for idx, preset in enumerate(comparison_palettes):
                        # skip empty values
                        if preset == '-':
                            continue
                        initial_palette = {}
                        presets = preset.split(',')
                        # truncate preset keys based on user-defined list
                        allowed_palette_presets = allowed_palette_presets[:len(presets)]
                        for key_idx, key in enumerate(allowed_palette_presets):
                            value = presets[key_idx]
                            if value and value != '-':
                                initial_palette[key] = value
                        # add to presets
                        if initial_palette:
                            section = slider_sections[idx]['name']
                            if section in section_presets:
                                section_presets[section].update(initial_palette)
                            else:
                                section_presets[section] = initial_palette

                # comparison_initial_vars
                # [Pressure_absolute,Pressure_absolute]
                comparison_vars = self.get_default(context, "comparison_initial_vars", default="")
                if comparison_vars and (comparison_vars.startswith('[') and comparison_vars.endswith(']')):
                    comparison_vars = comparison_vars.strip('[]')
                    comparison_vars = re.sub(r"\s+", "", comparison_vars)  # white spaces
                    for idx, var in enumerate(comparison_vars.split(',')):
                        if var and var != '-':
                            section = slider_sections[idx]['name']
                            if section in section_presets:
                                section_presets[section].update({'var': var})
                            else:
                                section_presets[section] = {'var': var}

                # comparison_initial_views
                # [current-other,current]
                comparison_views = self.get_default(context, "comparison_initial_views", default="")
                if comparison_views and (comparison_views.startswith('[') and comparison_views.endswith(']')):
                    comparison_views = comparison_views.strip('[]')
                    comparison_views = re.sub(r"\s+", "", comparison_views)
                    for idx, view in enumerate(comparison_views.split(',')):
                        if view and view != '-':
                            section = slider_sections[idx]['name']
                            if section in section_presets:
                                section_presets[section].update({'view': view})
                            else:
                                section_presets[section] = {'view': view}

                # add to context
                # dont add if no property is available
                if section_presets:
                    template_context.update({'presets': section_presets})

            template_context.update({
                'rgb_diff_comparison': rgb_diff_comparison,
                'html_export': html_export
            })

        template_context.update({'slider_sections': slider_sections})

        return render_to_string('reports/template_layouts/slider_template.html', template_context)


# register it with the core
TemplateEngine.register(SliderTemplateEngine)


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
        from data.models import Item
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


class DataFilterTemplateEngine(LayoutEngine):
    """
    Gives a filter sidebar on the report to dynamically filter
    data of children items and templates.
    """
    SUPPORTED_ITEM_TYPES = ("line", "table")
    NUMERIC_FILTER_TYPES = ("slider", "input", "dropdown")
    TEXT_FILTER_TYPES = ("checkbox", "single_dropdown")
    ALLOWED_FILTER_TYPES = TEXT_FILTER_TYPES + NUMERIC_FILTER_TYPES
    ALLOWED_RANGE_PARAMS = frozenset({"plot_range_x", "plot_range_y"})

    def __init__(self, template_object):
        super().__init__(template_object)

    @classmethod
    def report_type(cls):
        return "Layout:datafilter"

    @staticmethod
    def _get_range_filters(tables, ctx, filter_params):

        from data.models import Item, XAxisObj
        range_filters = {}
        filter_step = ctx["filter_numeric_step"]

        for table_data in tables:
            np_data = table_data["array"]
            item = table_data["item"]
            num_rows, num_cols = np_data.shape
            row_labels = Item.get_row_labels(table_data, ctx, [None] * num_rows)
            col_labels = Item.get_column_labels(table_data, ctx, list(range(num_cols)))

            xaxis_obj = XAxisObj(ctx, table_data, row_labels, col_labels, item)

            y_data = []
            x_data = []
            y_labels = []
            for idx in xaxis_obj.y_row_indices():
                x_data.append(xaxis_obj.data(idx))
                y_data.append(np_data[idx])
                y_labels.append(row_labels[idx])

            x_values_set = set()
            y_values_set = set()
            for idx, y_val in enumerate(y_data):
                # each iteration is one series
                input_data = []
                # if it is a pie, x values are constant
                if table_data["type"] == "pie":
                    input_data.append(col_labels)
                else:
                    input_data.append(x_data[idx])
                input_data.append(y_val)
                x_values, y_values = item.clean_plot_data(input_data)
                x_values_set.update(set(x_values))
                y_values_set.update(set(y_values))

            # titles
            x_title = item.get_default(table_data, ctx, 'filter_x_title',
                                       default=ctx.get('xtitle', table_data.get('xtitle')))
            y_title = item.get_default(table_data, ctx, 'filter_y_title',
                                       default=ctx.get('ytitle', table_data.get('ytitle')))

            for filter_type, filter_params in filter_params.items():
                for param in filter_params:
                    if param == "plot_range_x":
                        name = x_title
                        values = x_values_set
                    else:
                        name = y_title
                        values = y_values_set

                    filter_data = {
                        "name": name,
                        "type": filter_type,
                        "event_type": param,
                        "min": round(min(values), 1),
                        "max": round(max(values), 1),
                    }
                    if filter_type == "dropdown":
                        filter_data["values"] = sorted(values)
                    else:
                        filter_data["step"] = filter_step
                    range_filters[f"range_{get_unique_id()}"] = filter_data
        return range_filters

    def _get_tag_filters(self, tables, ctx, filter_params):
        # merge
        def _update_dict(dest_dict, src_dict):
            for tag, value in src_dict.items():
                if tag in dest_dict:
                    if value not in dest_dict[tag]:
                        dest_dict[tag].add(value)
                else:
                    dest_dict[tag] = {value, }
            return dest_dict

        # filters
        from data.models import Item

        tag_dict = {}
        for table_data in tables:
            item = table_data["item"]
            col_tags = Item.get_column_tags(table_data, ctx)
            row_tags = Item.get_row_tags(table_data, ctx)
            if row_tags or col_tags:
                row_col_tags = {*row_tags, *col_tags}
                for tag in row_col_tags:
                    tags = Item.get_tag_dict_from_str(tag)
                    tag_dict = _update_dict(tag_dict, tags)
            else:
                tags = Item.get_tag_dict_from_str(item.tags)
                tag_dict = _update_dict(tag_dict, tags)

        filter_step = ctx["filter_numeric_step"]
        tag_filters = {}
        for filter_type, filter_params in filter_params.items():
            if filter_type in self.TEXT_FILTER_TYPES:
                event_type = "tag" if filter_type == "checkbox" else "single_tag"
                misc_tags = []
                # defaults are all tags as checkboxes
                if not filter_params:
                    filter_params = set(tag_dict.keys())
                for tag in filter_params:
                    tag_values = tag_dict.get(tag)
                    if not tag_values:
                        continue
                    # values are bools for key-only/misc tags
                    value = list(tag_values)[0]
                    if isinstance(value, bool):
                        misc_tags.append(tag)
                    else:
                        tag_filters[f"tag_{get_unique_id()}"] = {
                            'name': tag,
                            'type': filter_type,
                            'event_type': event_type,
                            'values': sorted(tag_values),
                        }

                # a separate misc checkbox section for key-only tags
                if misc_tags:
                    tag_filters[f"misc_{get_unique_id()}"] = {
                        'name': 'Other tags',
                        'type': filter_type,
                        'event_type': event_type,
                        'values': sorted(misc_tags),
                    }
            else:
                if not filter_params:
                    continue
                for tag in filter_params:
                    tag_values = tag_dict.get(tag)
                    if not tag_values:
                        continue
                    try:
                        values = sorted([float(val) for val in tag_values])
                    except ValueError as e:
                        raise ValueError(
                            f"{str(e)} : Tag values used with filter type '{filter_type}' must be a number.") from e
                    filter_data = {
                        "name": tag,
                        "type": filter_type,
                        "event_type": "tag",
                        "min": round(min(values), 1),
                        "max": round(max(values), 1),
                    }
                    if filter_type == "dropdown":
                        filter_data["values"] = values
                    else:
                        filter_data["step"] = filter_step
                    tag_filters[f"tag_{get_unique_id()}"] = filter_data

        return tag_filters

    @staticmethod
    def _get_list_from_str(input_str, default=None):
        if input_str:
            if input_str.startswith("[") and input_str.endswith("]"):
                output_list = split_quoted_string_list(input_str[1:-1], delimiter=',')
            else:
                output_list = [input_str]
        else:
            output_list = default or []
        return output_list

    def _get_filters(self, items, ctx):
        """
        Get:
            - tags
            - numeric values (both X & Y separately):
                - min
                - max
                - step (from min/max)
                - range of values from min, max, step
        :param items:
        :return:
        """
        # restrict to one line plot item for now.
        if len(items) > 1:
            raise Exception(f"The item filter has returned {len(items)} items. "
                            "Only one item is currently allowed with Data Filter Layout templates")

        # parse properties
        tag_filter_params = {}
        range_filter_params = {}
        ctx["filter_numeric_step"] = self.get_default(ctx, "filter_numeric_step", force_float=True, default=0.1)
        filter_types_config = self.get_default(ctx, "filter_types")
        filter_types = self._get_list_from_str(filter_types_config, default=[])
        for f_type in filter_types:
            if f_type not in self.ALLOWED_FILTER_TYPES:
                raise Exception(f"'{f_type}' specified in the 'filter_types' property is not a valid type of filter.")
            filter_config = self.get_default(ctx, f"filter_{f_type}")
            filter_params = set(self._get_list_from_str(filter_config, default=[]))
            # skip filters if empty.
            tag_params = filter_params.difference(self.ALLOWED_RANGE_PARAMS)
            if tag_params:
                tag_filter_params[f_type] = tag_params
            range_params = filter_params.intersection(self.ALLOWED_RANGE_PARAMS)
            if range_params:
                if f_type not in self.NUMERIC_FILTER_TYPES:
                    raise Exception(
                        f"'{f_type}' specified in the 'filter_types' property cannot be used for X/Y range filtering.")
                range_filter_params[f_type] = range_params

        # defaults are all tags as checkboxes
        # set() is not populated until tags from items
        # are actually processed later.
        if not tag_filter_params and not range_filter_params:
            tag_filter_params["checkbox"] = set()

        # process items
        tables = []  # todo: includes trees as well
        plots = []  # lines/bars/pies
        for item in items:
            if item.type != "table":
                continue
            item_data = safe_unpickle(item.payloaddata)
            plot_type = ctx.get('plot', item_data.get('plot', 'table'))
            if plot_type not in self.SUPPORTED_ITEM_TYPES:
                raise Exception(f"Invalid type '{plot_type}'. "
                                f"Currently supported types in Data Filter Layout templates are:"
                                f" {', '.join(self.SUPPORTED_ITEM_TYPES)}")
            if item_data["array"].size == 0:
                continue
            # decode
            if item_data["array"].dtype.type == numpy.bytes_:
                item_data = decode_table_data(item_data)
            item_data["item"] = item
            item_data["type"] = plot_type
            # segregate
            if plot_type == "table":
                tables.append(item_data)
            else:
                plots.append(item_data)

        processed_filters = {}
        if tables or plots:
            processed_filters.update(self._get_tag_filters([*tables, *plots], ctx, tag_filter_params))
        # range based filtering is only applicable to plots
        if plots and range_filter_params:
            processed_filters.update(self._get_range_filters(plots, ctx, range_filter_params))

        return processed_filters

    @context_macros
    def render_template(self, items, context, **kwargs):
        if self.get_child_layouts():
            raise Exception("Data Filter Layout templates cannot have children templates nested in them.")

        context["enable_filtering"] = True
        html = super().render_template(items, context, **kwargs)
        template_context = {
            'param_html': html,
            'parent_container_id': f'{str(self.template.guid)}_{TemplateEngine.get_unique_number(context)}',
            'parent_num': TemplateEngine.get_unique_number(context),
        }

        if items:
            template_context["filters"] = self._get_filters(items, context)

        return render_to_string('reports/template_layouts/data_filter_template.html', template_context)


# register it with the core
TemplateEngine.register(DataFilterTemplateEngine)
