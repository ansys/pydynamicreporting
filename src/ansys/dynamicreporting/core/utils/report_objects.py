import base64
import copy
import datetime
import io
import json
import os
import os.path
import pickle
import shlex
import sys
import uuid
import weakref

import dateutil
import dateutil.parser
import pytz

from . import extremely_ugly_hacks, report_utils
from .encoders import PayloaddataEncoder

try:
    from PyQt5 import QtCore, QtGui

    has_qt = True
except ImportError:
    has_qt = False

try:
    import numpy

    has_numpy = True
except ImportError:
    has_numpy = False

"""@package report_objects
Basic object classes used for server operations
"""


# tools to map properties to Nexus dictionary entries
def convert_color(rgb):
    r = "%0.2x" % int(rgb[0] * 255)
    g = "%0.2x" % int(rgb[1] * 255)
    b = "%0.2x" % int(rgb[2] * 255)
    return "#" + r + g + b


def convert_style(s, t):
    tmp = "solid"
    if t == 0:
        return "none"
    if s == 1:
        tmp = "dot"
    elif s == 3:
        tmp = "dash"
    return tmp


def convert_marker(m):
    if m == 1:
        return "circle"
    if m == 2:
        return "circle-open"
    if m == 3:
        return "triangle-open"
    if m == 4:
        return "square-open"
    return "none"


def convert_label_format(s):
    if s.endswith("g"):
        import re

        m = re.match(r"%(\d+)g", s)  # Find the numbers
        if m:
            return "sigfigs" + m.group(1)  # Get the numbers
        else:
            return "sigfigs4"
    elif s.endswith("f"):
        return f"floatdot{s[-2]}"
    # endswith 'e'
    return "scientific"


def get_title_units(title, var):
    try:
        import ensight
    except ImportError:
        return title

    if var is None:
        # if no var, replace the tag
        return title.replace("<\\\\units>", "")
    units = ensight.objs.core.get_units(var, format=1, prefix=" [", suffix="]", utf8=1)
    return title.replace("<\\\\units>", units)


def extract_data_from_ensight_query(q):
    data = q.QUERY_DATA
    array = numpy.array(data["xydata"], numpy.double).transpose()
    if q.NORMALIZEX:
        tmp = array[0] - min(array[0])
        mx = max(tmp)
        if mx != 0.0:
            tmp /= mx
        array[0] = tmp
    else:
        array[0] = array[0] * q.SCALE[0] + q.OFFSET[0]
    if q.NORMALIZEY:
        tmp = array[1] - min(array[1])
        mx = max(tmp)
        if mx != 0.0:
            tmp /= mx
        array[1] = tmp
    else:
        array[1] = array[1] * q.SCALE[1] + q.OFFSET[1]
    return array


def map_ensight_plot_to_table_dictionary(p):
    # TODO: re-consider use of utf8 encoding here for Python 3...  report_utils.local_to_utf8(s, True)
    try:
        import ensight

        if type(p) is not ensight.objs.ENS_PLOTTER:
            return None
    except ImportError:
        # You can still process, assuming the passed object fits the ENS_PLOTTER schema
        pass

    # any data in this plotter??
    if len(p.QUERIES) < 1:
        return None

    x_axis_title = get_title_units(p.AXISXTITLE, p.VAR_XAXIS_OBJ)
    y_axis_title = get_title_units(p.AXISYTITLE, p.VAR_YAXIS_LEFT_OBJ)

    max_columns = 0
    plot_data = list()
    # line color
    line_colors = "["
    # line thickness
    line_thickness = "["
    # line style
    line_styles = "["
    # marker...
    line_markers = "["
    # marker size
    line_marker_size = "["
    for q in p.QUERIES:
        a = extract_data_from_ensight_query(q)
        # convert EnSight undefined values into Numpy NaN values
        try:
            a[a == ensight.Undefined] = numpy.nan
        except Exception:
            pass
        max_columns = max(a.shape[1], max_columns)
        d = dict(array=a, yname=q.LEGENDTITLE, xname=x_axis_title)
        plot_data.append(d)
        # other attributes
        if len(line_colors) > 1:
            line_colors += ","
            line_thickness += ","
            line_styles += ","
            line_markers += ","
            line_marker_size += ","
        line_colors += f"{convert_color(q.RGB)}"
        line_thickness += f"{q.LINEWIDTH}"
        line_styles += f"{convert_style(q.LINESTYLE, q.LINETYPE)}"
        line_markers += f"{convert_marker(q.MARKER)}"
        line_marker_size += f"{q.MARKERSCALE * 5.0}"
    line_colors += "]"
    line_thickness += "]"
    line_styles += "]"
    line_markers += "]"
    line_marker_size += "]"
    # cleanup and extend arrays...
    rowlbls = list()
    array = None
    yaxis_txt = "["
    xaxis_txt = "["
    i = 0
    for tmp in plot_data:
        # special case: Nexus will use the X axis row name as the title
        # instead of xtitle.  If the name provided by the query aligns
        # with the plotter title, we will use the plotter title instead as
        # it may include things like units...
        tmp_title = tmp["xname"]
        if x_axis_title.startswith(tmp_title):
            tmp_title = x_axis_title
        rowlbls.append(tmp_title)
        rowlbls.append(tmp["yname"])
        if i > 0:
            xaxis_txt += ","
            yaxis_txt += ","
        xaxis_txt += f"{i}"
        yaxis_txt += f"{i + 1}"
        i += 2
        a = tmp["array"]
        # pad out the array to match the largest (making concatenation possible)
        while a.shape[1] < max_columns:
            a = numpy.insert(a, a.shape[1], numpy.nan, 1)
        if array is None:
            array = a
        else:
            array = numpy.concatenate([array, a])
    xaxis_txt += "]"
    yaxis_txt += "]"
    # Add a table payload...
    plot_title = get_title_units(p.PLOTTITLE, None)
    d = dict(
        array=array,
        rowlbls=rowlbls,
        plot_title=plot_title,
        plot="line",
        xtitle=x_axis_title,
        ytitle=y_axis_title,
    )
    # axis types
    if p.AXISXSCALE:
        d["plot_xaxis_type"] = "log"
    if p.AXISYSCALE:
        d["plot_yaxis_type"] = "log"
    if not p.AXISXAUTOSCALE:
        d["xrange"] = f"[{p.AXISXMIN}, {p.AXISXMAX}]"
    if not p.AXISYAUTOSCALE:
        d["yrange"] = f"[{p.AXISYMIN}, {p.AXISYMAX}]"
    # axis formats
    d["yaxis_format"] = convert_label_format(p.AXISYLABELFORMAT)
    d["xaxis_format"] = convert_label_format(p.AXISXLABELFORMAT)
    # mark the desired display format and x axis
    d["yaxis"] = yaxis_txt
    d["xaxis"] = xaxis_txt
    # trace visuals
    d["line_marker_size"] = line_marker_size
    d["line_marker"] = line_markers
    d["line_color"] = line_colors
    d["line_style"] = line_styles
    d["line_width"] = line_thickness
    # one plot done
    return d


# Method copied from data.templatetags.data_tags
def split_quoted_string_list(s, deliminator=None):
    """Split a string into a list at shlex determined locations, properly handling
    quoted strings."""
    tmp = shlex.shlex(s)
    if deliminator is not None:
        tmp.whitespace = deliminator
    else:
        tmp.whitespace += ","
    # only split at the whitespace chars
    tmp.whitespace_split = True
    # we do not have comments
    tmp.commenters = ""
    out = list()
    while True:
        token = tmp.get_token()
        token = token.strip()
        if (token.startswith("'") and token.endswith("'")) or (
            token.startswith('"') and token.endswith('"')
        ):
            token = token[1:-1]
        if len(token) == 0:
            break
        out.append(token)
    return out


# simplified version of the Stanza from data/models.py
class Stanza:
    """Representation of a single term in a filter expression."""

    def __init__(self, link, field, comparison, value):
        self._link = link
        self._field = field
        self._comp = comparison
        self._value = value


def parse_filter(query):
    # convert the query string into a list of Stanza objects
    qlist = []
    if type(query) == bytes:
        query = query.decode(report_utils.platform_encoding())
    else:
        query = str(query)
    terms = [_f for _f in query.split(";") if _f]
    for term in terms:
        tmp = term.split("|")
        # parse out the values into a list and strip leading/trailing spaces
        values = [_f for _f in tmp[3].split(",") if _f]
        values = list(map(str.strip, values))
        if len(values):
            qlist.append(Stanza(tmp[0], tmp[1], tmp[2], values))
    return qlist


# Note: all of these classes assume that their input parameters are UTF-8 encoded, this is CRITICAL
class Template:
    """Report editor representation of a report template."""

    # class methods ##################
    # variables/methods to track the current server and options
    @classmethod
    def get_list_url(cls):
        return "/reports/api_list"

    # a hash table to look up objects from guids via weakref
    template_lookup = {}

    @classmethod
    def get_template_object(cls, guid):
        tmp = cls.template_lookup.get(guid, None)
        if tmp:
            # have a weakref, return the object
            return tmp()
        return None

    @classmethod
    def add_template_object(cls, obj):
        # take the opportunity here to clean up the hash
        # of stale entries...
        for guid in list(cls.template_lookup.keys()):
            if cls.template_lookup[guid]() is None:
                del cls.template_lookup[guid]
        # add the new object
        cls.template_lookup[obj.guid] = weakref.ref(obj)

    # instance methods ##################

    def __init__(self, *initial_data, **kwargs):
        self.parent = None
        self.master = True
        self.name = ""
        self.tags = ""
        self.report_type = "Layout:basic"
        self.item_filter = ""
        self.date = datetime.datetime.now(pytz.utc).isoformat()
        self.children_order = ""
        self.children = list()
        self.guid = ""
        self.params = None
        self.temp_children = list()
        self.reset_defaults()
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])
        self.__class__.add_template_object(self)
        self._dirty = True

    def paste_reset(self):
        # Assume this template is the result of a deepcopy operation and it is being
        # "pasted" into existence
        # It needs a new GUID and date
        self.guid = str(uuid.uuid1())
        self.date = datetime.datetime.now(pytz.utc).isoformat()
        self.__class__.add_template_object(self)
        # Note: these are str GUIDs, not object references
        # the methods get_parent_object()/get_child_objects()
        # can return these as objects
        self.parent = None
        self.master = True
        self._dirty = True
        self.children = list()
        self.children_order = ""

    def reset_defaults(self):
        self.paste_reset()
        self.name = ""
        self.tags = ""
        self.set_params({})
        self.report_type = "Layout:basic"
        self.item_filter = ""

    def get_params(self):
        try:
            return json.loads(self.params)
        except Exception:
            return {}

    def set_params(self, d: dict = None):
        if d is None:
            d = {}
        if type(d) is not dict:
            raise ValueError("Error: input must be a dictionary")
        self.params = json.dumps(d)
        return

    def change_type(self, t):
        if t == self.report_type:
            return
        # This is not ideal, but it can be handy
        # If we are converting to some specific types from the initial type and there is currently
        # no filtering set, set the filter to reject all data items, as for these template types it
        # can be more appropriate.
        if (t in ["Layout:toc", "Layout:header", "Layout:footer"]) and (
            self.report_type == "Layout:basic"
        ):
            if self.item_filter == "":
                self.item_filter = "A|i_name|eq|__NonexistantName__;"
        self.report_type = t
        self.set_dirty(True)

    def from_json(self, json_dict):
        # record our current guid
        tmpguid = self.guid
        # update attributes from json dict
        for key in json_dict:
            tmp = json_dict[key]
            # convert objects to UTF encoded str objects
            # If I use platform encoding instead of getfilesystemencoding, on win it gives me mbcs
            # which doesn't allow me to load templates with international characters.
            if type(tmp) == str:
                tmp = tmp.encode(sys.getfilesystemencoding()).decode("utf-8")
            if type(tmp) == bytes:
                tmp.decode("utf-8")
            setattr(self, key, tmp)
        # ok, re-order the children list to match the order in children_order
        sorted_guids = self.children_order.lower().split(",")
        sorted_guids.reverse()
        for guid in sorted_guids:
            idx = 0
            for childguid in self.children:
                if guid == str(childguid).lower():
                    self.children.insert(0, self.children.pop(idx))
                    break
                idx += 1
        # Instance specific initialization
        # this may have changed the guid, so
        if tmpguid != self.guid:
            self.__class__.add_template_object(self)
        self._dirty = False

    def get_dirty(self):
        if self._dirty:
            self.date = datetime.datetime.now(pytz.utc).isoformat()
        return self._dirty

    def set_dirty(self, d):
        self._dirty = d

    def get_date_object(self):
        return dateutil.parser.parse(self.date)

    def get_url_data(self):
        # children_order can be generated from children
        self.children_order = ""
        for guid in self.children:
            self.children_order += str(guid) + ","
        self.master = self.parent is None
        # Fields that match the REST API
        d = {}
        for key in [
            "guid",
            "date",
            "name",
            "tags",
            "master",
            "params",
            "report_type",
            "item_filter",
            "parent",
            "children",
            "children_order",
        ]:
            d[key] = getattr(self, key)
        return "/reports/api_detail/" + self.guid, d

    def get_url_file(self):
        return None

    def get_parent_object(self):
        return self.__class__.get_template_object(self.parent)

    def get_child_objects(self):
        ret = []
        for c in self.children:
            obj = self.__class__.get_template_object(c)
            if obj:
                ret.append(obj)
        return ret


