#
# *************************************************************
#  Copyright 2021-2023 ANSYS, Inc.
#
#  Unauthorized use, distribution, or
#  duplication is prohibited.
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

import colorsys
import copy
import json
import time

from django.template import engines

from ..data.templatetags.data_tags import convert_macro_slashes, split_quoted_string_list
from ..data.templatetags.data_tags import expand_string_context, expand_dictionary_context
from ..report_framework.utils import get_render_error_html, StrEnum


def context_macros(f):
    def wrapper_context_macros(*args, **kwargs):
        # self, items, context, ...
        # replace {{key}} with value
        # replace {{key|fmt}} with {{value|fmt}}
        ret = f(*args, **kwargs)
        for key, value in args[2].items():
            ret = ret.replace("{{" + str(key) + "}}", str(value))
            ret = ret.replace("{{" + str(key) + "|", "{{" + str(value) + "|")
        return ret

    return wrapper_context_macros


class TemplateEngine:
    """Core object that manages HTML generation"""

    # Class methods ###################################
    #

    # a basic factory mapping a report type (string) to a
    # class that must be a subclass of TemplateEngine
    engine_classes = dict()
    unique_number = -1

    class PrintStyle(StrEnum):
        PDF = 'pdf'
        HTML = 'html'
        PPTX = 'pptx'

    allowed_render_formats = [export_type.value for export_type in PrintStyle]

    class BrowserType(StrEnum):
        EMBEDDED = 'embedded'

    @classmethod
    def factory(cls, template_object):
        # the fallback will be an instance of the TemplateEngine base class
        # the typename should be:  Class:Classname  where Class can be 'Layout' or 'Generator'
        # originally, there were no Class values, so for backward compatibility, we prefix
        # with 'Layout'...
        type_name = template_object.report_type
        if ':' not in type_name:
            type_name = 'Layout:' + type_name
        c = cls.engine_classes.get(type_name, TemplateEngine)
        # return an instance of the engine associated with this template
        return c(template_object)

    @classmethod
    def register(cls, engine_class):
        if engine_class.report_type() in cls.engine_classes:
            return
        cls.engine_classes[engine_class.report_type()] = engine_class

    # Base class report_type (should be overridden by subclasses)
    @classmethod
    def report_type(cls):
        return "unknown"

    # This may need to be revisited, but while only one report can be processed at once, this will work.
    # We store "global" properties on a context hung off of the engine class.
    global_context = dict()

    @classmethod
    def get_global_context(cls):
        return cls.global_context

    @classmethod
    def set_global_context(cls, ctx):
        cls.global_context = ctx

    # The user may have asked for a report to be generated in a printed style.
    # the specific printing style is cached on the TemplateEngine class
    print_style = None

    @classmethod
    def set_print_style(cls, style):
        cls.print_style = style

    @classmethod
    def get_print_style(cls):
        return cls.print_style

    # The target browser may have specialized requirements/specifications
    # the browser type specified in the URL is cached on the TemplateEngine class
    browser_type = None

    @classmethod
    def set_browser_type(cls, browser):
        cls.browser_type = browser

    @classmethod
    def get_browser_type(cls):
        return cls.browser_type

    @classmethod
    def set_unique_number(cls, unique_num, context):
        cls.unique_number = unique_num
        context['UNIQUE_NUMBER'] = unique_num

    # Since a report template can be reused and items can be repeated 
    # it can be useful to have a unique number that can be used to name
    # things.  This number starts at 0 and increments when used...
    @classmethod
    def get_unique_number(cls, context):
        unique_number = (cls.unique_number + 1) % 0xffffffff
        cls.set_unique_number(unique_number, context)
        return unique_number

    # Use these methods (get_default and get_indexed_default) to get a value from
    # the current context.  They handle recursive substitution (soon).
    @staticmethod
    def get_default(ctx, key, default=None, force_int=False, force_float=False, ignore_tags=None):
        # "hide" the tags we do not want to replace
        if ignore_tags is None:
            ignore_tags = list()
        for t in ignore_tags:
            if t in ctx:
                ctx['__TEMP__' + t] = ctx.pop(t)
        # look for the key in the context dictionary
        tmp = ctx.get(key, default)
        if tmp is not None:
            tmp = expand_string_context(tmp, ctx)
        if force_int:
            try:
                tmp = int(tmp)
            except:
                tmp = default
        if force_float:
            try:
                tmp = float(tmp)
            except:
                tmp = default
        # "un-hide" the tags we do not want to replace
        for t in ignore_tags:
            if '__TEMP__' + t in ctx:
                ctx[t] = ctx.pop('__TEMP__' + t)
        return tmp

    @staticmethod
    def get_indexed_default(ctx, idx, key, default=None, ignore_tags=None):
        # "hide" the tags we do not want to replace
        if ignore_tags is None:
            ignore_tags = list()
        for t in ignore_tags:
            if t in ctx:
                ctx['__TEMP__' + t] = ctx.pop(t)
        # look for the key in the context dictionary
        # if it has the [] syntax, split it and use the value at [idx]
        # if not, return the value
        tmp = ctx.get(key, default)
        if tmp is not None:
            tmp = str(tmp).strip()
            if len(tmp) and ((tmp[0] == '[') and (tmp[-1] == ']')):
                tmp = split_quoted_string_list(tmp[1:-1], delimiter=',')
                # tmp = tmp.strip()[1:-1].split(',')
                tmp = tmp[idx % len(tmp)]
            tmp = expand_string_context(tmp, ctx).strip()
        # "un-hide" the tags we do not want to replace
        for t in ignore_tags:
            if '__TEMP__' + t in ctx:
                ctx[t] = ctx.pop('__TEMP__' + t)
        return tmp

    @staticmethod
    def context_expansion(s, context, item=None):
        # one special case: for symmetry we map i/keyname to keyname
        # this provides symmetry with the 'd/' and 's/' cases
        s = convert_macro_slashes(s)
        # get an instance of the Django template engine...
        django_engine = engines['django']
        try:
            template = django_engine.from_string('{% load data_tags %}' + s)
        except Exception as e:
            return s + "<br><p><b>Macro expansion initialization error: {}</b></p>".format(str(e))
        local_context = copy.copy(context)
        if item is not None:
            local_context.update(item.build_tag_dictionary())
        local_context.update(TemplateEngine.get_global_context())
        expand_dictionary_context(local_context, local_context)
        try:
            out = template.render(context=local_context)
        except Exception as e:
            return s + "<br><p><b>Macro expansion error: {}</b></p>".format(str(e))
        return out

    # Table of contents handling (see parallel notes wth global_context)
    # The basic idea is that when a report is started, the engine keeps track of
    # the number of Tables and Figures as well as a general Table of Contents.
    # As the report engine traverses the report, it notes report templates with
    # specific tags or properties that flag them as being part of the TOC lists.
    # A number is assigned when these flags are detected and a name is generated
    # for display.  The global context is updated to reflect the new numbers so
    # they can be used in macro expansions.  These include: {{toc_figure_number}}
    # {{toc_table_number}} and {{toc_item_number}}.
    #
    # An anchor is placed in the output HTML stream that will serve as the TOC link
    # target.  An instance of the TOC layout is used to place the various TOC lists
    # in the report.
    #
    # Entries into the TOC system are based on the following tags/properties:
    #
    # TOCFigure - if set will add a figure entry: 0=none, 1=template, 2=items
    # TOCTable - if set will add a table entry: 0=none, 1=template, 2=items
    # TOCItem - if set will add a TOC item entry: 0=none, 1=template, 2=items
    # TOCName - if set will provide the text string to use for the new entry, if
    #           not set, the name of the object is used
    # TOCLevel - when adding a TOCItem, this entry selects the level in the toc
    #            hierarchy that the item will be placed into
    #
    # At present, the system is limited to templates, but it could be extended to
    # items in the future.

    toc_tracking_state = True
    toc_figure_list = list()  # [number, "text", "href_id"]
    toc_table_list = list()  # [number, "text", "href_id"]
    toc_item_list = list()  # [number, "text", "href_id", level]

    # if true, items will record toc entities (as children of a template)
    toc_figure_record = True
    toc_table_record = True
    toc_item_record = True

    # these are the HTML ids of the <div> blocks added for the various TOC lists
    toc_figurelist_divs = list()
    toc_tablelist_divs = list()
    toc_itemlist_divs = list()

    # clear out the TOC system state
    @classmethod
    def start_toc_session(cls):
        cls.toc_figure_list = list()
        cls.toc_table_list = list()
        cls.toc_item_list = list()

        cls.toc_figure_record = True
        cls.toc_table_record = True
        cls.toc_item_record = True

        cls.toc_figurelist_divs = list()
        cls.toc_tablelist_divs = list()
        cls.toc_itemlist_divs = list()

    # generate the <script> blocks to fill in the TOC<div>s
    @classmethod
    def end_toc_session(cls):
        # classes for the <ul> and <li> tags
        s = "<style>\n"
        s += ".toc_root {list-style-type: none;}\n"
        s += ".toc_0 {text-indent: 0pt;}\n"
        s += ".toc_1 {text-indent: 15pt;}\n"
        s += ".toc_2 {text-indent: 30pt;}\n"
        s += ".toc_3 {text-indent: 45pt;}\n"
        s += ".toc_4 {text-indent: 60pt;}\n"
        s += ".toc_5 {text-indent: 75pt;}\n"
        s += ".toc_6 {text-indent: 90pt;}\n"
        s += "</style>\n"
        s += "<script type='text/javascript'>\n"
        s += "$(document).ready(function() {\n"
        # Figures
        s += " var figtmp = '<ul class=\"toc_root\">"
        for fig in cls.toc_figure_list:
            s += '<li class=\"toc_0\"><a href="#{}">{}. {}</a></li>'.format(fig[2], fig[0], fig[1].replace("'", '"'))
        s += "</ul>';\n"
        for div in cls.toc_figurelist_divs:
            s += " document.getElementById('{}').innerHTML = figtmp;\n".format(div)
        s += " var tabtmp = '<ul class=\"toc_root\">"
        for tab in cls.toc_table_list:
            s += '<li class=\"toc_0\"><a href="#{}">{}. {}</a></li>'.format(tab[2], tab[0], tab[1].replace("'", '"'))
        s += "</ul>';\n"
        for div in cls.toc_tablelist_divs:
            s += " document.getElementById('{}').innerHTML = tabtmp;\n".format(div)
        s += " var itmtmp = '<ul class=\"toc_root\">"
        for itm in cls.toc_item_list:  # [number, "text", "href_id", level]
            n = max(0, min(itm[0].count('.'), 6))
            s += '<li class=\"toc_{}\"><a href="#{}">{} {}</a></li>'.format(n, itm[2], itm[0], itm[1].replace("'", '"'))
        s += "</ul>';\n"
        for div in cls.toc_itemlist_divs:
            s += " document.getElementById('{}').innerHTML = itmtmp;\n".format(div)
        s += "});\n"
        s += "</script>\n"
        return s

    # Add the active figures to a dictionary that will be merged into the current context
    @classmethod
    def build_toc_properties(cls):
        d = dict()
        try:
            num = cls.toc_figure_list[-1][0]
            d['toc_figure_number'] = str(num)
        except:
            pass
        try:
            num = cls.toc_table_list[-1][0]
            d['toc_table_number'] = str(num)
        except:
            pass
        try:
            num = cls.toc_item_list[-1][0]
            d['toc_item_number'] = str(num)
        except:
            pass
        return d

    # called when a template is started
    # look at the context and see if we need to generate an entity or mark that items should do so...
    def start_template_toc(self, ctx):
        # save incoming values
        self.toc_figure_record_save = TemplateEngine.toc_figure_record
        self.toc_table_record_save = TemplateEngine.toc_table_record
        self.toc_item_record_save = TemplateEngine.toc_item_record
        # set up  the new values and return generated refs
        # suppress toc tracking for child templates
        if self._enable_toc_tracking is False:
            return list()
        return self.record_toc_entry(self, ctx)

    @classmethod
    def record_toc_entry(cls, obj, ctx):
        is_template = isinstance(obj, TemplateEngine)
        out = list()
        # is it a figure?
        figure_flags = cls.get_default(ctx, "TOCFigure", default=0, force_int=True)
        if is_template:
            cls.toc_figure_record = (figure_flags & 2) != 0
            if figure_flags & 1:
                out.append(cls.add_toc_figure(obj, ctx))
        else:
            if cls.toc_figure_record:
                out.append(cls.add_toc_figure(obj, ctx))
        # is it a table?
        table_flags = cls.get_default(ctx, "TOCTable", default=0, force_int=True)
        if is_template:
            cls.toc_table_record = (table_flags & 2) != 0
            if table_flags & 1:
                out.append(cls.add_toc_table(obj, ctx))
        else:
            if cls.toc_table_record:
                out.append(cls.add_toc_table(obj, ctx))
        # is it an item?
        item_flags = cls.get_default(ctx, "TOCItem", default=0, force_int=True)
        if is_template:
            cls.toc_item_record = (item_flags & 2) != 0
            if item_flags & 1:
                out.append(cls.add_toc_item(obj, ctx))
        else:
            if cls.toc_item_record:
                out.append(cls.add_toc_item(obj, ctx))

        return out

    # called when the template is ended
    def end_template_toc(self):
        # restore the recording status
        TemplateEngine.toc_figure_record = self.toc_figure_record_save
        TemplateEngine.toc_table_record = self.toc_table_record_save
        TemplateEngine.toc_item_record = self.toc_item_record_save

    # methods that add a toc entity...
    @classmethod
    def add_toc_figure(cls, obj, ctx):
        num = len(cls.toc_figure_list) + 1
        href_id = "TOC_fig_tgt_{}".format(num)
        name = cls.get_default(ctx, "TOCName", obj.name)
        if name == '""':
            name = obj.name
        name = expand_string_context(name, cls.get_global_context())
        cls.toc_figure_list.append([num, name, href_id])
        return href_id

    @classmethod
    def add_toc_table(cls, obj, ctx):
        num = len(cls.toc_table_list) + 1
        href_id = "TOC_tab_tgt_{}".format(num)
        name = cls.get_default(ctx, "TOCName", obj.name)
        if name == '""':
            name = obj.name
        name = expand_string_context(name, cls.get_global_context())
        cls.toc_table_list.append([num, name, href_id])
        return href_id

    @classmethod
    def add_toc_item(cls, obj, ctx):
        # build the href using the length of the array
        num = len(cls.toc_item_list) + 1
        href_id = "TOC_item_tgt_{}".format(num)
        name = cls.get_default(ctx, "TOCName", obj.name)
        if name == '""':
            name = obj.name
        try:
            # the level defaults to the last recorded level or 0
            try:
                last = cls.toc_item_list[-1][-1]
            except:
                last = 0
            # but can be overridden
            level = int(ctx.get("TOCLevel", last))
        except:
            level = 0
        # build the toc numbers
        name = expand_string_context(name, cls.get_global_context())
        cls.toc_item_list.append([num, name, href_id, level])
        cls.build_toc_item_numbers(0, 0, "")
        return href_id

    @classmethod
    def build_toc_item_numbers(cls, level, index, prefix):
        # number of values at this level
        count = 0
        while True:
            # end of the list?
            if (index >= len(cls.toc_item_list)) or (index < 0):
                return -1
            # new, deeper level
            if cls.toc_item_list[index][-1] > level:
                v = "{}{}.".format(prefix, count)
                index = cls.build_toc_item_numbers(cls.toc_item_list[index][-1], index, v)
            # same level
            elif cls.toc_item_list[index][-1] == level:
                count += 1
                # assign value
                cls.toc_item_list[index][0] = "{}{}".format(prefix, count)
                index += 1
            # hit a shallower level (end this block)
            else:
                return index

    # Object methods ###################################
    #
    def __init__(self, template_object):
        # helpful when mixing items and engines...
        self.name = template_object.name
        self._parent = None
        self._children = []
        self._template = template_object
        # convert the JSON encoded parameters into instance member
        try:
            self._params = json.loads(self._template.params)
        except Exception:
            self._params = {}
        self._filter_timing = 0.
        self._render_timing = 0.
        self._enable_toc_tracking = True
        # for debugging...
        self._colorize_color = None

    @property
    def template(self):
        return self._template

    @property
    def properties(self):
        return self._params.get("properties", {})

    @property
    def children(self):
        return self._children

    @property
    def parent(self):
        return self._parent

    def set_parent(self, parent):
        self._parent = parent

    # used to paint background to match debugging colors
    def calculate_random_colors(self, h, tgt):
        r, g, b = colorsys.hsv_to_rgb(h, 0.3, 0.99)
        if tgt == str(self._template.guid):
            r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.99)
        self._colorize_color = (r, g, b)
        h = (h + 0.618033988749895) % 1.
        for i in range(len(self._children)):
            h = self._children[i].calculate_random_colors(h, tgt)
        return h

    def get_colorize_color(self):
        if self._colorize_color is None:
            return None
        r = int(min(255, max(0, self._colorize_color[0] * 255)))
        g = int(min(255, max(0, self._colorize_color[1] * 255)))
        b = int(min(255, max(0, self._colorize_color[2] * 255)))
        rgb = "background-color: #{0:02x}{1:02x}{2:02x};".format(r, g, b)
        return rgb

    # A report template may provide top level menus that should
    # replace the default menus.  If so, returning True here will
    # suppress the default menus.
    def provides_menus(self):
        return False

    # apply the template filter.  this can filter the input list of items or
    # start a new search and replace or append to the input list
    def filter_items(self, input_items, context):
        # get the operation
        filter_type = self._params.get('filter_type', 'items')
        # three cases here:
        # 'items' : filter the item list using the current template item filter
        # 'root_replace' : apply the template filter to the entire database and return the result (discards user query)
        # 'root_append' : similar to above, except the results are appended to the (unfiltered) input items
        if filter_type.startswith('root'):
            from ..data.models import Item, object_filter
            # root queryset must be perm filtered.
            # context must always contain request.
            qs = Item.filtered_objects.with_perms(context['request'])
            root_items = list(object_filter(self._template.item_filter,
                                            qs,
                                            model=Item))
            if filter_type.endswith('append'):
                root_items.extend(list(input_items))
            return root_items
        # the default case: 'items' will filter the input list using the template's filter string
        tmp = list(self._template.filter_items(input_items))
        return tmp

    attribute_lookup = {
        'i_name': ('i', 'name'),
        'i_src': ('i', 'source'),
        'i_date': ('i', 'date'),
        'i_tags': ('i', 'tags'),
        'i_type': ('i', 'type'),
        'i_seq': ('i', 'sequence'),
        's_app': ('s', 'application'),
        's_ver': ('s', 'version'),
        's_date': ('s', 'date'),
        's_tags': ('s', 'tags'),
        's_host': ('s', 'host'),
        's_plat': ('s', 'platform'),
        'd_name': ('d', 'filename'),
        'd_dir': ('d', 'dirname'),
        'd_fmt': ('d', 'format'),
        'd_tags': ('d', 'tags')
    }

    @classmethod
    def sort_items(cls, rules, items):
        # Heavyweight sort key function for comparing two items with
        # multi-directional, multi-key sorting...
        def sort_items_key(item):
            sort_rules = item.sort_info
            for rev, obj, attr in sort_rules:
                try:
                    if obj == 's':
                        item = item.session_set.first()
                    elif obj == 'd':
                        item = item.dataset_set.first()
                    value = getattr(item, attr)
                    return -value if rev else value
                except Exception:
                    pass
            return 0

        if not rules:
            return items

        # Convert the rules into a simplified form...
        expanded_rules = []
        for rule in rules:
            rev = rule[0] == '-'
            obj, attr = TemplateEngine.attribute_lookup.get(rule[1:], ('i', 'name'))
            expanded_rules.append((rev, obj, attr))

        # Assign expanded rules to each item
        for item in items:
            item.sort_info = expanded_rules

        # Sort the items based on the key function
        items.sort(key=sort_items_key)
        return items

    def dispatch_render(self, render_format, input_items, context, **kwargs):
        # Try to dispatch to the right method; if a method isn't implemented,
        # defer to the default render() method to return HTML. Also defer
        # to render() if the render_format isn't on the approved list.
        # This must be used if you want the client to decide the render
        # format.
        if render_format.lower() in self.allowed_render_formats:
            handler = getattr(self, f"render_{render_format.lower()}", self.render)
        else:
            handler = self.render
        return handler(input_items, context, **kwargs)

    def render(self, input_items, context, **kwargs):
        return ""

    def add_child(self, engine):
        self._children.append(engine)