class BaseRESTObject:
    # the api version of the REST client
    API_VERSION = 1.0

    def __init__(self):
        self.guid = str(uuid.uuid1())
        self.tags = ""
        # the REST obj needs to know the current server's api version
        # in order to determine how to parse the server's response
        self.server_api_version = None
        # to track whether an obj has already been saved(pushed)
        # we use this to decide if put_objects() is going to do an update
        # or a create.
        self._saved = False

    @property
    def saved(self):
        return self._saved

    def generate_new_guid(self):
        self.guid = str(uuid.uuid1())

    # These members should be overridden
    def get_url_file(self):
        return None

    @classmethod
    def get_json_keys(cls):
        return ["guid", "tags"]

    @classmethod
    def get_json_key_limits(cls):
        return {}

    @classmethod
    def get_url_base_name(cls):
        return "foo"

    # These most likely will not need to be overridden
    def get_detail_url(self):
        return f"/{self.get_url_base_name()}/api_detail/{self.guid}?version={self.API_VERSION}"

    @classmethod
    def get_list_url(cls):
        return f"/{cls.get_url_base_name()}/api_list?version={cls.API_VERSION}"

    def validate_url_data(self, key, value):
        # Fields that match the REST API
        # with simple length-based error checking...
        limit = self.get_json_key_limits().get(key, None)
        if limit:
            if len(value) > limit:
                raise ValueError(
                    "Attribute {} is limited to {} characters ({},'{}')".format(
                        key, str(limit), str(self), value
                    )
                )

    # this is used to serialize the data out of the REST object into JSON
    def get_url_data(self):
        data_dict = {}
        for key in self.get_json_keys():
            attr = getattr(self, key)
            self.validate_url_data(key, attr)
            data_dict[key] = attr

        return self.get_detail_url(), data_dict

    # this is used to deserialize JSON data into the REST obj.
    def from_json(self, json_dict):
        # serializes an existing object, so we mark it as saved.
        self._saved = True
        # update attributes from json dict
        for key in json_dict:
            # todo: check if the key is in get_json_keys before setting
            #  or just iterate through it like get_url_data.
            setattr(self, key, json_dict[key])

    def update_api_version(self, new_api_version):
        # subclasses may do conversions...
        self.server_api_version = new_api_version

    def get_tags(self):
        return self.tags

    def set_tags(self, s):
        self.tags = s

    @staticmethod
    def add_quotes(s):
        if (" " in s) and (s[0] != "'"):
            return "'" + s + "'"
        return s

    def rebuild_tags(self, v):
        tmp = list()
        for t in v:
            a = t.split("=")
            if len(a) > 1:
                tmp.append(self.add_quotes(a[0]) + "=" + self.add_quotes(a[1]))
            else:
                tmp.append(self.add_quotes(a[0]))
        self.set_tags(" ".join(tmp))

    def add_tag(self, tag, value=None):
        self.rem_tag(tag)
        tags = shlex.split(self.get_tags())
        if value:
            tags.append(tag + "=" + str(value))
        else:
            tags.append(tag)
        self.rebuild_tags(tags)

    def rem_tag(self, tag):
        tags = shlex.split(self.get_tags())
        for t in list(tags):
            if "=" in t:
                if t.split("=")[0] == tag:
                    tags.remove(t)
            elif t == tag:
                tags.remove(t)
        self.rebuild_tags(tags)


class DatasetREST(BaseRESTObject):
    """Simple representation of a database."""

    def __init__(self):
        super().__init__()
        self.filename = ""
        self.dirname = ""
        self.format = ""
        self.numparts = 0
        self.numelements = 0

    @classmethod
    def get_url_base_name(cls):
        return "dataset"

    @classmethod
    def get_json_keys(cls):
        return [
            "guid",
            "tags",
            "filename",
            "dirname",
            "format",
            "numparts",
            "numelements",
        ]

    @classmethod
    def get_json_key_limits(cls):
        d = super().get_json_key_limits()
        d["filename"] = 256
        d["dirname"] = 256
        d["format"] = 50
        return d


class SessionREST(BaseRESTObject):
    """Simple representation of a session."""

    def __init__(self):
        super().__init__()
        self.date = datetime.datetime.now(pytz.utc)
        self.hostname = ""
        self.version = ""
        self.platform = ""
        self.application = ""

    @classmethod
    def get_url_base_name(cls):
        return "session"

    @classmethod
    def get_json_keys(cls):
        return [
            "guid",
            "tags",
            "date",
            "hostname",
            "version",
            "platform",
            "application",
        ]

    @classmethod
    def get_json_key_limits(cls):
        d = super().get_json_key_limits()
        d["hostname"] = 50
        d["platform"] = 50
        d["application"] = 40
        d["version"] = 20
        return d


class ItemCategoryREST(BaseRESTObject):
    """Representation of an ItemCategory."""

    def __init__(self):
        super().__init__()
        # we dont support tags here.
        del self.tags
        self.name = ""
        self.date = datetime.datetime.now(pytz.utc)
        self._perms_and_groups = {}

    # make this read-only. All access to this has to go
    # through our utility methods below.
    # This is a dict of perms on the category and groups
    # that are assigned these perms.
    @property
    def perms_and_groups(self):
        return self._perms_and_groups

    @classmethod
    def get_url_base_name(cls):
        return "item-categories"

    def get_detail_url(self):
        return f"/api/{self.get_url_base_name()}/{self.guid}/"

    @classmethod
    def get_list_url(cls):
        return f"/api/{cls.get_url_base_name()}/"

    @classmethod
    def get_json_keys(cls):
        return ["guid", "date", "name", "perms_and_groups"]

    @classmethod
    def get_json_key_limits(cls):
        d = {
            "name": 80,
        }
        return d

    def validate_url_data(self, key, value):
        # inherited to do custom validation.
        super().validate_url_data(key, value)
        if key == "perms_and_groups":
            owner_groups = value.get("own_itemcategory")
            if not owner_groups:
                raise ValueError(
                    "The category '{}' must have at least one owner.({},'{}')".format(
                        str(self.guid), str(self), value
                    )
                )

    def _validate_group(self, group):
        if not group or not isinstance(group, report_utils.text_type):
            raise ValueError(f"Group names must be valid strings ({str(self)},'{group}')")

    def _validate_groups(self, groups):
        if isinstance(groups, (list, tuple, set)):
            for grp in groups:
                self._validate_group(grp)
        else:
            raise ValueError(
                "Groups must be a valid Python list, tuple or set, containing strings."
            )

    def get_url_data(self):
        _, data_dict = super().get_url_data()
        # until older APIs are rewritten the right way, we cannot change the base class's
        # handling of this. So we override url specifically here.
        # if the object was already saved, return the detail url to PUT, else list_url to POST.
        url = self.get_detail_url() if self.saved else self.get_list_url()
        return url, data_dict

    def from_json(self, json_dict):
        # self.perms_and_groups is read-only, so we have to pop it out
        # here because the super() call tries to set the value to the property
        # which ll throw an error. So set it manually to the proxy variable instead.
        perms_and_groups = json_dict.pop("perms_and_groups", None)
        # convert all group lists to sets for easier manipulation.
        for k, v in perms_and_groups.items():
            self._perms_and_groups[k] = set(v)
        # call base
        super().from_json(json_dict)

    def _get_groups(self, perm):
        return self._perms_and_groups.get(f"{perm}_itemcategory")

    @property
    def owners(self):
        return self._get_groups("own")

    @property
    def viewers(self):
        return self._get_groups("view")

    @property
    def changers(self):
        return self._get_groups("change")

    @property
    def deleters(self):
        return self._get_groups("delete")

    def _set_perms(self, perm, groups):
        # also allows empty iterables to mimic 'clearing'
        self._validate_groups(groups)
        self._perms_and_groups[f"{perm}_itemcategory"] = set(groups)

    @owners.setter
    def owners(self, groups):
        self._set_perms("own", groups)

    @viewers.setter
    def viewers(self, groups):
        self._set_perms("view", groups)

    @changers.setter
    def changers(self, groups):
        self._set_perms("change", groups)

    @deleters.setter
    def deleters(self, groups):
        self._set_perms("delete", groups)

    def _add_group_to_perm(self, perm, group):
        self._validate_group(group)
        perm_key = f"{perm}_itemcategory"
        curr_groups = self._perms_and_groups.get(perm_key, set())
        if curr_groups:
            curr_groups.add(group)
            self._perms_and_groups[perm_key] = curr_groups
        else:
            self._set_perms(perm, {group})

    def add_owner(self, group):
        self._add_group_to_perm("own", group)

    def add_viewer(self, group):
        self._add_group_to_perm("view", group)

    def add_changer(self, group):
        self._add_group_to_perm("change", group)

    def add_deleter(self, group):
        self._add_group_to_perm("delete", group)

    def _remove_group_from_perm(self, perm, group):
        self._validate_group(group)
        perm_key = f"{perm}_itemcategory"
        curr_groups = self._perms_and_groups.get(perm_key, set())
        if curr_groups:
            curr_groups.discard(group)
            self._perms_and_groups[perm_key] = curr_groups

    def remove_owner(self, group):
        self._remove_group_from_perm("own", group)

    def remove_viewer(self, group):
        self._remove_group_from_perm("view", group)

    def remove_changer(self, group):
        self._remove_group_from_perm("change", group)

    def remove_deleter(self, group):
        self._remove_group_from_perm("delete", group)


class ItemREST(BaseRESTObject):
    """Simple representation of a Item."""

    # the various report item payload types
    type_html = "html"  # a 'string' that is a valid HTML <div> block
    type_str = "string"  # a general string
    type_tbl = "table"  # dict: numpy array of dbls, list of col and row names
    type_img = "image"  # an image (in-memory .png or .jpg files)
    type_anim = "anim"  # an animation (in-memory .mp4 files)
    type_scn = "scene"  # a 3D geometry scene
    type_file = "file"  # a general file
    type_none = "none"  # no additional payload
    type_tree = "tree"  # payload is a dict representing a tree

    def __init__(self):
        super().__init__()
        self.sequence = 0
        self.date = datetime.datetime.now(pytz.utc)
        self.name = ""
        self.source = ""
        self.type = ItemREST.type_none
        self.session = ""
        self.dataset = ""
        self._categories = set()
        self.width = 0
        self.height = 0
        self._payloaddata = None
        # extra fields used by file I/O
        self.fileurl = None
        self.fileobj = None
        self.image_data = None

    @property
    def payloaddata(self):
        # NOTE: this param will be read-only from now on.
        return self._payloaddata

    def _validate_and_get_category(self, category):
        if category:
            if isinstance(category, str):
                return category
            elif isinstance(category, ItemCategoryREST):
                return category.name

        raise ValueError("Category has to be a valid string or an ItemCategoryREST object.")

    def _validate_and_get_categories(self, categories):
        if isinstance(categories, (list, tuple, set)):
            return {self._validate_and_get_category(cat) for cat in categories}

        raise ValueError(
            "Categories must be a valid Python list, tuple or set, containing strings or ItemCategoryREST objects."
        )

    @property
    def categories(self):
        return self._categories

    @categories.setter
    def categories(self, categories):
        self._categories = self._validate_and_get_categories(categories)

    def add_category(self, category):
        self._categories.add(self._validate_and_get_category(category))

    def remove_category(self, category):
        self._categories.discard(self._validate_and_get_category(category))

    @classmethod
    def get_url_base_name(cls):
        return "item"

    @classmethod
    def get_json_keys(cls):
        return [
            "guid",
            "tags",
            "sequence",
            "date",
            "name",
            "source",
            "type",
            "session",
            "dataset",
            "width",
            "height",
            "payloaddata",
            "categories",
        ]

    @classmethod
    def get_json_key_limits(cls):
        d = super().get_json_key_limits()
        d["name"] = 255
        d["source"] = 80
        d["type"] = 16
        return d

    def update_api_version(self, new_api_version):
        # this call is made if we were read from an older API server, but are now
        # being written to a newer API server.
        # Before API 1.0, the encoding of the payload data may have used an older
        # scheme.
        if (self.server_api_version is not None) and (self.server_api_version < 1.0):
            # note: unpickling a numpy array requires numpy to be available or will fail.
            content = extremely_ugly_hacks.safe_unpickle(self._payloaddata, item_type=self.type)
            # for non-table objects, the unpickle is all that is needed.  newer servers
            # cannot handle the older pickle encoding
            if self.type != self.type_tbl:
                self._payloaddata = content
            else:
                # for Table objects, changes in the storage of the array (moving to a dict
                # with extra metadata) is needed.  The set_payload_table() call handles this.
                self.set_payload_table(content)
        super().update_api_version(new_api_version)

    # override the call to get the JSON data to do some backwards compat ugliness.
    def get_url_data(self):
        detail_url, data_dict = super().get_url_data()
        # serialize categories properly
        categs = data_dict.get("categories")
        if categs:
            data_dict["categories"] = [{"name": cat} for cat in categs]
        # delay the payload's encoding until json data is requested.
        if "payloaddata" in data_dict:
            # for request to older servers
            # has to send a pickled string
            if (self.server_api_version is not None) and (self.server_api_version < 1.0):
                # Note: we do not support a python 3 client talking to a python 2 server.
                # A python 2 Nexus server has no knowledge of this base64 encoding scheme.
                # We need to encode the bytes into an ASCII string...  This output likely came
                # from pickle( protocol=0), but that can still include 'latin-1' chars that are
                # not strictly ASCII. So we treat it as binary and base64 encode it to make an
                # ASCII string.  We need a prefix to know when to decode this string.
                data_dict["payloaddata"] = "!@P0@!" + base64.b64encode(
                    pickle.dumps(data_dict["payloaddata"], protocol=0)
                ).decode("utf-8")
            else:
                # otherwise future versions use json dumps.
                data_dict["payloaddata"] = json.dumps(
                    data_dict["payloaddata"], cls=PayloaddataEncoder
                )

        return detail_url, data_dict

    def from_json(self, json_dict):
        # self.categories and self.payloaddata are read-only, so we have to pop it out
        # here because the super() call tries to set the value to the property
        # which ll throw an error. So set it manually to the proxy variable instead.
        categories = json_dict.pop("categories", None)
        if categories:
            # deserialize categories to a set for easier manipulation.
            self._categories = {cat["name"] for cat in categories}
        # for older servers, this will return the pickled string,
        # which can later be loaded on demand using get_payload_content(),
        # just as before.
        # for newer servers, this will give the actual payload
        self._payloaddata = json_dict.pop("payloaddata", None)
        # base call
        super().from_json(json_dict)

    def get_payload_content(self, as_list=False):
        # if you dont copy.copy, it'll modify the array in the original variable
        # which we dont want.
        ret = copy.copy(self._payloaddata)
        # for response from older servers
        # has to expect a pickled string
        if (self.server_api_version is not None) and (self.server_api_version < 1.0):
            # note: unpickling a numpy array requires numpy to be available or will fail.
            ret = extremely_ugly_hacks.safe_unpickle(ret, item_type=self.type)

        # by default, arrays are returned as numpy arrays if the user has numpy installed.
        # if the user doesn't want that, they can specify as_list=True
        # to return lists.
        # Of course, if its not a table, none of this makes sense.
        if self.type == ItemREST.type_tbl:
            if isinstance(ret, dict):
                # now get the actual array.
                array = ret.get("array")
                if array is not None:
                    # if its a nexus_array, the flag as_list is always assumed to be true
                    # because the user never knows there's a nexus_array yet and always
                    # sees/expects a list. This should change in future.
                    if isinstance(array, report_utils.nexus_array):
                        ret.update(array.to_json())
                        return ret

                    if as_list:
                        # if a list is to be returned, we convert the numpy array
                        if has_numpy and isinstance(array, numpy.ndarray):
                            ret.update(
                                {
                                    "array": array.tolist(),
                                    "shape": array.shape,
                                    "size": array.size,
                                    "dtype": str(array.dtype),
                                }
                            )
                    else:
                        if has_numpy:
                            dtype = ret.get("dtype")
                            if not isinstance(array, numpy.ndarray) and dtype:
                                if "S" in dtype:
                                    # if the intended type is bytes, we have to explicitly encode
                                    array = numpy.char.encode(array, encoding="utf-8").astype(dtype)
                                else:
                                    # default: numpy array of double type
                                    array = numpy.array(array, dtype=dtype)

                                ret.update(
                                    {
                                        "array": array,
                                        "shape": array.shape,
                                        "size": array.size,
                                        "dtype": str(array.dtype),
                                    }
                                )

        return ret

    def get_url_file(self):
        if self.fileurl and self.fileobj:
            url = "/item/api_payload/" + self.guid
            f, e = os.path.splitext(self.fileurl)
            if e.lower() == ".png":
                fname = "image.png"
            elif e.lower() == ".csf":
                fname = "scene.csf"
            elif e.lower() == ".ply":
                fname = "scene.ply"
            elif e.lower() == ".stl":
                fname = "scene.stl"
            elif e.lower() == ".avz":
                fname = "scene.avz"
            elif e.lower() == ".mp4":
                fname = "movie.mp4"
            else:
                fname = "file" + e
            self.fileobj.seek(0)
            return url, fname, self.fileobj
        return None

    def is_file_protocol(self):
        return self.type in [
            ItemREST.type_img,
            ItemREST.type_scn,
            ItemREST.type_anim,
            ItemREST.type_file,
        ]

    def set_payload_none(self):
        self.type = ItemREST.type_none
        self._payloaddata = ""

    def set_payload_string(self, s):
        self.type = ItemREST.type_str
        self._payloaddata = s

    def set_payload_html(self, s):
        self.type = ItemREST.type_html
        self._payloaddata = s

    @staticmethod
    def validate_tree_value(value):
        # if its a list of values, validate them recursively.
        if isinstance(value, list):
            for v in value:
                ItemREST.validate_tree_value(v)
        else:
            type_ = type(value)
            if sys.version_info[0] < 3:
                if type_ not in [
                    float,
                    int,
                    datetime.datetime,
                    str,
                    bool,
                    uuid.UUID,
                    type(None),
                    unicode,
                ]:
                    raise ValueError(f"{str(type_)} is not a valid Tree payload 'value' type")
            else:
                if type_ not in [float, int, datetime.datetime, str, bool, uuid.UUID, type(None)]:
                    raise ValueError(f"{str(type_)} is not a valid Tree payload 'value' type")

    @staticmethod
    def validate_tree(t):
        if type(t) != list:
            raise ValueError("The tree payload must be a list of dictionaries")
        for i in t:
            if type(i) != dict:
                raise ValueError("The tree payload must be a list of dictionaries")
            if "key" not in i:
                raise ValueError("Tree payload dictionaries must have a 'key' key")
            if "name" not in i:
                raise ValueError("Tree payload dictionaries must have a 'name' key")
            if "value" not in i:
                raise ValueError("Tree payload dictionaries must have a 'value' key")
            if "children" in i:
                ItemREST.validate_tree(i["children"])
            # validate tree value
            ItemREST.validate_tree_value(i["value"])

    def set_payload_tree(self, t):
        self.validate_tree(t)
        self.type = ItemREST.type_tree
        self._payloaddata = t

    def set_payload_table(self, table_input):
        # Set up a dummy table dictionary that can be filled in later
        payloaddata = None
        if table_input is None:
            # if we have nothing, build our own
            if has_numpy:
                array = numpy.zeros((1, 1), numpy.double)
            else:
                array = report_utils.nexus_array(dtype="f8", shape=(1, 1))
            payloaddata = {
                "array": array,
                "rowlbls": None,
                "collbls": None,
                "title": None,
                "row_tags": None,
                "col_tags": None,
            }
        elif isinstance(table_input, dict):
            # obtain the dtype if its not set and we have numpy to get it from
            dtype = table_input.get("dtype")
            array = table_input.get("array")
            if not dtype and has_numpy and isinstance(array, numpy.ndarray):
                table_input.update({"dtype": str(array.dtype)})
            payloaddata = table_input
        else:
            ensight_dict = map_ensight_plot_to_table_dictionary(table_input)
            if ensight_dict is not None:
                payloaddata = ensight_dict

        if payloaddata is not None:
            validated_payload = self.validate_and_clean_table(payloaddata)
            self.type = ItemREST.type_tbl
            self._payloaddata = validated_payload
        else:
            raise TypeError("The input value must be a dictionary or None")

    def set_payload_table_values(
        self,
        array,
        dtype=None,
        rowlbls=None,
        collbls=None,
        title=None,
        row_tags=None,
        col_tags=None,
    ):
        d = {
            "array": array,
            "dtype": dtype,
            "rowlbls": rowlbls,
            "collbls": collbls,
            "title": title,
            "row_tags": row_tags,
            "col_tags": col_tags,
        }
        self.set_payload_table(d)

    # A special validity check for table objects
    def validate_and_clean_table(self, value):
        # in case the array is missing
        array = value.get("array", [[1]])
        dtype = value.get("dtype", "f8")  # Default is a double

        # NOTE: We provide 2 options to the user:
        # 1. user can provide a prebuilt numpy array OR
        # 2. user can provide a list and if so,  we will cast to numpy or nexus_array from
        # the dtype specified in the payload. This is because it's hard to guess the intended
        # type of the final array(and also inefficient) from every single element of the list.
        if has_numpy:
            if not isinstance(array, numpy.ndarray):
                # this will convert lists to numpy arrays from dtype in payload.
                array = numpy.array(array, dtype)
            kind = array.dtype.kind
        else:
            if not isinstance(array, report_utils.nexus_array):
                nexus_array = report_utils.nexus_array(dtype=dtype, shape=(1, 1))
                nexus_array.from_2dlist(array)
                array = nexus_array
            kind = array.dtype[0]

        # valid array types are bytes and float for now
        if kind not in ["S", "f"]:
            raise ValueError("Table array must be a bytes or float type.")

        shape = array.shape
        size = array.size

        nrows = 0
        ncols = 0
        # labels
        rowlbls = value.get("rowlbls", None)
        if rowlbls:
            nrows = len(rowlbls)
        collbls = value.get("collbls", None)
        if collbls:
            ncols = len(collbls)
        # proper shape???
        if len(shape) == 1:
            if nrows:
                shape = (nrows, size / nrows)
            elif ncols:
                shape = (size / ncols, ncols)
            else:
                shape = (1, size)
            array.shape = shape
        elif len(shape) != 2:
            raise ValueError("Table array must be 2D.")

        # update after validation
        value.update(
            {"array": array, "dtype": str(array.dtype), "shape": array.shape, "size": array.size}
        )
        return value

    def set_payload_image(self, img):
        if has_qt:  # pragma: no cover
            if isinstance(img, QtGui.QImage):
                tmpimg = img
            elif report_utils.is_enve_image(img):
                image_data = report_utils.enve_image_to_data(img, str(self.guid))
                if image_data is not None:
                    self.width = image_data["width"]
                    self.height = image_data["height"]
                    self.type = ItemREST.type_img
                    # set up the parameters for get_url_file(): self.fileurl and self.fileobj
                    self.image_data = image_data["file_data"]
                    self.fileobj = io.BytesIO(self.image_data)
                    # The format might be png or tif, make sure the name the URL properly
                    # or Nexus will generate the incorrect display code.
                    self.fileurl = "image." + image_data["format"]
                return
            else:
                import imghdr

                fmt = imghdr.what("/dummy", img)
                tmpimg = QtGui.QImage.fromData(img, fmt)
            # record the GUID in the image (watermark it)
            # note: the Qt PNG format supports text keys
            tmpimg.setText("CEI_NEXUS_GUID", str(self.guid))
            # save it in PNG format in memory
            be = QtCore.QByteArray()
            buf = QtCore.QBuffer(be)
            buf.open(QtCore.QIODevice.WriteOnly)
            tmpimg.save(buf, "png")
            buf.close()
            # s is an in-memory representation of a .png file
            # width and height are its size
            s = bytes(be)
            width = tmpimg.width()
            height = tmpimg.height()
        else:
            try:
                from . import png
            except Exception:
                import png
            # we can only read png images as string content (not filename)
            reader = png.Reader(io.BytesIO(img))
            # parse the input file
            pngobj = reader.read()
            width = pngobj[3]["size"][0]
            height = pngobj[3]["size"][1]
            imgdata = list(pngobj[2])
            # tag the data and write it back out...
            writer = png.Writer(
                width=width,
                height=height,
                bitdepth=pngobj[3].get("bitdepth", 8),
                greyscale=pngobj[3].get("greyscale", False),
                alpha=pngobj[3].get("alpha", False),
                planes=pngobj[3].get("planes", None),
                palette=pngobj[3].get("palette", None),
            )
            # TODO: current version does not support set_text()?
            # writer.set_text(dict(CEI_NEXUS_GUID=str(self.guid)))
            io_in = io.BytesIO()
            writer.write(io_in, imgdata)
            s = io_in.getvalue()
        # common options
        self.width = width
        self.height = height
        self.type = ItemREST.type_img
        # set up the parameters for get_url_file(): self.fileurl and self.fileobj
        self.image_data = s
        self.fileobj = io.BytesIO(self.image_data)
        self.fileurl = "image.png"

    def set_payload_animation(self, mp4_filename):
        # filename is required to be UTF8, but the low-level I/O may not take UTF-8
        self.type = ItemREST.type_anim
        self.fileobj = open(mp4_filename, "rb")
        self.fileurl = mp4_filename

    def set_payload_file(self, filename):
        # filename is required to be UTF8, but the low-level I/O may not take UTF-8
        self.type = ItemREST.type_file
        self.fileobj = open(filename, "rb")
        self.fileurl = filename

    def set_payload_scene(self, filename):
        # filename is required to be UTF8, but the low-level I/O may not take UTF-8
        self.type = ItemREST.type_scn
        self.fileobj = open(filename, "rb")
        self.fileurl = filename