class LayoutEngine(TemplateEngine):
    """Base class for all of the Layout objects.  This engine converts items into HTML output via render()"""

    def __init__(self, template_object):
        super().__init__(template_object)
        self._container_class = 'container-fluid mx-auto'

    def parse_HTML(self, context):
        return self.context_expansion(self._params.get('HTML', ''), context)

    def parse_comments(self, context):
        return self.context_expansion(self._params.get('comments', ''), context)

    def get_margin_style(self, context):
        # get the user specified margin styling from the context
        style = ''
        for side in ['top', 'bottom', 'right', 'left']:
            margin = self.get_default(context, f'margin_{side}', -1, force_int=True)
            if margin >= 0:
                style += f'padding-{side}: {margin}pt;'
        return style

    def get_margin_linebreak(self, context):
        if self.get_default(context, 'margin_line', 1, force_int=True):
            return '<br>'
        return ''

    def block_header(self, items, context):
        # start the output with an over-arching <div>
        # set up margins/etc
        # Optionally include HTML header
        out = self.get_margin_linebreak(context)
        skip_html = self.get_default(context, "skip_html", False)
        if not skip_html:
            out += self.parse_HTML(context)
        out += self.parse_comments(context)
        # header for the children...
        style = self.get_margin_style(context)
        background = self.get_colorize_color()
        if background:
            style += background
        if len(style):
            style = 'style="{}"'.format(style)
        out += '<div class="{}" id="{}" {}>\n'.format(self._container_class, str(self.template.guid), style)
        return out

    def block_trailer(self, items, context):
        out = '</div>\n'
        return out

    def skip_empty(self, items):
        # Skip if no data items option
        try:
            skip_empty = int(self._params.get("skip_empty", "0"))
        except:
            skip_empty = 0
        # Forced skip
        if skip_empty == 2:
            return True
        # Skip if empty
        if (skip_empty == 1) and (len(items) == 0):
            return True
        # Never skip (0)
        return False

    def render(self, input_items, context, apply_item_filter=True, **kwargs):
        # start the timing
        t0 = time.time()

        # Start with nothing...
        html = ''

        # builds a context dict for the current template
        # from the global context dict
        local_context = copy.copy(context)
        # template properties
        template_props = self._params.get("properties", {})
        if len(template_props):
            local_context.update(template_props)
        local_context['template_name'] = self.template.name

        # Top level div with template GUID name tag
        style = ' nexus_template="{}"'.format(str(self.template.guid))
        # build the style css
        css = ''
        # if background shading is active, set it on the top level div
        background = self.get_colorize_color()
        if background is not None:
            css += ' border: none; margin: 0; padding: 0; {}'.format(background)
        # Control over page break
        pagebreak = self.get_default(local_context, 'pagebreak', 0, force_int=True)
        if pagebreak:
            css += ' page-break-inside: avoid;'
        # Build the style/css if needed
        if len(css):
            style += ' style="{}"'.format(css)
        # External <div>
        html += '<div {}>'.format(style)

        # filter the item list if requested
        if apply_item_filter:
            items = self.filter_items(input_items, context)
        else:
            items = input_items
        filter_timing = time.time() - t0

        # Skip if no data items option
        if self.skip_empty(items):
            # Skip this template...
            return ''

        # sort the items (if need be)
        t1 = time.time()
        rules = self._params.get("sort_fields", [])
        if len(rules):
            items = TemplateEngine.sort_items(rules, items)
        sort_timing = time.time() - t1

        # first, last, all selection
        sort_selection = self._params.get("sort_selection", "all")
        if sort_selection == 'first':
            items = items[:1]
        elif sort_selection == 'last':
            items = items[-1:]

        # TOC handling: now that we have the current context, look for TOC properties
        # check to see if this template defines a TOC entity
        toc_targets = self.start_template_toc(local_context)
        for tmp in toc_targets:
            # insert a link target <a> with potential shifting for the nav bar
            html += '<a id="{}"></a>'.format(tmp)
        # add active TOC properties to the context
        d = self.build_toc_properties()
        if d:
            local_context.update(d)

        # dispatch to the core renderer
        html += self.render_template(items, local_context, **kwargs)
        render_timing = time.time() - t0

        # debug timing...
        if self.get_default(local_context, 'template_timing_debug') is not None:
            html += "<p>Template timing total: {}, filtering: {}, sorting: {}</p>".format(render_timing,
                                                                                          filter_timing,
                                                                                          sort_timing)
        # End of TOC processing for this template
        self.end_template_toc()

        # end the top level div
        html += '</div>'

        return html

    def get_descendants(self):
        descendants = []
        # recurse depth-wise
        for child in self.children:
            descendants.extend([child, *child.get_descendants()])
        return descendants

    def get_child_layouts(self, exclude_tag="__INACTIVE__", recursive=False):
        children = self.get_descendants() if recursive else self.children
        if exclude_tag is not None:
            children = [child for child in children if exclude_tag not in child.template.tags]
        return children

    @context_macros
    def render_template(self, items, context, child_item_context_blocks=None, **kwargs):
        # build the columns information
        col_widths = self._params.get('column_widths', None)
        # how many items will we place in the columns?
        num_items = len(items)
        # should we cap the number of columns at the number of items?
        limit_column_count = self.get_default(context, 'column_count_item_limit', default=0, force_int=True)
        if col_widths is None:
            num_columns = int(self._params.get('column_count', 1))
            if limit_column_count:
                num_columns = min(num_columns, num_items)
            # clamp to the range [1,12]
            col_count = min(max(num_columns, 1), 12)
            col_widths = [1. / float(col_count)] * col_count
        else:
            # clean up and normalize
            col_widths = col_widths[:12]
            if limit_column_count:
                if len(col_widths) > num_items:
                    col_widths = col_widths[:num_items]
            # should we re-normalize???
            s = sum(col_widths)
            col_widths = [x / s for x in col_widths]  # pylint: disable=W1619
            col_count = len(col_widths)
        # beware: round is different in py2 vs 3. py3 rounds to nearest even number
        col_widths = [int(round(x * 12)) for x in col_widths]  # pylint: disable=W1633

        # remember who we are just in case we need it somewhere...
        context['template_engine'] = self

        # start the output block
        out = self.block_header(items, context)

        # walk the children or the items...
        items_as_links = context.get('items_as_links', self._params.get('item_as_links', False))

        # In the default mode, the objects being rendered into the columns come from the
        # the child templates or from the actual items (for leaf nodes).  If child_item_context_blocks
        # is set, the iteration is a little different.  The variable specifies tuple(s) of child templates, items
        # and contexts, each set of which should go into a column.  To make this work, out_list is
        # generated from this form if the more specific keyword is not set.
        # Thus, len(out_list) is the number of "renderables" that play into the column layout scheme.
        if child_item_context_blocks is not None:
            out_list = child_item_context_blocks
        else:
            # in the default mode, each child or item is a new column entry using the input item list and
            # the context for rendering.
            out_list = list()
            if len(self.children):
                for c in self.get_child_layouts():
                    out_list.append(([c], items, context))
            else:
                for i in items:
                    out_list.append(([i], items, context))

        # ok, time to lay out the page and render the items.
        if (col_count == 1) and (col_widths[0] == 12):
            # super simple case, no need for wrapping by <div>
            # each tuple goes into a separate "column"
            for tmp_render, tmp_items, tmp_context in out_list:
                # iterator over the child/item and render them.
                if isinstance(tmp_render[0], TemplateEngine):
                    for v in tmp_render:
                        out += v.render(tmp_items, tmp_context)
                else:
                    for v in tmp_render:
                        if items_as_links:
                            url = v.get_payload_url()
                            if '?' in url:
                                url += '&formatted=1'
                            else:
                                url += '?formatted=1'
                            out += '<li><a href="' + url + '">' + v.name + '</a></li>\n'
                        else:
                            try:
                                out += v.render(tmp_context)
                            except Exception as e:
                                out += get_render_error_html(e, target='item', guid=v.guid)
        else:
            # we might need to take the transpose of the input
            if self._params.get('transpose', False):
                # get the rectangle
                row_count = len(out_list) // col_count
                # pad out the list with None values
                # as the transpose could result in
                # multiple, short rows (which we mark as None)
                if col_count * row_count < len(out_list):
                    row_count += 1
                    out_list += [(None, None, None)] * (col_count * row_count - len(out_list))
                # swap rows and columns
                tmp = []
                # take every 'column' element starting some number in...
                for start in range(row_count):
                    for v in out_list[start::row_count]:
                        tmp.append(v)
                out_list = tmp
            # we have real columns
            count = 0
            out += '<div class="row">\n'
            # iterate over all of the column "items"
            for tmp_render, tmp_items, tmp_context in out_list:
                # new row?
                if count % col_count == 0:
                    out += '</div>\n<div class="row">\n'
                # this could be None because of transpose padding...
                if tmp_render is not None:
                    # Normally, this should be 'md' or such to work around
                    # printing issues with chrome, use 'xs' so that it keeps columns
                    # bs4 : col-xs is now col.
                    col_class = 'col-%d' % col_widths[count % col_count]
                    out += '<div class="%s text-center mx-auto">\n' % col_class
                    if isinstance(tmp_render[0], TemplateEngine):
                        # all of the child templates go into this row/column "cell"
                        for v in tmp_render:
                            out += v.render(tmp_items, tmp_context)
                    else:
                        # all of these items go into this row/column "cell"
                        for v in tmp_render:
                            if items_as_links:
                                url = v.get_payload_url()
                                out += '<li><a href="' + url + '">' + v.name + '</a></li>\n'
                            else:
                                try:
                                    out += v.render(tmp_context)
                                except Exception as e:
                                    out += get_render_error_html(e, target='item', guid=v.guid)

                    out += '</div>\n'
                count += 1
            out += '</div\n>'

        # end of the children block
        out += self.block_trailer(items, context)
        return out