class TemplateREST(BaseRESTObject):
    """Simple representation of a Template."""

    @classmethod
    def factory(cls, json_data):
        if "report_type" in json_data:
            exec(
                "tmp_cls = " + json_data["report_type"].split(":")[1] + "REST()",
                locals(),
                globals(),
            )
            return tmp_cls
        else:
            return TemplateREST()

    def __init__(self):
        super().__init__()
        self.date = datetime.datetime.now(pytz.utc)
        self.name = ""
        self.params = json.dumps({})
        self.report_type = "Layout:basic"
        self.item_filter = ""
        self.parent = None
        self.children = list()
        # computed values from 'children'
        self.children_order = ""
        self.master = True

    # override the call to get the JSON data, first compute a couple of
    # attributes, then call the superclass
    def get_url_data(self):
        # children_order can be generated from children
        self.children_order = ""
        for guid in self.children:
            self.children_order += str(guid) + ","
        # configure the master flag
        self.master = self.parent is None
        # call the superclass
        return super().get_url_data()

    # When the template is read, the order of the objects in the children list can be
    # arbitrary.  The children_order string contains the correct order.  This method
    # reorders the children list to be correct.
    def reorder_children(self):
        sorted_guids = self.children_order.lower().split(",")
        sorted_guids.reverse()
        # return the children based on the order of guids in children_order
        for guid in sorted_guids:
            if len(guid):
                idx = 0
                for child in self.children:
                    if guid == str(child).lower():
                        self.children.insert(0, self.children.pop(idx))
                        break
                    idx += 1

    @classmethod
    def get_url_base_name(cls):
        return "reports"

    @classmethod
    def get_json_keys(cls):
        return [
            "guid",
            "date",
            "name",
            "tags",
            "master",
            "params",
            "report_type",
            "item_filter",
            "parent",
            "children",
            "children_order",
        ]

    @classmethod
    def get_json_key_limits(cls):
        d = super().get_json_key_limits()
        d["name"] = 255
        d["report_type"] = 50
        d["params"] = 4096
        d["filter"] = 1024
        return d

    def add_params(self, d: dict = None):
        if d is None:
            d = {}
        if type(d) is not dict:
            raise ValueError("Error: input must be a dictionary")
        try:
            tmp_params = json.loads(self.params)
            for k in d:
                tmp_params[k] = d[k]
            self.params = json.dumps(tmp_params)
            return
        except Exception:
            return {}

    def get_params(self):
        try:
            return json.loads(self.params)
        except Exception:
            return {}

    def set_params(self, d: dict = None):
        if d is None:
            d = {}
        if type(d) is not dict:
            raise ValueError("Error: input must be a dictionary")
        self.params = json.dumps(d)
        return

    def get_sort_fields(self):
        if "sort_fields" in json.loads(self.params):
            return json.loads(self.params)["sort_fields"]
        else:
            return []

    def get_property(self):
        if "properties" in json.loads(self.params):
            return json.loads(self.params)["properties"]
        else:
            return {}

    def set_property(self, property: dict = None):
        if property is None:
            property = {}
        if type(property) is not dict:
            raise ValueError("Error: input must be a dictionary")
        d = json.loads(self.params)
        d["properties"] = property
        self.params = json.dumps(d)
        return

    def add_property(self, property: dict = None):
        if property is None:
            property = {}
        if type(property) is not dict:
            raise ValueError("Error: input must be a dictionary")
        d = json.loads(self.params)
        if "properties" not in d:
            d["properties"] = {}
        for k in property.keys():
            d["properties"][k] = property[k]
        self.params = json.dumps(d)
        return

    def set_sort_fields(self, sort_field):
        if type(sort_field) is list:
            d = json.loads(self.params)
            d["sort_fields"] = sort_field
            self.params = json.dumps(d)
        else:
            raise ValueError("Error: sorting filter is not a list")

    def add_sort_fields(self, sort_field):
        if type(sort_field) is list:
            d = json.loads(self.params)
            d["sort_fields"].extend(sort_field)
            self.params = json.dumps(d)
        else:
            raise ValueError("Error: sorting filter is not a list")

    def get_sort_selection(self):
        if "sort_selection" in json.loads(self.params):
            return json.loads(self.params)["sort_selection"]
        else:
            return ""

    def set_sort_selection(self, value="all"):
        if type(value) is not str:
            raise ValueError("Error: sort selection input should be a string")
        if value not in ["all", "first", "last"]:
            raise ValueError("Error: sort selection not among the acceptable inputs")
        d = json.loads(self.params)
        d["sort_selection"] = value
        self.params = json.dumps(d)
        return

    def get_filter(self):
        return self.item_filter

    def set_filter(self, filter_str=""):
        if type(filter_str) is str:
            self.item_filter = filter_str
        else:
            raise ValueError("Error: filter value should be a string")

    def add_filter(self, filter_str=""):
        if type(filter_str) is str:
            self.item_filter += filter_str
        else:
            raise ValueError("Error: filter value should be a string")

    def get_filter_mode(self):
        if "filter_type" in json.loads(self.params):
            return json.loads(self.params)["filter_type"]
        else:
            return "items"

    def set_filter_mode(self, value="items"):
        if type(value) is not str:
            raise ValueError("Error: filter mode input should be a string")
        if value not in ["items", "root_replace", "root_append"]:
            raise ValueError("Error:  filter mode not among the acceptable inputs")
        d = json.loads(self.params)
        d["filter_type"] = value
        self.params = json.dumps(d)
        return

    def get_html(self):
        if "Layout:" in self.report_type:
            if "HTML" in json.loads(self.params):
                return json.loads(self.params)["HTML"]
            else:
                return ""
        else:
            raise ValueError(f"Error: HTML not supported on the report type {self.report_type}")


class LayoutREST(TemplateREST):
    """Representation of the common Layout Template."""

    def __init__(self):
        super().__init__()

    def get_column_count(self):
        if "column_count" in json.loads(self.params):
            return json.loads(self.params)["column_count"]
        else:
            return 1

    def set_column_count(self, value):
        if type(value) is not int:
            raise ValueError("Error: column count input should be an integer")
        if value <= 0:
            raise ValueError("Error: column count input should be larger than 0")
        d = json.loads(self.params)
        d["column_count"] = value
        self.params = json.dumps(d)
        return

    def get_column_widths(self):
        if "column_widths" in json.loads(self.params):
            return json.loads(self.params)["column_widths"]
        else:
            return [1.0]

    def set_column_widths(self, value):
        if type(value) is not list:
            raise ValueError("Error: column widths input should be a list")
        d = json.loads(self.params)
        d["column_widths"] = value
        self.params = json.dumps(d)
        return

    def set_html(self, value=""):
        if "Layout:" in self.report_type:
            if type(value) is str:
                d = json.loads(self.params)
                d["HTML"] = value
                self.params = json.dumps(d)
                return
            else:
                raise ValueError("Error: input needs to be a string")
        else:
            raise ValueError(f"Error: HTML not supported on the report type {self.report_type}")

    def set_comments(self, value=""):
        if "Layout:" in self.report_type:
            if isinstance(value, str):
                d = json.loads(self.params)
                d["comments"] = value
                self.params = json.dumps(d)
                return
            else:
                raise ValueError("Error: input needs to be a string")
        else:
            raise ValueError(f"Error: Comments not supported on the report type {self.report_type}")

    def get_transpose(self):
        if "Layout:" in self.report_type:
            if "transpose" in json.loads(self.params):
                return json.loads(self.params)["HTML"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: transpose columns/rows not supported on the report type {self.report_type}"
            )

    def set_transpose(self, value=0):
        if "Layout:" in self.report_type:
            if type(value) is int:
                if value not in [0, 1]:
                    raise ValueError("Error: input needs to be either 0 or 1")
                d = json.loads(self.params)
                d["transpose"] = value
                self.params = json.dumps(d)
                return
            else:
                raise ValueError("Error: input needs to be an integer (0 or 1)")
        else:
            raise ValueError(
                f"Error: transpose columns/rows not supported on the report type {self.report_type}"
            )

    def get_skip(self):
        if "Layout:" in self.report_type:
            if "skip_empty" in json.loads(self.params):
                return json.loads(self.params)["skip_empty"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: skip empty not supported on the report type {self.report_type}"
            )

    def set_skip(self, value=0):
        if "Layout:" in self.report_type:
            if type(value) is int:
                if value not in [0, 1]:
                    raise ValueError("Error: input needs to be either 0 or 1")
                d = json.loads(self.params)
                d["skip_empty"] = value
                self.params = json.dumps(d)
                return
            else:
                raise ValueError("Error: input needs to be an integer (0 or 1)")
        else:
            raise ValueError(
                f"Error: skip empty not supported on the report type {self.report_type}"
            )


class GeneratorREST(TemplateREST):
    """Representation of the common Generator Template."""

    def __init__(self):
        super().__init__()

    def get_generated_items(self):
        if "generate_merge" in json.loads(self.params):
            return json.loads(self.params)["generate_merge"]
        else:
            return "add"

    def set_generated_items(self, value):
        if type(value) is not str:
            raise ValueError("Error: generated items should be a string")
        if value not in ["add", "replace"]:
            raise ValueError("Error: input should be add or replace")
        d = json.loads(self.params)
        d["generate_merge"] = value
        self.params = json.dumps(d)
        return

    def get_append_tags(self):
        if "generate_appendtags" in json.loads(self.params):
            return json.loads(self.params)["generate_appendtags"]
        else:
            return True

    def set_append_tags(self, value=True):
        if type(value) is not bool:
            raise ValueError("Error: value should be True / False")
        if value not in [True, False]:
            raise ValueError("Error: input should be add or replace")
        d = json.loads(self.params)
        d["generate_appendtags"] = value
        self.params = json.dumps(d)
        return


class basicREST(LayoutREST):
    """Representation of Column Layout Template."""

    def __init__(self):
        super().__init__()


class panelREST(LayoutREST):
    """Representation of Panel Layout Template."""

    def __init__(self):
        super().__init__()

    def get_panel_style(self):
        if "style" in json.loads(self.params):
            return json.loads(self.params)["style"]
        else:
            return ""

    def set_panel_style(self, value="panel"):
        if type(value) is not str:
            raise ValueError("Error: panel style mode input should be a string")
        if value not in [
            "panel",
            "callout-default",
            "callout-danger",
            "callout-warning",
            "callout-success",
            "callout-info",
        ]:
            raise ValueError("Error:  panel style mode not among the acceptable inputs")
        d = json.loads(self.params)
        d["style"] = value
        self.params = json.dumps(d)
        return

    def get_items_as_link(self):
        if "items_as_links" in json.loads(self.params):
            return json.loads(self.params)["items_as_links"]
        else:
            return 0

    def set_items_as_link(self, value=0):
        if type(value) is not int:
            raise ValueError("Error: show items as link input should be an integer")
        if value not in [0, 1]:
            raise ValueError("Error: show items as link input not among the acceptable values")
        d = json.loads(self.params)
        d["items_as_links"] = value
        self.params = json.dumps(d)
        return


class boxREST(LayoutREST):
    """Representation of Box Layout Template."""

    def __init__(self):
        super().__init__()

    def get_children_layout(self):
        if "boxes" in json.loads(self.params):
            return json.loads(self.params)["boxes"]
        else:
            return {}

    def set_child_position(self, guid=None, value=None):
        if value is None:
            value = [0, 0, 10, 10]
        if type(value) is not list:
            raise ValueError("Error: child position should be a list")
        if len(value) != 4:
            raise ValueError("Error: child position should contain 4 values")
        if len([x for x in value if type(x) is not int]) > 0:
            raise ValueError("Error: child position array should contain only integers")
        try:
            uuid.UUID(guid, version=4)
        except Exception:
            raise ValueError("Error: input guid is not a valid guid")
        d = json.loads(self.params)
        if "boxes" not in d:
            d["boxes"] = {}
        if guid not in d["boxes"]:
            d["boxes"][guid] = [0, 0, 0, 0, "self"]
        value.append(d["boxes"][guid][4])
        d["boxes"][guid] = value
        self.params = json.dumps(d)
        return

    def set_child_clip(self, guid=None, clip="self"):
        if type(clip) is not str:
            raise ValueError("Error: child clip parameter should be a string")
        if clip not in ["self", "scroll", "none"]:
            raise ValueError("Error: child clip parameter not among the accepted values")
        try:
            import uuid

            uuid.UUID(guid, version=4)
        except Exception:
            raise ValueError("Error: input guid is not a valid guid")
        d = json.loads(self.params)
        if "boxes" not in d:
            d["boxes"] = {}
        if guid not in d["boxes"]:
            d["boxes"][guid] = [0, 0, 0, 0, "self"]
        tmp_value = d["boxes"][guid][0:4]
        tmp_value.append(clip)
        d["boxes"][guid] = tmp_value
        self.params = json.dumps(d)
        return


class tabsREST(LayoutREST):
    """Representation of Tab Layout Template."""

    def __init__(self):
        super().__init__()


class carouselREST(TemplateREST):
    """Representation of Carousel Layout Template."""

    def __init__(self):
        super().__init__()

    def get_animated(self):
        if "animate" in json.loads(self.params):
            return json.loads(self.params)["animate"]
        else:
            return 0

    def set_animated(self, value=0):
        if type(value) is not int:
            raise ValueError("Error: Animated input not valid. Should be an integer")
        d = json.loads(self.params)
        d["animate"] = value
        self.params = json.dumps(d)
        return

    def get_slide_dots(self):
        if "maxdots" in json.loads(self.params):
            return json.loads(self.params)["maxdots"]
        else:
            return 20

    def set_slide_dots(self, value=20):
        if type(value) is not int:
            raise ValueError("Error: slide dots input not valid. Should be an integer")
        d = json.loads(self.params)
        d["maxdots"] = value
        self.params = json.dumps(d)
        return