class GeneratorEngine(TemplateEngine):
    """Base class for all of the Generator objects.  Filter, sort, select, properties and then process."""

    def __init__(self, template_object):
        super().__init__(template_object)
        self._enable_toc_tracking = False

    def skip_empty(self, items):
        # Skip if no data items option
        try:
            skip_empty = int(self._params.get("skip_empty", "0"))
        except:
            skip_empty = 0
        # Forced skip
        if skip_empty == 2:
            return True
        # Skip if empty
        if (skip_empty == 1) and (len(items) == 0):
            return True
        # Never skip (0)
        return False

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

        # update the context to include local options
        local_context = copy.copy(context)
        template_props = self._params.get("properties", {})
        if len(template_props):
            local_context.update(template_props)

        # do the real work here!!!
        # todo: evaluates 100s of items in the queryset, if unfiltered by user query
        #  rewrite this.
        final_items = list(input_items)
        new_items = self.process(items, local_context, **kwargs)

        # if the user requested that the template tags be copied, do so now...
        # this copies the template's tags to the item's tags.
        copy_tags = self._params.get("generate_appendtags", True)
        if copy_tags:
            for idx in range(len(new_items)):
                new_items[idx].tags += " " + self.template.tags

        # add or replace the incoming items
        # todo: change default value, because there's a chance final_items might be unfiltered
        #  resulting in a large set returned
        operation = self._params.get("generate_merge", "add")
        if operation == "add":
            final_items.extend(new_items)
        else:
            final_items = new_items

        s = ''
        # we may need to place this in a custom div
        background = self.get_colorize_color()
        if background is not None:
            style = 'style="border: none; margin: 0; padding: 0; {}"'.format(background)
            s += '<div {}>'.format(style)

        # Continue processing our children until all children are done,
        # if no children, render the items directly.
        if len(self.children):
            for template_engine in self.children:
                s += template_engine.render(final_items, local_context, **kwargs)
        else:
            for item in final_items:
                try:
                    s += item.render(local_context, **kwargs)
                except Exception as e:
                    s += get_render_error_html(e, target='item', guid=item.guid)

        # end any debug colorizing div
        if self._colorize_color is not None:
            s += '</div>'

        return s

    # Override this method in the generator subclasses to do the operation
    # this method should return the newly generated items only.  They will be merged by render()
    def process(self, items, context, **kwargs):
        return []


# We need to define all the template classes and register them with the engine factory
# To do this, we  import all the modules that contain generator and layout template classes
# here.  The individual classes are responsible for registering them with the factory.
# For now, this takes the form of a simple import of a part of modules.  It could eventually
# become a more automated system (e.g. user-defined, etc).