class sliderREST(LayoutREST):
    """Representation of Slider Layout Template."""

    def __init__(self):
        super().__init__()

    def get_map_to_slider(self):
        slider = []
        if "slider_tags" in json.loads(self.params):
            for v in split_quoted_string_list(json.loads(self.params)["slider_tags"]):
                slider.append(v)
            return slider
        else:
            return []

    def set_map_to_slider(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: slider tags input not valid. Should be a list")
        for i in value:
            if i.split("|")[1] not in [
                "text_up",
                "text_down",
                "numeric_up",
                "numeric_down",
                "none",
            ]:
                raise ValueError("Error: the input sorting parameter is not supported")
        d = json.loads(self.params)
        mys = []
        for i in value:
            mys.append(i)
        d["slider_tags"] = str(mys)[1:-1]
        self.params = json.dumps(d)
        return

    def add_map_to_slider(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: slider tags input not valid. Should be a list")
        for i in value:
            if i.split("|")[1] not in [
                "text_up",
                "text_down",
                "numeric_up",
                "numeric_down",
                "none",
            ]:
                raise ValueError("Error: the input sorting parameter is not supported")
        d = json.loads(self.params)
        mys = d["slider_tags"]
        mys += ",'"
        for i in value:
            mys += i + "','"
        d["slider_tags"] = mys[0:-2]
        self.params = json.dumps(d)
        return


class footerREST(LayoutREST):
    """Representation of Page Footer Layout Template."""

    def __init__(self):
        super().__init__()


class headerREST(LayoutREST):
    """Representation of Page Header Layout Template."""

    def __init__(self):
        super().__init__()


class iteratorREST(LayoutREST):
    """Representation of Iterator Layout Template."""

    def __init__(self):
        super().__init__()

    def get_iteration_tags(self):
        it_tags = []
        if "tag" in json.loads(self.params):
            it_tags.append(json.loads(self.params)["tag"])
        else:
            it_tags.append("")
        if "secondary_tag" in json.loads(self.params):
            it_tags.append(json.loads(self.params)["secondary_tag"])
        else:
            it_tags.append("")
        return it_tags

    def set_iteration_tags(self, value=None):
        if value is None:
            value = ["", ""]
        if type(value) is not list:
            raise ValueError("Error: input needs to be a list")
        if len(value) != 2:
            raise ValueError(
                "Error: input list needs to contain 2 elements: iteration tag and secondary sorting tag"
            )
        if len([x for x in value if type(x) is str]) != 2:
            raise ValueError("Error: input tags need to be strings")
        d = json.loads(self.params)
        d["tag"] = value[0]
        d["secondary_tag"] = value[1]
        self.params = json.dumps(d)
        return

    def get_sort_tag(self):
        sort_int = []
        if "sort" in json.loads(self.params):
            sort_int.append(json.loads(self.params)["sort"])
        else:
            sort_int.append(True)
        if "reverse_sort" in json.loads(self.params):
            sort_int.append(json.loads(self.params)["reverse_sort"])
        else:
            sort_int.append(False)
        return sort_int

    def set_sort_tag(self, value=None):
        if value is None:
            value = [True, False]
        if type(value) is not list:
            raise ValueError("Error: input needs to be a list")
        if len(value) != 2:
            raise ValueError(
                "Error: input list needs to contain 2 elements: sort items by tag and reverse the sort"
            )
        if len([x for x in value if type(x) is bool]) != 2:
            raise ValueError("Error: input tags need to be True/False values")
        d = json.loads(self.params)
        d["sort"] = value[0]
        if value[0] is False:
            d["reverse_sort"] = False
        else:
            d["reverse_sort"] = value[1]
        self.params = json.dumps(d)
        return


class tagpropsREST(LayoutREST):
    """Representation of Tags to Properties Conversion Layout Template."""

    def __init__(self):
        super().__init__()


class tocREST(LayoutREST):
    """Representation of Table of Contents Layout Template."""

    def __init__(self):
        super().__init__()

    def get_toc(self):
        if (
            ("TOCitems" in json.loads(self.params))
            and ("TOCfigures" in json.loads(self.params))
            and ("TOCtables" in json.loads(self.params))
        ):
            if json.loads(self.params)["TOCfigures"] == 1:
                return "figure"
            elif json.loads(self.params)["TOCtables"] == 1:
                return "table"
            elif json.loads(self.params)["TOCitems"] == 1:
                return "toc"
            else:
                return None
        else:
            return None

    def set_toc(self, option="toc"):
        if option not in ["toc", "figure", "table"]:
            raise ValueError(
                "Error: input needs to be one of the accepted values: toc, figure, table"
            )
        d = json.loads(self.params)
        if option == "toc":
            d["TOCitems"] = 1
            d["TOCfigures"] = 0
            d["TOCtables"] = 0
        elif option == "figure":
            d["TOCitems"] = 0
            d["TOCfigures"] = 1
            d["TOCtables"] = 0
        elif option == "table":
            d["TOCitems"] = 0
            d["TOCfigures"] = 0
            d["TOCtables"] = 1
        self.params = json.dumps(d)
        return


class reportlinkREST(LayoutREST):
    """Representation of Linked Report Layout Template."""

    def __init__(self):
        super().__init__()

    def get_report_link(self):
        if "report_guid" in json.loads(self.params):
            if json.loads(self.params)["report_guid"] == "":
                return None
            else:
                return json.loads(self.params)["report_guid"]
        else:
            return None

    def set_report_link(self, link=None):
        d = json.loads(self.params)
        if link is None:
            d["report_guid"] = ""
            self.params = json.dumps(d)
            return
        else:
            try:
                uuid.UUID(link, version=4)
                d["report_guid"] = link
                self.params = json.dumps(d)
                return
            except Exception:
                raise ValueError("Error: input guid is not a valid guid")


class tablemergeREST(GeneratorREST):
    """Representation of Table Merge Generator Template."""

    def __init__(self):
        super().__init__()

    def get_merging_param(self):
        if "merge_params" in json.loads(self.params):
            if "merge_type" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["merge_type"]
        return "row"

    def set_merging_param(self, value="row"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        if value not in ["row", "column"]:
            raise ValueError("Error: input should be either row or column")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["merge_type"] = value
        self.params = json.dumps(d)
        return

    def get_table_name(self):
        if "merge_params" in json.loads(self.params):
            if "table_name" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["table_name"]
        return ""

    def set_table_name(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["table_name"] = value
        self.params = json.dumps(d)
        return

    def get_sources(self):
        if "merge_params" in json.loads(self.params):
            if "source_rows" in json.loads(self.params)["merge_params"]:
                sources = []
                for i in shlex.split(json.loads(self.params)["merge_params"]["source_rows"]):
                    sources.append(i.replace(",", ""))
                return sources
        return ["*|duplicate"]

    def set_sources(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        for v in value:
            if v.split("|")[1] not in ["duplicate", "merge", "rename_tag", "rename_nametag"]:
                raise ValueError(
                    "Error: the input does not contain one of the acceptable conditions"
                )
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["source_rows"] = ", ".join(repr(x) for x in value)
        self.params = json.dumps(d)
        return

    def add_sources(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        for v in value:
            if v.split("|")[1] not in ["duplicate", "merge", "rename_tag", "rename_nametag"]:
                raise ValueError(
                    "Error: the input does not contain one of the acceptable conditions"
                )
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["source_rows"] = ", ".join(
            [d["merge_params"]["source_rows"], ", ".join(repr(x) for x in value)]
        )
        self.params = json.dumps(d)
        return

    def get_rename_tag(self):
        if "merge_params" in json.loads(self.params):
            if "collision_tag" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["collision_tag"]
        return ""

    def set_rename_tag(self, value: str = ""):
        if type(value) is not str:
            raise ValueError("Error: the input should be a string")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["collision_tag"] = value
        self.params = json.dumps(d)
        return

    def get_use_labels(self):
        if "merge_params" in json.loads(self.params):
            if "column_labels_as_ids" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_labels_as_ids"]
        return 1

    def set_use_labels(self, value: int = 1):
        if type(value) is not int:
            raise ValueError("Error: the input should be an integer")
        if value not in [0, 1]:
            raise ValueError("Error: the input should be 0/1")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["column_labels_as_ids"] = value
        self.params = json.dumps(d)
        return

    def get_use_ids(self):
        if "merge_params" in json.loads(self.params):
            if "column_labels_as_ids" in json.loads(self.params)["merge_params"]:
                if json.loads(self.params)["merge_params"]["column_labels_as_ids"] == 1:
                    return ""
            if "column_id_row" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_id_row"]
        return ""

    def set_use_ids(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: the input should be a string")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        if d["merge_params"]["column_labels_as_ids"] == 1:
            if d["merge_params"]["merge_type"] == "column":
                raise ValueError(
                    "Error: can not set the Column to use as row IDs while Use row labels as row IDs is ON"
                )
            else:
                raise ValueError(
                    "Error: can not set the Row to use as column IDs while Use column labels as column IDs is ON"
                )
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["column_id_row"] = value
        self.params = json.dumps(d)
        return

    def get_id_selection(self):
        if "merge_params" in json.loads(self.params):
            if "column_merge" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_merge"]
        return "all"

    def set_id_selection(self, value="all"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        if value not in ["all", "intersect", "select"]:
            raise ValueError("Error: input should be one of all / intersect / select")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["column_merge"] = value
        self.params = json.dumps(d)
        return

    def get_ids(self):
        if "merge_params" in json.loads(self.params):
            if "column_merge" in json.loads(self.params)["merge_params"]:
                if json.loads(self.params)["merge_params"]["column_merge"] != "select":
                    # grayed out if ID selection is not set to Select Specific IDs
                    return []
            if "selected_column_ids" in json.loads(self.params)["merge_params"]:
                values = json.loads(self.params)["merge_params"]["selected_column_ids"]
                outvalue = []
                for v in shlex.split(values):
                    outvalue.append(int(v.replace(",", "")))
                return outvalue
            else:
                return []

    def set_ids(self, value=None):
        if value is None:
            value = []
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        if d["merge_params"]["column_merge"] != "select":
            # grayed out if ID selection is not set to Select Specific IDs
            if d["merge_params"]["merge_type"] == "row":
                raise ValueError(
                    "Error: can not set column IDs if the Column ID selection is not set to specific IDs"
                )
            if d["merge_params"]["merge_type"] == "column":
                raise ValueError(
                    "Error: can not set row IDs if the Row ID selection is not set to specific IDs"
                )
        if type(value) is not list:
            raise ValueError("Error: input should be a list")
        if len([x for x in value if type(x) == int]) != len(value):
            raise ValueError("Error: input should be a list of integers only")
        d["merge_params"]["selected_column_ids"] = ", ".join(repr(x) for x in value)
        self.params = json.dumps(d)
        return

    def add_ids(self, value=None):
        if value is None:
            value = []
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        if json.loads(self.params)["merge_params"]["column_merge"] != "select":
            # grayed out if ID selection is not set to Select Specific IDs
            if d["merge_params"]["merge_type"] == "row":
                raise ValueError(
                    "Error: can not add column IDs if the Column ID selection is not set to specific IDs"
                )
            if d["merge_params"]["merge_type"] == "column":
                raise ValueError(
                    "Error: can not add row IDs if the Row ID selection is not set to specific IDs"
                )
        if type(value) is not list:
            raise ValueError("Error: input should be a list")
        if len([x for x in value if type(x) == int]) != len(value):
            raise ValueError("Error: input should be a list of integers only")
        d["merge_params"]["selected_column_ids"] = ", ".join(
            [d["merge_params"]["selected_column_ids"], ", ".join(repr(x) for x in value)]
        )
        self.params = json.dumps(d)
        return

    def get_unknown_value(self):
        if "merge_params" in json.loads(self.params):
            if "unknown_value" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["unknown_value"]
        return "nan"

    def set_unknown_value(self, value="nan"):
        if type(value) != str:
            raise ValueError("Error: the unknown value should be a string")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["unknown_value"] = value
        self.params = json.dumps(d)
        return

    def get_table_transpose(self):
        if "merge_params" in json.loads(self.params):
            if "transpose_output" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["transpose_output"]
        return 0

    def set_table_transpose(self, value=0):
        if type(value) != int:
            raise ValueError("Error: the transpose input should be integer")
        if value not in [0, 1]:
            raise ValueError("Error: input value should be 0 or 1")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["transpose_output"] = value
        self.params = json.dumps(d)
        return

    def get_numeric_output(self):
        if "merge_params" in json.loads(self.params):
            if "force_numeric" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["force_numeric"]
        return 0

    def set_numeric_output(self, value=0):
        if type(value) != int:
            raise ValueError("Error: the numeric output should be integer")
        if value not in [0, 1]:
            raise ValueError("Error: input value should be 0 or 1")
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        d["merge_params"]["force_numeric"] = value
        self.params = json.dumps(d)
        return


class tablereduceREST(GeneratorREST):
    """Representation of Table Reduce Generator Template."""

    def __init__(self):
        super().__init__()

    def get_reduce_param(self):
        if "reduce_params" in json.loads(self.params):
            if "reduce_type" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["reduce_type"]
        return "row"

    def set_reduce_param(self, value="row"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        if value not in ["row", "column"]:
            raise ValueError("Error: input should be either row or column")
        d = json.loads(self.params)
        if "reduce_params" not in d:
            d["reduce_params"] = {}
        d["reduce_params"]["reduce_type"] = value
        self.params = json.dumps(d)
        return

    def get_table_name(self):
        if "reduce_params" in json.loads(self.params):
            if "table_name" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["table_name"]
        return ""

    def set_table_name(self, value="output_table"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        if "reduce_params" not in d:
            d["reduce_params"] = {}
        d["reduce_params"]["table_name"] = value
        self.params = json.dumps(d)
        return

    def get_operations(self):
        if "reduce_params" in json.loads(self.params):
            if "operations" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["operations"]
        return []

    def delete_operation(self, name=None):
        if name is None:
            name = []
        if type(name) != list:
            raise ValueError(
                "Error: need to pass the operation with the source row/column name as a list of strings"
            )
        if len([x for x in name if type(x) == str]) != len(name):
            raise ValueError("Error: the elements of the input list should all be strings")
        d = json.loads(self.params)
        if "reduce_params" not in d:
            return
        if "operations" not in d:
            return
        sources = d["reduce_params"]["operations"]
        valid = 0
        for _, s in enumerate(sources):
            compare = []
            for iname in shlex.split(s["source_rows"]):
                compare.append(iname.replace(",", ""))
            if compare == name:
                valid = 1
                break
        if valid == 0:
            raise ValueError("Error: no existing source with the passed input")
        del sources[i]
        d["reduce_params"]["operations"] = sources
        self.params = json.dumps(d)
        return

    def add_operation(
        self,
        name=None,
        unique=False,
        output_name="output row",
        existing=True,
        select_names="*",
        operation="count",
    ):
        if name is None:
            name = ["*"]
        d = json.loads(self.params)
        if type(name) != list:
            raise ValueError("Error: row/column name should be a list of strings")
        if len([x for x in name if type(x) == str]) != len(name):
            raise ValueError("Error: the elements of the input list should all be strings")
        if type(unique) is not bool:
            raise ValueError("Error: unique input should be True/False")
        if type(output_name) is not str:
            raise ValueError("Error: output_name should be a string")
        if type(existing) is not bool:
            raise ValueError("Error: existing should be True/False")
        if type(select_names) is not str:
            raise ValueError("Error: select_names should be a string")
        if type(operation) is not str:
            raise ValueError("Error: operation should be a string")
        if operation not in [
            "min",
            "max",
            "count",
            "sum",
            "diff",
            "mean",
            "stdev",
            "skew",
            "kurtosis",
        ]:
            raise ValueError("Error operation not among the acceptable values")
        if "reduce_params" not in d:
            d["reduce_params"] = {}
        if "operations" not in d["reduce_params"]:
            sources = []
        else:
            sources = d["reduce_params"]["operations"]
        new_source = {}
        new_source["source_rows"] = ", ".join(repr(x) for x in name)
        new_source["output_rows_from_values"] = unique
        new_source["output_rows"] = output_name
        new_source["output_columns_from_values"] = not existing
        if existing:
            new_source["output_columns_select"] = select_names
            new_source["output_columns"] = ""
        else:
            new_source["output_columns_select"] = ""
            new_source["output_columns"] = select_names
        new_source["operation"] = operation
        sources.append(new_source)
        d["reduce_params"]["operations"] = sources
        self.params = json.dumps(d)
        return

    def get_table_transpose(self):
        if "reduce_params" in json.loads(self.params):
            if "transpose_output" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["transpose_output"]
        return 0

    def set_table_transpose(self, value=0):
        if type(value) != int:
            raise ValueError("Error: the transpose input should be integer")
        if value not in [0, 1]:
            raise ValueError("Error: input value should be 0 or 1")
        d = json.loads(self.params)
        if "reduce_params" not in d:
            d["reduce_params"] = {}
        d["reduce_params"]["transpose_output"] = value
        self.params = json.dumps(d)
        return

    def get_numeric_output(self):
        if "reduce_params" in json.loads(self.params):
            if "force_numeric" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["force_numeric"]
        return 0

    def set_numeric_output(self, value=0):
        if type(value) != int:
            raise ValueError("Error: the numeric output should be integer")
        if value not in [0, 1]:
            raise ValueError("Error: input value should be 0 or 1")
        d = json.loads(self.params)
        if "reduce_params" not in d:
            d["reduce_params"] = {}
        d["reduce_params"]["force_numeric"] = value
        self.params = json.dumps(d)
        return


class tablerowcolumnfilterREST(GeneratorREST):
    """Representation of Table Row/Column Filter Generator Template."""

    def __init__(self):
        super().__init__()

    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return ""

    def set_table_name(self, value="output_table"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        d["table_name"] = value
        self.params = json.dumps(d)
        return

    def get_filter_rows(self):
        if "select_rows" in json.loads(self.params):
            out = []
            for i in shlex.split(json.loads(self.params)["select_rows"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]

    def set_filter_rows(self, value=None):
        if value is None:
            value = ["*"]
        if type(value) != list:
            raise ValueError("Error: input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements in the input list should be strings")
        d = json.loads(self.params)
        d["select_rows"] = ", ".join(repr(x) for x in value)
        self.params = json.dumps(d)
        return

    def add_filter_rows(self, value=None):
        if value is None:
            value = ["*"]
        if type(value) != list:
            raise ValueError("Error: input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements in the input list should be strings")
        d = json.loads(self.params)
        d["select_rows"] = ", ".join([d["select_rows"], ", ".join(repr(x) for x in value)])
        self.params = json.dumps(d)
        return

    def get_filter_columns(self):
        if "select_columns" in json.loads(self.params):
            out = []
            for i in shlex.split(json.loads(self.params)["select_columns"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]

    def set_filter_columns(self, value=None):
        if value is None:
            value = ["*"]
        if type(value) != list:
            raise ValueError("Error: input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements in the input list should be strings")
        d = json.loads(self.params)
        d["select_columns"] = ", ".join(repr(x) for x in value)
        self.params = json.dumps(d)
        return

    def add_filter_columns(self, value=None):
        if value is None:
            value = ["*"]
        if type(value) != list:
            raise ValueError("Error: input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements in the input list should be strings")
        d = json.loads(self.params)
        d["select_columns"] = ", ".join([d["select_columns"], ", ".join(repr(x) for x in value)])
        self.params = json.dumps(d)
        return

    def get_invert(self):
        if "invert" in json.loads(self.params):
            return json.loads(self.params)["invert"]
        else:
            return 0

    def set_invert(self, value=False):
        if type(value) != int and type(value) != bool:
            raise ValueError("Error: the invert input should be integer or True/False")
        if (type(value) == int) and (value not in [0, 1]):
            raise ValueError("Error: integer input value should be 0 or 1")
        d = json.loads(self.params)
        d["invert"] = value
        self.params = json.dumps(d)
        return

    def get_sort(self):
        if "reorder" in json.loads(self.params):
            return json.loads(self.params)["reorder"]
        else:
            return 0

    def set_sort(self, value=False):
        if type(value) != int and type(value) != bool:
            raise ValueError("Error: the sort input should be integer or True/False")
        if (type(value) == int) and (value not in [0, 1]):
            raise ValueError("Error: integer input value should be 0 or 1")
        d = json.loads(self.params)
        if d["invert"] is True:
            raise ValueError("Error: sort can not be set if the invert toggle is ON")
        d["reorder"] = value
        self.params = json.dumps(d)
        return

    def get_table_transpose(self):
        if "transpose" in json.loads(self.params):
            return json.loads(self.params)["transpose"]
        else:
            return 0

    def set_table_transpose(self, value=False):
        if type(value) != int and type(value) != bool:
            raise ValueError("Error: the transpose input should be integer or True/False")
        if (type(value) == int) and (value not in [0, 1]):
            raise ValueError("Error: integer input value should be 0 or 1")
        d = json.loads(self.params)
        d["transpose"] = value
        self.params = json.dumps(d)
        return


class tablevaluefilterREST(GeneratorREST):
    """Representation of Table Value Filter Generator Template."""

    def __init__(self):
        super().__init__()

    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return ""

    def set_table_name(self, value="value filtered table"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        d["table_name"] = value
        self.params = json.dumps(d)
        return

    def get_filter_by(self):
        out = []
        if "row_column" in json.loads(self.params):
            out.append(json.loads(self.params)["row_column"])
        else:
            out.append("column")
        if "column_name" in json.loads(self.params):
            out.append(json.loads(self.params)["column_name"])
        else:
            out.append("0")
        return out

    def set_filter_by(self, value=None):
        if value is None:
            value = ["column", "0"]
        if type(value) is not list:
            raise ValueError("Error: input should be a list")
        if len(value) != 2:
            raise ValueError("Error: input list should contain 2 values")
        if value[0] not in ["row", "column"]:
            raise ValueError("Error: the first input should be row / column")
        if type(value[1]) is not str:
            raise ValueError("Error: the second input should be a str")
        d = json.loads(self.params)
        d["row_column"] = value[0]
        d["column_name"] = value[1]
        self.params = json.dumps(d)
        return

    def get_filter(self):
        if "filter" in json.loads(self.params):
            if json.loads(self.params)["filter"] == "range":
                if "range_min" in json.loads(self.params):
                    return [
                        "range",
                        json.loads(self.params)["range_min"],
                        json.loads(self.params)["range_max"],
                    ]
                else:
                    return ["range", "", ""]
            elif json.loads(self.params)["filter"] == "specific":
                if "specific_values" in json.loads(self.params):
                    values = []
                    for i in shlex.split(json.loads(self.params)["specific_values"]):
                        values.append(i.replace(",", ""))
                    return ["specific", values]
                else:
                    return ["specific", ["*"]]
            elif json.loads(self.params)["filter"] == "top_percent":
                if "percent" in json.loads(self.params):
                    return ["top_percent", float(json.loads(self.params)["percent"])]
                else:
                    return ["top_percent", 10.0]
            elif json.loads(self.params)["filter"] == "top_count":
                if "count" in json.loads(self.params):
                    return ["top_count", int(json.loads(self.params)["count"])]
                else:
                    return ["top_count", 10]
            elif json.loads(self.params)["filter"] == "bot_percent":
                if "percent" in json.loads(self.params):
                    return ["bot_percent", float(json.loads(self.params)["percent"])]
                else:
                    return ["bot_percent", 10.0]
            elif json.loads(self.params)["filter"] == "bot_count":
                if "count" in json.loads(self.params):
                    return ["bot_count", int(json.loads(self.params)["count"])]
                else:
                    return ["bot_count", 10]

    def set_filter(self, value=None):
        if value is None:
            value = ["range", "", ""]
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        if len(value) < 2:
            raise ValueError("Error: the list input is too short")
        d = json.loads(self.params)
        if value[0] == "range":
            d["filter"] = "range"
            if len(value) != 3:
                raise ValueError("Error: the input should contain 3 elements")
            if len(value) != len([x for x in value if type(x) == str]):
                raise ValueError("Error: all input elements should be strings")
            d["range_min"] = value[1]
            d["range_max"] = value[2]
        elif value[0] == "specific":
            d["filter"] = "specific"
            if len(value) != 2:
                raise ValueError("Error: the input should contain 2 elements")
            if type(value[1]) is not list:
                raise ValueError("Error: the second input should be a list")
            if len(value[1]) != len([x for x in value[1] if type(x) == str]):
                raise ValueError("Error: the specific value(s) should be string")
            d["specific_values"] = ", ".join(repr(x) for x in value[1])
        elif value[0] == "top_percent":
            d["filter"] = "top_percent"
            if len(value) != 2:
                raise ValueError("Error: the input should contain 2 elements")
            if not (type(value[1]) is float or type(value[1]) is int):
                raise ValueError("Error: the second input should be a float")
            if value[1] < 0.0 or value[1] > 100.0:
                raise ValueError("Error: the percentage should be in the (0,100) range")
            d["percent"] = str(value[1])
        elif value[0] == "top_count":
            d["filter"] = "top_count"
            if len(value) != 2:
                raise ValueError("Error: the input should contain 2 elements")
            if type(value[1]) is not int:
                raise ValueError("Error: the second input should be an int")
            d["count"] = str(value[1])
        elif value[0] == "bot_percent":
            d["filter"] = "bot_percent"
            if len(value) != 2:
                raise ValueError("Error: the input should contain 2 elements")
            if not (type(value[1]) is float or type(value[1]) is int):
                raise ValueError("Error: the second input should be a float")
            if value[1] < 0.0 or value[1] > 100.0:
                raise ValueError("Error: the percentage should be in the (0,100) range")
            d["percent"] = str(value[1])
        elif value[0] == "bot_count":
            d["filter"] = "bot_count"
            if len(value) != 2:
                raise ValueError("Error: the input should contain 2 elements")
            if type(value[1]) is not int:
                raise ValueError("Error: the second input should be an int")
            d["count"] = str(value[1])
        else:
            raise ValueError("Error: the first input is not among the acceptable values")
        self.params = json.dumps(d)
        return

    def get_invert_filter(self):
        if "invert" in json.loads(self.params):
            return json.loads(self.params)["invert"]
        else:
            return 0

    def set_invert_filter(self, value=False):
        if type(value) != int and type(value) != bool:
            raise ValueError("Error: the invert input should be integer or True/False")
        if (type(value) == int) and (value not in [0, 1]):
            raise ValueError("Error: integer input value should be 0 or 1")
        d = json.loads(self.params)
        d["invert"] = value
        self.params = json.dumps(d)
        return

    def get_values_as_dates(self):
        if "values_as_dates" in json.loads(self.params):
            return json.loads(self.params)["values_as_dates"]
        else:
            return 0

    def set_values_as_dates(self, value=False):
        if type(value) != int and type(value) != bool:
            raise ValueError("Error: the values as dates input should be integer or True/False")
        if (type(value) == int) and (value not in [0, 1]):
            raise ValueError("Error: integer input value should be 0 or 1")
        d = json.loads(self.params)
        d["values_as_dates"] = value
        self.params = json.dumps(d)
        return


class tablesortfilterREST(GeneratorREST):
    """Representation of Table Row/Column Sort Filter Generator Template."""

    def __init__(self):
        super().__init__()

    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return "sorted table"

    def set_table_name(self, value="sorted table"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        d["table_name"] = value
        self.params = json.dumps(d)
        return

    def get_sort_rows(self):
        if "sort_rows" in json.loads(self.params):
            return json.loads(self.params)["sort_rows"]
        else:
            return []

    def set_sort_rows(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements should be string")
        for i in value:
            if i[0] not in ["+", "-"]:
                raise ValueError("Error: the first character should be + or -")
        d = json.loads(self.params)
        d["sort_rows"] = value
        self.params = json.dumps(d)
        return

    def add_sort_rows(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements should be string")
        for i in value:
            if i[0] not in ["+", "-"]:
                raise ValueError("Error: the first character should be + or -")
        d = json.loads(self.params)
        d["sort_rows"] = d["sort_rows"] + value
        self.params = json.dumps(d)
        return

    def get_sort_columns(self):
        if "sort_columns" in json.loads(self.params):
            return json.loads(self.params)["sort_columns"]
        else:
            return []

    def set_sort_columns(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements should be string")
        for i in value:
            if i[0] not in ["+", "-"]:
                raise ValueError("Error: the first character should be + or -")
        d = json.loads(self.params)
        d["sort_columns"] = value
        self.params = json.dumps(d)
        return

    def add_sort_columns(self, value=None):
        if value is None:
            value = []
        if type(value) is not list:
            raise ValueError("Error: the input should be a list")
        if len(value) != len([x for x in value if type(x) == str]):
            raise ValueError("Error: all the elements should be string")
        for i in value:
            if i[0] not in ["+", "-"]:
                raise ValueError("Error: the first character should be + or -")
        d = json.loads(self.params)
        d["sort_columns"] = d["sort_columns"] + value
        self.params = json.dumps(d)
        return


class treemergeREST(GeneratorREST):
    """Representation of Tree Merge Generator Template."""

    def __init__(self):
        super().__init__()

    def get_merge_rule(self):
        return json.loads(self.params).get("rows", "all")

    def set_merge_rule(self, value="all"):
        if value not in ["all", "common", "first"]:
            raise ValueError("Error: legal match rules are: 'all', 'common', 'first' ")
        d = json.loads(self.params)
        d["rows"] = value
        self.params = json.dumps(d)

    def get_match_rule(self):
        return json.loads(self.params).get("matchby", "both")

    def set_match_rule(self, value="both"):
        if value not in ["key", "name", "both"]:
            raise ValueError("Error: legal match rules are: 'key', 'name', 'both' ")
        d = json.loads(self.params)
        d["matchby"] = value
        self.params = json.dumps(d)

    def get_tree_name(self):
        return json.loads(self.params).get("mergedname", "treemerge")

    def set_tree_name(self, value="treemerge"):
        if type(value) is not str:
            raise ValueError("Error: the input should be a string")
        d = json.loads(self.params)
        d["mergedname"] = value
        self.params = json.dumps(d)

    def get_fill_value(self):
        return json.loads(self.params).get("fillvalue", "")

    def set_fill_value(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: the input should be a string")
        d = json.loads(self.params)
        d["fillvalue"] = value
        self.params = json.dumps(d)

    def get_header_tag(self):
        return json.loads(self.params).get("headertag", "")

    def set_header_tag(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: the input should be a string")
        d = json.loads(self.params)
        d["headertag"] = value
        self.params = json.dumps(d)


class sqlqueriesREST(GeneratorREST):
    """Representation of SQL Query Generator Template."""

    def __init__(self):
        super().__init__()

    def get_db_type(self):
        if "typedb" in json.loads(self.params):
            return json.loads(self.params)["typedb"]
        else:
            return "SQLite"

    def set_db_type(self, value="SQLite"):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        if value not in ["SQLite", "PostgreSQL"]:
            raise ValueError("Error: input should be SQLite or PostgreSQL")
        d = json.loads(self.params)
        d["typedb"] = value
        self.params = json.dumps(d)
        return

    def get_sqlite_name(self):
        if "sqldb" in json.loads(self.params):
            return json.loads(self.params)["sqldb"]
        else:
            return ""

    def set_sqlite_name(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        if d["typedb"] == "PostgreSQL":
            raise ValueError(
                "Error: can not set SQLite database while the database type is PostgreSQL"
            )
        d["sqldb"] = value
        self.params = json.dumps(d)
        return

    def get_postgre(self):
        out = {}
        if "sqldb" in json.loads(self.params):
            if "sqldb" in json.loads(self.params):
                out["database"] = json.loads(self.params)["sqldb"]
            else:
                out["database"] = ""
            if "hostsqldb" in json.loads(self.params):
                out["hostname"] = json.loads(self.params)["hostsqldb"]
            else:
                out["hostname"] = ""
            if "portsqldb" in json.loads(self.params):
                out["port"] = str(json.loads(self.params)["portsqldb"])
            else:
                out["port"] = ""
            if "usrsqldb" in json.loads(self.params):
                out["username"] = json.loads(self.params)["usrsqldb"]
            else:
                out["username"]
            if "pswsqldb" in json.loads(self.params):
                out["password"] = json.loads(self.params)["pswsqldb"]
            else:
                out["password"] = ""
        else:
            out = {"database": "", "hostname": "", "port": "", "username": "", "password": ""}
        return out

    def set_postgre(self, value: dict = None):
        if value is None:
            value = {
                "database": "",
                "hostname": "localhost",
                "port": "5432",
                "username": "nexus",
                "password": "cei",
            }
        if type(value) is not dict:
            raise ValueError("Error: input should be a dictionary")
        d = json.loads(self.params)
        if d["typedb"] == "SQLite":
            raise ValueError(
                "Error: can not set PostgreSQL database while the database type is SQLite"
            )
        if "database" in value:
            d["sqldb"] = value["database"]
        else:
            d["sqldb"] = ""
        if "hostname" in value:
            d["hostsqldb"] = value["hostname"]
        else:
            d["hostsqldb"] = "localhost"
        if "port" in value:
            d["portsqldb"] = str(value["port"])
        else:
            d["portsqldb"] = "5342"
        if "username" in value:
            d["usrsqldb"] = value["username"]
        else:
            d["usrsqldb"] = "nexus"
        if "password" in value:
            d["pswsqldb"] = value["password"]
        else:
            d["pswsqldb"] = "cei"
        self.params = json.dumps(d)
        return

    def get_query(self):
        if "sqlquery" in json.loads(self.params):
            return json.loads(self.params)["sqlquery"]
        else:
            return ""

    def set_query(self, value=""):
        if type(value) is not str:
            raise ValueError("Error: input should be a string")
        d = json.loads(self.params)
        d["sqlquery"] = value
        self.params = json.dumps(d)
        return

    def validate(self):
        """
        Validate connection to database.

        Parameters
        ----------
        None

        Returns
        -------
        bool
            True: can connect to the database. False: can not connect to the database
        str
            out_msg: error or warning message, in case of failure.
                     Empty string in case of success
        """
        valid = True
        p = json.loads(self.params)
        out_msg = ""
        if "SQLite" == p.get("typedb", "SQLite"):
            filename = p.get("sqldb", "")
            if not report_utils.isSQLite3(filename):
                valid = False
                out_msg = "SQLite file is not a valid database"
        else:
            try:
                import psycopg

                attrs = dict(
                    sqldb="dbname",
                    hostsqldb="host",
                    portsqldb="port",
                    usrsqldb="user",
                    pswsqldb="password",
                )
                conn_string = ""
                for key in attrs:
                    tmp = str(p.get(key, ""))
                    if len(tmp):
                        conn_string += f"{attrs[key]}={tmp} "
                _ = psycopg.connect(conn_string.strip())
            except Exception as e:
                valid = False
                out_msg = f"Could not validate connection:\n{e}"
        return valid, out_msg


class pptxREST(LayoutREST):
    """Representation of PPTX Layout Template."""

    @property
    def input_pptx(self):
        return self.get_property().get("input_pptx")

    @input_pptx.setter
    def input_pptx(self, value):
        props = self.get_property()
        props["input_pptx"] = value
        self.set_property(props)

    @property
    def use_all_slides(self):
        return self.get_property().get("use_all_slides")

    @use_all_slides.setter
    def use_all_slides(self, value):
        props = self.get_property()
        props["use_all_slides"] = value
        self.set_property(props)

    @property
    def output_pptx(self):
        return self.get_property().get("output_pptx")

    @output_pptx.setter
    def output_pptx(self, value):
        props = self.get_property()
        props["output_pptx"] = value
        self.set_property(props)


class pptxslideREST(LayoutREST):
    """Representation of PPTX Slide Layout Template."""

    @property
    def source_slide(self):
        return self.get_property().get("source_slide")

    @source_slide.setter
    def source_slide(self, value):
        props = self.get_property()
        props["source_slide"] = value
        self.set_property(props)


class datafilterREST(LayoutREST):
    """Representation of Data Filter Layout Template."""

    @property
    def filter_types(self):
        return self.get_property().get("filter_types")

    @filter_types.setter
    def filter_types(self, value):
        props = self.get_property()
        props["filter_types"] = value
        self.set_property(props)

    @property
    def filter_checkbox(self):
        return self.get_property().get("filter_checkbox")

    @filter_checkbox.setter
    def filter_checkbox(self, value):
        props = self.get_property()
        props["filter_checkbox"] = value
        self.set_property(props)

    @property
    def filter_slider(self):
        return self.get_property().get("filter_slider")

    @filter_slider.setter
    def filter_slider(self, value):
        props = self.get_property()
        props["filter_slider"] = value
        self.set_property(props)

    @property
    def filter_input(self):
        return self.get_property().get("filter_input")

    @filter_input.setter
    def filter_input(self, value):
        props = self.get_property()
        props["filter_input"] = value
        self.set_property(props)

    @property
    def filter_dropdown(self):
        return self.get_property().get("filter_dropdown")

    @filter_dropdown.setter
    def filter_dropdown(self, value):
        props = self.get_property()
        props["filter_dropdown"] = value
        self.set_property(props)

    @property
    def filter_single_dropdown(self):
        return self.get_property().get("filter_single_dropdown")

    @filter_single_dropdown.setter
    def filter_single_dropdown(self, value):
        props = self.get_property()
        props["filter_single_dropdown"] = value
        self.set_property(props)

    @property
    def filter_numeric_step(self):
        return self.get_property().get("filter_numeric_step")

    @filter_numeric_step.setter
    def filter_numeric_step(self, value):
        props = self.get_property()
        props["filter_numeric_step"] = value
        self.set_property(props)
