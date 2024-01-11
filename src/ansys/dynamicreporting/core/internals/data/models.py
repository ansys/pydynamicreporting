#
# *************************************************************
#  Copyright 2021-2024 ANSYS, Inc.
#  All Rights Reserved.
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
# Create your models here.
# Notes:
# 1) datetime.now(pytz.utc) to get a proper date w/timezone
# 2) we define get_absolute_url methods, but in a template, the following also works (for an item):
# {% url 'data_session_detail' item.session.guid %} instead of
# {{ item.session.get_absolute_url }}
#
import sys

import copy
import datetime
import json
import os
import os.path
import shlex
import uuid

import numpy
from ..report_framework.acls import check_obj_perm
from ..report_framework.base_model_managers import NexusQuerySet
from ..report_framework.utils import get_render_error_html
from ..data.geofile_rendering import render_scene, render_file
from ..data.managers import SessionManager, DatasetManager, ItemManager, ItemCategoryManager
from dateutil import parser
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models.query import Q, QuerySet
from django.template import engines
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from guardian.models import UserObjectPermissionBase, GroupObjectPermissionBase
from ..reports.engine import TemplateEngine
from ..reports.models import Template
from ..reports.template_generators import is_simple_number

from .acls import generate_media_auth_hash
from .conditional_format import ConditionalFormattingHTMLStyle, TreeConditionalFormattingHTMLStyle
from .extremely_ugly_hacks import safe_unpickle
from .templatetags.data_tags import (
    convert_datelist_to_plotly_datelist,
    expand_string_context,
    convert_macro_slashes,
    split_quoted_string_list,
    format_plotly,
    format_value_general
)
from .themes import PLOTLY_THEMES
from .utils import get_aware_datetime, decode_table_data, get_nexus_version, get_unique_id


class Session(models.Model):
    guid = models.UUIDField(verbose_name="uid", primary_key=True, default=uuid.uuid1)
    # core session information
    tags = models.TextField(verbose_name="userdata", blank=True, db_index=True)
    date = models.DateTimeField(verbose_name="timestamp", db_index=True, default=timezone.now)
    hostname = models.CharField(verbose_name="host machine name", max_length=50, blank=True, db_index=True)
    platform = models.CharField(verbose_name="system architecture", max_length=50, blank=True, db_index=True)
    application = models.CharField(verbose_name="capture application", max_length=40, blank=True, db_index=True)
    version = models.CharField(verbose_name="application version", max_length=20, blank=True, db_index=True,
                               default=get_nexus_version)

    objects = models.Manager()  # The default manager.
    filtered_objects = SessionManager()

    def get_absolute_url(self):
        return reverse('data_session_detail', kwargs={'guid': self.guid})

    def __str__(self):
        return "{} ({}:{})".format(self.application, self.version, str(self.guid))

    @classmethod
    def find(cls, request, reverse=0, sort_tag="date"):
        # start a query
        queryset = Session.objects.all()
        # special case of an explicit GUID
        s_guid = request.GET.get('s_guid', None)
        if s_guid is not None:
            kwargs = {'guid__exact': s_guid}
            queryset = queryset.filter(**kwargs)
        else:
            queryset = object_filter(request.GET.get('query', ''), queryset, model=Session)

        # pick the sort (we can only sort QuerySets for now)
        if isinstance(queryset, QuerySet):
            if reverse:
                sort_tag = "-" + sort_tag
            return queryset.order_by(sort_tag)

        return queryset


class Dataset(models.Model):
    guid = models.UUIDField(verbose_name="uid", primary_key=True, default=uuid.uuid1)
    # core dataset information
    tags = models.TextField(verbose_name="userdata", blank=True, db_index=True)
    filename = models.CharField(verbose_name="dataset filename", max_length=256, blank=True, db_index=True)
    dirname = models.CharField(verbose_name="dataset directory name", max_length=256, blank=True, db_index=True)
    format = models.CharField(verbose_name="dataset format", max_length=50, blank=True, db_index=True)
    numparts = models.IntegerField(verbose_name="number of parts", default=0)
    numelements = models.IntegerField(verbose_name="number of elements", default=0)

    objects = models.Manager()  # The default manager.
    filtered_objects = DatasetManager()

    def get_absolute_url(self):
        return reverse('data_dataset_detail', kwargs={'guid': self.guid})

    def __str__(self):
        return "{} ({}:{})".format(self.filename, self.format, str(self.guid))

    @classmethod
    def find(cls, request, reverse=0, sort_tag="format"):
        # start a query
        queryset = Dataset.objects.all()
        # special case of an explicit GUID
        d_guid = request.GET.get('d_guid', None)
        if d_guid is not None:
            kwargs = {'guid__exact': d_guid}
            queryset = queryset.filter(**kwargs)
        else:
            queryset = object_filter(request.GET.get('query', ''), queryset, model=Dataset)

        # pick the sort (we can only sort QuerySets for now)
        if isinstance(queryset, QuerySet):
            if reverse:
                sort_tag = "-" + sort_tag
            return queryset.order_by(sort_tag)

        return queryset


# xaxis_obj = XAxisObj(ctx, data, rowlbls, collbls, item)
# xrows = xaxis_obj.x_row_indices()
# yrows = xaxis_obj.y_row_indices()
# xdata = xaxis_obj.data(y_row_index)
# xaxistitle = xaxis_obj.title()
# xaxis can be a single value or an array of values. The values can be a row index or a row label name
class XAxisObj:
    def __init__(self, context, data, row_labels, column_labels, item):
        self._column_labels = column_labels
        self._row_labels = row_labels
        self._context = context
        self._data = data
        self._xrows = list()
        self._yrows = list()
        self._row_map = dict()
        self._item = item
        # how many X axis rows are there?
        num_x_rows = item.get_indexed_count(self._data, self._context, 'xaxis')
        # collect a list of the X rows
        for i in range(num_x_rows):
            row_name = item.get_indexed_default(self._data, self._context, i, 'xaxis', default='0')
            x_row_index = self.find_row_index(row_name)
            if x_row_index is not None:
                self._xrows.append(x_row_index)
        # how many Y axis rows are there?
        num_y_rows = item.get_indexed_count(self._data, self._context, 'yaxis')
        # build a potential list of Y rows (anything in 'yaxis' or not in 'xaxis')
        if num_y_rows == 0:
            # walk all rows and if not marked as an 'X' row, map it to the corresponding x row
            for i in range(len(self._row_labels)):
                if i not in self._xrows:
                    row_name = item.get_indexed_default(self._data, self._context, i, 'xaxis', default='0')
                    x_row_index = self.find_row_index(row_name)
                    if x_row_index is not None:
                        self._row_map[i] = x_row_index
                        self._yrows.append(i)
        else:
            # we have lists of both X and Y rows, the indexing should match, just query both
            for i in range(num_y_rows):
                row_name = item.get_indexed_default(self._data, self._context, i, 'yaxis', default='0')
                y_row_index = self.find_row_index(row_name)
                row_name = item.get_indexed_default(self._data, self._context, i, 'xaxis', default='0')
                x_row_index = self.find_row_index(row_name)
                # create the Y row index to X row index map...
                if (x_row_index is not None) and (y_row_index is not None):
                    self._row_map[y_row_index] = x_row_index
                    self._yrows.append(y_row_index)
        # the xaxis title will be the first xrow row_label or the data xtitle key
        if len(self._xrows) > 0:
            self._title = context.get('xtitle', self._row_labels[self._xrows[0]])
        else:
            self._title = context.get('xtitle', self._data.get('xtitle', None))

    def find_row_index(self, name):
        # special case, if name is an index, just return it...
        name = str(name)
        if name.startswith('@'):
            name = name[1:]
        if is_simple_number(name):
            i = int(name)
            if i < 0:
                return None
            if i >= len(self._row_labels):
                return None
            return i
        for i in range(len(self._row_labels)):
            if self._row_labels[i] == name:
                return i
        return None

    # these two methods are used to figure out if a given name is the name of a row
    # if it is, we can get the actual data for the row
    # The rules:  '0' - the number 0, not a row index
    #             '@0' - the row index 0
    #             '@foo' - the row named 'foo'
    def get_row_reference(self, name):
        tmp = str(name)
        if tmp[0] != '@':
            return None
        row = self.find_row_index(tmp[1:])
        if row is None:
            return None
        return self._data['array'][row]

    def is_row_reference(self, name):
        tmp = str(name)
        if tmp[0] != '@':
            return False
        if self.find_row_index(tmp[1:]) is None:
            return False
        return True

    def x_row_indices(self):
        return self._xrows

    def y_row_indices(self):
        return self._yrows

    def data(self, y_row_index):
        # if no x rows specified, use the column labels (forced unique)
        if len(self._xrows) == 0:
            tmp = list()
            for idx in range(len(self._column_labels)):
                label_format = self._item.get_indexed_default(self._data, self._context, idx,
                                                              'format_column', default='str')
                lbl, dummy = format_value_general(str(self._column_labels[idx]).strip(), label_format)
                # make the values unique
                if lbl in tmp:
                    i = 0
                    v = "{} ->> {:04d}".format(lbl, i)
                    while v in tmp:
                        i += 1
                        v = "{} ->> {:04d}".format(lbl, i)
                    lbl = v
                tmp.append(lbl)
            return tmp
        return self._data['array'][self._row_map.get(y_row_index, 0)]

    def title(self):
        return self._title


class ItemCategory(models.Model):
    guid = models.UUIDField(verbose_name="uid", primary_key=True, default=uuid.uuid1)
    name = models.CharField(verbose_name="item category name", max_length=255, unique=True)
    date = models.DateTimeField(verbose_name="timestamp", default=timezone.now, db_index=True)

    objects = models.Manager()  # The default manager.
    filtered_objects = ItemCategoryManager()

    class Meta:
        permissions = [
            ('own_itemcategory', 'Owns the item category'),
        ]

    def __str__(self):
        return f"{self.name} ({self.name}:{self.guid})"

    @classmethod
    def find(cls, request, reverse=0, sort_tag="date", perm=None):
        # start a query
        queryset = ItemCategory.filtered_objects.with_perms(request, perm=perm)

        # guid or list of guids
        ic_guid = request.GET.get('ic_guid', None)
        if ic_guid is not None:
            ic_guid_list = ic_guid.split(",")
            kwargs = {'guid__in': ic_guid_list}
            queryset = queryset.filter(**kwargs)
        else:
            queryset = object_filter(request.GET.get('query', ''), queryset, model=ItemCategory)

        # pick the sort (we can only sort QuerySets for now)
        if isinstance(queryset, QuerySet):
            if reverse:
                sort_tag = "-" + sort_tag
            return queryset.order_by(sort_tag)

        return queryset


class Item(models.Model):
    guid = models.UUIDField(verbose_name="uid", primary_key=True, default=uuid.uuid1)
    # links to the sessions and dataset for this item
    session = models.ForeignKey(Session, verbose_name="item session", on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, verbose_name="item dataset", on_delete=models.CASCADE)
    # core item information
    tags = models.TextField(verbose_name="userdata", blank=True, db_index=True)
    sequence = models.IntegerField(verbose_name="index number for a set of items", default=0, db_index=True)
    date = models.DateTimeField(verbose_name="timestamp", db_index=True, default=timezone.now)
    source = models.CharField(verbose_name="name of the source", max_length=80, blank=True, db_index=True)
    name = models.CharField(verbose_name="item name", max_length=255, blank=True, db_index=True)
    width = models.IntegerField(verbose_name="width", default=0)
    height = models.IntegerField(verbose_name="height", default=0)
    type = models.CharField(verbose_name="item type", max_length=16, default="none", db_index=True)
    payloaddata = models.TextField(verbose_name="raw payload data", blank=True)  # this is a Python cPickle string
    payloadfile = models.FileField(verbose_name="uploaded payload data file")
    categories = models.ManyToManyField(
        ItemCategory,
        verbose_name="item category list",
        through='ItemCategoryRelation',
        through_fields=('item', 'category',),
    )

    objects = models.Manager()  # The default manager.
    filtered_objects = ItemManager()

    # Type values:
    # image, anim, string, html, table, scene, file, none, tree

    # Instance ctor. Initialize local instance variables here.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tag_dict = None

    def __str__(self):
        return "{} ({}:{})".format(self.name, self.type, str(self.guid))

    # for this item, return an ID that can be used as the suffix to a
    # variable name.  Remove the '-'s in the guid and return that.
    def get_unique_id(self):
        return str(self.guid).replace("-", "")

    @classmethod
    def find(cls, request, reverse=0, sort_tag="date", perm=None, query='', queryset=None):
        # start a query
        qs = Item.filtered_objects.all()
        # if an initial queryset is provided, start with it
        if queryset is not None:
            if not isinstance(queryset, NexusQuerySet):
                raise Exception("The queryset passed is invalid")
            qs = queryset
        # filter by perms
        qs = qs.with_perms(request, perm=perm)
        # case of explicit guid(s)
        item_guids = request.GET.get('i_guid', None)
        if item_guids is not None:
            # i_guid can be a list of guids
            # separated by a comma, or just one guid
            item_guid_list = item_guids.split(",")
            kwargs = {'guid__in': item_guid_list}
            qs = qs.filter(**kwargs)
        else:
            # use manually specified query if available
            if not query:
                if 'query' in request.GET:
                    query = request.GET['query']
                else:
                    # allow reading params from other types of REST requests
                    # too, not just GET.
                    if hasattr(request, 'query_params'):
                        query = request.query_params.get('query', '')
            #  use the query expr to filter
            qs = object_filter(query, qs, model=Item)

        # pick the sort (we can only sort QuerySets for now)
        if isinstance(qs, QuerySet):
            if reverse:
                sort_tag = "-" + sort_tag
            return qs.order_by(sort_tag)

        return qs

    def is_file_payload(self):
        return self.type in ['image', 'anim', 'scene', 'file']

    # return a URL for the payload portion of the object.  Optional block sizing is allowed as well
    def get_payload_url(self, width=None, height=None, controls=None):
        url = reverse('data_item_payload', kwargs={'guid': self.guid})
        sep = "?"
        if width is not None:
            url += "{}width={}".format(sep, width)
            sep = "&"
        if height is not None:
            url += "{}height={}".format(sep, height)
            sep = "&"
        if controls is not None:
            url += "{}controls={}".format(sep, controls)
            sep = "&"
        return url

    def get_payload_file_url(self):
        if self.payloadfile:
            return self.payloadfile.url
        return ''

    def get_payload_server_pathname(self):
        if self.payloadfile:
            return self.payloadfile.path
        return settings.MEDIA_ROOT

    def get_absolute_url(self):
        return reverse('data_item_detail', kwargs={'guid': self.guid})

    @staticmethod
    def get_tag_dict_from_str(tags, prefix=None):
        if not tags:
            return {}
            # make sure cases like foo='a bar example' work (use shlex.split)
        # It is possible for the user to have invalid tags.  Consider:  foo='a bar's example'
        # This will raise an exception, and we will try replacing them to avoid blocking an item display entirely
        try:
            tag_list = shlex.split(tags)
        except ValueError:
            # we can't really fix this case, so remove the quotes and try one more time...
            try:
                tag_list = shlex.split(tags.replace('"', '_').replace("'", "_"))
            except ValueError:
                # give up
                tag_list = []
        tag_dict = {}
        for tag in tag_list:
            if '=' in tag:
                values = tag.split('=')
                name = values[0]
                if len(values) > 1:
                    str_value = values[1]
                else:
                    str_value = ""
                # Try to convert the value to a int, then float. If it doesn't
                # work, leave it as a string.
                try:
                    value = int(str_value)
                except ValueError:
                    try:
                        value = float(str_value)
                    except ValueError:
                        value = str_value
                tmp = name
                if prefix:
                    tmp = prefix + 'Z' + tmp
                tag_dict[tmp] = value
            else:
                tmp = tag
                if prefix:
                    tmp = prefix + 'Z' + tmp
                tag_dict[tmp] = True

        return tag_dict

    def add_tags_from_str_into_dictionary(self, tags, prefix=None):
        tag_dict = self.get_tag_dict_from_str(tags, prefix=prefix)
        self._tag_dict.update(tag_dict)

    def add_fields_from_obj_into_dictionary(self, obj, fields, prefix=None):
        for attr in fields:
            value = getattr(obj, attr, None)
            if value is not None:
                tmp = attr
                if prefix:
                    tmp = prefix + 'Z' + tmp

                self._tag_dict[tmp] = str(value)

    def build_tag_dictionary(self):
        # If we haven't made the dictionary before, build it.
        if self._tag_dict is None:
            from collections import defaultdict
            self._tag_dict = defaultdict(lambda: False)  # Return False if the item is not found
            self.add_tags_from_str_into_dictionary(self.tags)
            # walk the session tags
            try:
                self.add_tags_from_str_into_dictionary(self.session.tags, prefix='s')
                fields = ['date', 'hostname', 'platform', 'application', 'version']
                self.add_fields_from_obj_into_dictionary(self.session, fields, prefix='sf')
            except:
                pass
            # walk the dataset tags
            try:
                self.add_tags_from_str_into_dictionary(self.dataset.tags, prefix='d')
                fields = ['filename', 'dirname', 'format']
                self.add_fields_from_obj_into_dictionary(self.dataset, fields, prefix='df')
            except:
                pass
            fields = ['date', 'sequence', 'name', 'source']
            self.add_fields_from_obj_into_dictionary(self, fields, prefix='if')
        return self._tag_dict

    # Search the tags, given a particular context, returning a value if set,
    # True if not, and false if the tag does not exist.
    def search_tag(self, search_tag, context=None, default=None):
        # Current implementation has tags converted to a dictionary and
        # searches that.
        d = self.build_tag_dictionary()
        # Search the dictionary for the tag parameter.
        tmp = d.get(search_tag, default)
        # potentially expand the string using the context...
        if context is not None:
            tmp = expand_string_context(tmp, context).strip()
        return tmp

    @staticmethod
    def get_indexed_count(data, ctx, key, default=None):
        prop_value = ctx.get(key, data.get(key, default))
        if prop_value is not None:
            prop_value = str(prop_value).strip()
            if prop_value and ((prop_value[0] == '[') and (prop_value[-1] == ']')):
                prop_value_list = split_quoted_string_list(prop_value[1:-1], delimiter=',')
                return len(prop_value_list)
            return 1
        return 0

    def get_indexed_default(self, data, ctx, idx, key, default=None, wildcard=None):
        # look for the key in the data or context dictionaries
        # if it has the [] syntax, split it and use the value at [idx]
        # if not, return the value
        prop_value = ctx.get(key, data.get(key, default))
        if prop_value is not None:
            prop_value = str(prop_value).strip()
            if prop_value:
                if prop_value[0] == '[' and prop_value[-1] == ']':
                    prop_value_list = split_quoted_string_list(prop_value[1:-1], delimiter=',')
                    prop_value = prop_value_list[idx % len(prop_value_list)] if prop_value_list else ""
                prop_value = expand_string_context(prop_value, ctx, wildcard=wildcard)
                prop_value = expand_string_context(prop_value, self.build_tag_dictionary(), wildcard=wildcard)
                # If the new value contains spaces, it will be returned in between single quote.
                # Remove them
                prop_value = prop_value.replace("'", '')
            return prop_value.strip()
        return None

    def get_default(self, data, ctx, key, default=None, force_int=False):
        # look for the key in the data or context dictionaries
        if data is None:
            value = ctx.get(key, default)
        else:
            value = ctx.get(key, data.get(key, default))
        if value is not None:
            value = expand_string_context(str(value), ctx)
            value = expand_string_context(value, self.build_tag_dictionary())
        if force_int:
            try:
                value = int(value)
            except:
                value = default
        return value

    def format_for_javascript(self, s, latex=False):
        # returns the JS code for assigning the string
        # it will include the quotes (and perhaps the raw tag)
        if latex:
            if len(s) >= 3 and s[0] == '$' and s[-1] == '$':
                return "'" + s.replace('\\', '\\\\') + "'"
        tmp = self.clean_label(s)
        return "'" + tmp + "'"

    @staticmethod
    def convert_marker_to_plotly(s):
        if s is None:
            return s
        out = 'circle'
        tmp = s.split("-")
        if len(tmp):
            lookup = dict(none='none',
                          cricle='circle',
                          square='square',
                          cross='cross',
                          x='x',
                          triangle='triangle-up',
                          pentagon='pentagon',
                          hexagon='hexagon2',
                          octagon='octagon',
                          star='star',
                          diamond='diamond',
                          asterisk='asterisk-open',
                          hash='hash-open',
                          plus='cross-thin-open',
                          times='x-thin-open')
            out = lookup.get(tmp[0], 'circle')
            for opt in tmp[1:]:
                if opt == 'dot':
                    out += '-dot'
                elif opt == 'open':
                    if "open" not in out:
                        out += '-open'
        return out

    # this method is used to cleanup X/Y data vectors, removing NaN values as needed
    @staticmethod
    def clean_plot_data(data_in):
        data_out = list()
        common = 100000000
        for i in range(len(data_in)):
            data_out.append(list())
            common = min(len(data_in[i]), common)
        for i in range(common):
            keep = True
            for j in range(len(data_in)):
                x = data_in[j][i]
                if issubclass(type(x), float) or issubclass(type(x), numpy.float32):
                    if numpy.isnan(x):
                        keep = False
                        break
            if keep:
                for j in range(len(data_in)):
                    data_out[j].append(data_in[j][i])
        return data_out

    # plotly has issues with \r and \n in titles/labels/etc this method is used to clean them up
    @staticmethod
    def clean_label(s, allow_multiline=False):
        s = str(s)
        if allow_multiline is False:
            s = s.replace("\r", "").replace("\n", "")
        if s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
        return s

    @staticmethod
    def get_row_tags(data, context=None, default=None):
        return Item.get_labels(data, data['array'].shape[0], ('row_tags',), context, default)

    @staticmethod
    def get_column_tags(data, context=None, default=None):
        return Item.get_labels(data, data['array'].shape[1], ('col_tags',), context, default)

    @staticmethod
    def get_row_labels(data, context=None, default=None):
        return Item.get_labels(data, data['array'].shape[0], ('labels_row', 'rowlbls'), context, default)

    @staticmethod
    def get_column_labels(data, context=None, default=None):
        return Item.get_labels(data, data['array'].shape[1], ('labels_column', 'collbls'), context, default)

    @staticmethod
    def get_labels(data, n, allowed_props, context, default):
        labels = None
        for prop in allowed_props:
            # check context first
            if context is not None and prop in context:
                labels = context[prop]
            elif prop in data:  # else try data
                labels = data[prop]
            # break if found
            if labels is not None:
                break
        # if we have nothing, use the default
        if labels is None:
            labels = default
        # parse str into a list
        if type(labels) == str:
            labels = labels.strip()
            if labels:
                if (labels[0] == '[') and (labels[-1] == ']'):
                    labels = split_quoted_string_list(labels[1:-1], delimiter=',')
                    # labels = labels.strip()[1:-1].split(',')
                else:
                    # single value string becomes an array of that string
                    labels = [labels]
            else:
                # zero length string becomes an array of empty strings
                labels = []
        if type(labels) == list:
            labels = labels[:n]
            if len(labels) < n:
                labels.extend([''] * (n - len(labels)))
        return labels

    def generate_marker_text(self, template, x, y, row_name, number_format, color=None, size=None,
                             error=None, context=None, aux=None):
        if (template is None) or (len(x) < 1):
            return ""
        self.build_tag_dictionary()
        if aux is None:
            aux = list()
        plot = ""
        for i in range(len(x)):
            # add the local items to the dictionary
            t, dummy = format_value_general(x[i], number_format)
            self._tag_dict['vZx'] = t
            t, dummy = format_value_general(y[i], number_format)
            self._tag_dict['vZy'] = t
            if color is not None:
                if isinstance(color, list):
                    t, dummy = format_value_general(color[i], number_format)
                else:
                    t, dummy = format_value_general(color, number_format)
                self._tag_dict['vZcolor'] = t
            if size is not None:
                if isinstance(size, list):
                    t, dummy = format_value_general(size[i], number_format)
                else:
                    t, dummy = format_value_general(size, number_format)
                self._tag_dict['vZsize'] = t
            if error is not None:
                if isinstance(error, list):
                    t, dummy = format_value_general(error[i], number_format)
                else:
                    t, dummy = format_value_general(error, number_format)
                self._tag_dict['vZerror'] = t
            if row_name is not None:
                self._tag_dict['vZrowname'] = row_name
            # Aux channels are v/aux[0-9]
            for aux_idx in range(len(aux)):
                if aux[aux_idx] is not None:
                    if isinstance(aux[aux_idx], list):
                        t, dummy = format_value_general(aux[aux_idx][i], number_format)
                    else:
                        t, dummy = format_value_general(aux[aux_idx], number_format)
                    self._tag_dict[f'vZaux{aux_idx}'] = t
            tmp = expand_string_context(template, self._tag_dict)
            if context is not None:
                tmp = expand_string_context(tmp, context)
            tmp = TemplateEngine.context_expansion(tmp, self._tag_dict)
            plot += f"'{tmp}',"
        plot = f"text: [{plot}],\n"
        # unset the 'v/' values we set in the tag dictionary
        self._tag_dict.pop('vZx')
        self._tag_dict.pop('vZy')
        if color is not None:
            self._tag_dict.pop('vZcolor')
        if size is not None:
            self._tag_dict.pop('vZsize')
        if error is not None:
            self._tag_dict.pop('vZerror')
        if row_name is not None:
            self._tag_dict.pop('vZrowname')
        for aux_idx in range(len(aux)):
            if f'vZaux{aux_idx}' in self._tag_dict:
                self._tag_dict.pop(f'vZaux{aux_idx}')
        return plot

    def pick_alignment(self, align, default):
        '''
        Given a simple alignment string, generate the appropriate class for a table cell.
        :param align: Can be 'right', 'left', 'center' or 'justify'
        :param default: If ALIGN is not a supported value, what should be used
        :return: the class name, e.g. 'text-left'
        '''
        if align in ["right", "left", "center", "justify"]:
            return "text-" + align
        return default

    # generate HTML for this Item and return it as a string...
    def render(self, context, ext_ctx=None):
        if ext_ctx is None:
            ext_ctx = {}

        # collect the content
        s = ""

        # pass through some context keys
        ctx = copy.copy(context)
        for k in ['width', 'height', 'controls', 'format']:
            if k in ext_ctx:
                ctx[k] = ext_ctx[k]

        # if we are rendering in a report, there will be a template engine in the context
        if 'template_engine' in context:
            anchors = ctx['template_engine'].record_toc_entry(self, ctx)
            for tmp in anchors:
                # insert a link target <div>
                s += '<a id="{}"></a>'.format(tmp)
            if len(anchors):
                d = ctx['template_engine'].build_toc_properties()
                if len(d):
                    ctx.update(d)

        # In some cases, we have JavaScript variable names that may collide
        # if we do not give them unique names.  The Item guid does not work
        # as a single item can show up repeatedly in a report. So, we use a
        # one-shot GUID for this here:
        self.lcl_UUID = get_unique_id()

        # build the HTML string representation of the Item
        if self.get_default(None, ctx, 'item_context_debug') is not None:
            s += "<p>Item: {}<br>Context: {}<br>Item tags: {}<br></p>".format(
                self.guid, str(ctx), str(self.build_tag_dictionary()))

        self.media_auth_hash = ''

        if getattr(settings, 'ENABLE_ACLS', False):
            request = context.get('request')
            if request is not None:
                dict_to_hash = {
                    'obj_id': str(self.guid),
                    'user_id': request.user.id,
                    'has_view_perm': True
                }
                self.media_auth_hash = generate_media_auth_hash(dict_to_hash, str(self.guid))

        # get custom item alignments if any. start/end/center
        self.item_justification = ctx.get('item_justification', None)

        # render each type of item
        if self.type == "image":
            s += self.render_image(context, ctx)

        elif self.type == "anim":
            s += self.render_anim(context, ctx)

        elif self.type == "string":
            s += self.render_string(context, ctx)

        elif self.type == "html":
            s += self.render_html(context, ctx)

        elif self.type == "table":
            s += self.render_table(context, ctx)

        elif self.type == "scene":
            s += render_scene(self, context, ctx)

        elif self.type == "file":
            s += render_file(self, context, ctx)

        elif self.type == "none":
            s += "<p><em>No payload for the 'none' item type</em></p>"

        elif self.type == "tree":
            s += self.render_tree(context, ctx)

        else:
            s += "<p><em>Payload cannot be displayed for item type:" + str(self.type) + "</em></p>"

        # set justification. Default is no justification.
        if self.item_justification == "None":
            self.item_justification = None
        if self.item_justification is not None:
            if self.item_justification == 'left':
                self.item_justification = 'start'
            elif self.item_justification == 'right':
                self.item_justification = 'end'
            else:
                self.item_justification = 'center'
        else:
            if self.type in ["image", "anim", "scene"]:
                self.item_justification = 'center'

        if self.item_justification:
            if self.type == "scene":
                # if row, it will resize the scene to fit into the row width, which makes the 3D scene too small. 
                # Therefore, for a 3D scene item, use a column layout so it fits the height instead
                s = f'<div class="col justify-content-{self.item_justification}"><div class="col-md-auto">{s}</div></div>'
            else:
                s = f'<div class="row justify-content-{self.item_justification}"><div class="col-md-auto">{s}</div></div>'

        return s

    def render_image(self, context, ctx):
        s = ""
        is_deep_image = os.path.splitext(self.get_payload_file_url().lower())[1] in [".tif", ".tiff"]
        image_link = self.get_default(None, ctx, 'image_link', 0, force_int=True)
        if image_link and not is_deep_image:
            if image_link == 2:
                s += '<a href="' + self.get_payload_file_url() + '" target="_blank">'
            elif image_link == 1:
                s += '<a href="' + self.get_payload_file_url() + '" target="_self">'
            elif image_link == 3:
                s += '<a href="' + self.get_absolute_url() + '" target="_blank">'

        image_scale = ""
        tmp = self.get_default(None, context, "width", -1, force_int=True)
        if tmp > 1:
            image_scale += ' width="{}"'.format(tmp)
        tmp = self.get_default(None, context, "height", -1, force_int=True)
        if tmp > 1:
            image_scale += ' height="{}"'.format(tmp)
        image_class = 'class="img-fluid"'
        if len(image_scale):
            image_class = ''
        image_style = 'style="margin: 0 auto; display:flex; justify-content:center;"'

        media_payload_url = self.get_payload_file_url()
        if self.media_auth_hash:
            media_payload_url += f'?media_auth={self.media_auth_hash}'

        template_context = dict()
        template_context['is_deep_image'] = is_deep_image
        template_context['media_payload_url'] = media_payload_url
        template_context['image_class'] = image_class
        template_context['image_style'] = image_style
        template_context['image_scale'] = image_scale
        template_context['item_id'] = self.lcl_UUID
        s += render_to_string('data/item_layouts/image_item_template.html', template_context)

        if image_link and not is_deep_image:
            s += '</a>'
        return s

    def render_anim(self, context, ctx):
        s = ""
        image_display = self.get_default(None, context, 'image_display', 0, force_int=True)
        if TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF:
            image_display = 1
        if image_display == 1:
            s += '<p>Unable to generate thumbnail image for movie</p>\n'
            try:
                import enve
                import base64
                from PyQt5 import QtGui, QtCore
                movie_filename = self.get_payload_server_pathname()
                movie = enve.movie(enve.MOVIE_READ)
                movie.filename = movie_filename
                if movie.open() > -1:
                    image = movie.getframe(0)[0]
                    movie.close()
                    temp_image = QtGui.QImage.fromData(image.ppm(), "ppm")
                    ba = QtCore.QByteArray()
                    buf = QtCore.QBuffer(ba)
                    buf.open(QtCore.QIODevice.WriteOnly)
                    temp_image.save(buf, 'png')
                    buf.close()
                    imgsize = ""
                    tmp = self.get_default(None, context, "width", -1, force_int=True)
                    if tmp > 1:
                        imgsize += ' width="{}"'.format(tmp)
                    tmp = self.get_default(None, context, "height", -1, force_int=True)
                    if tmp > 1:
                        imgsize += ' height="{}"'.format(tmp)
                    imgformat = 'class ="img img-fluid" style="margin: 0 auto;"'
                    imgsrc = "data:image/png;base64," + base64.b64encode(buf.data()).decode("utf-8")
                    s = '<img src="{}" {} {}>'.format(imgsrc, imgformat, imgsize)
            except:
                pass
        else:
            s += '<video  class="img img-fluid" style="margin: 0 auto;" '
            tmp = self.get_default(None, context, "width", -1, force_int=True)
            if tmp > 1:
                s += ' width="{}"'.format(tmp)
            tmp = self.get_default(None, context, "height", -1, force_int=True)
            if tmp > 1:
                s += ' height="{}"'.format(tmp)
            cont = str(self.get_default(None, ctx, 'controls', None))
            if cont == '1':
                s += ' controls'
            elif cont == '2':
                s += ' autoplay'
            elif cont == '3':
                s += ' controls autoplay'
            elif cont == 'None':
                s += ' controls'
            s += ' muted loop>\n'

            media_payload_url = self.get_payload_file_url()
            if self.media_auth_hash:
                media_payload_url += f'?media_auth={self.media_auth_hash}'

            s += f'<source src="{media_payload_url}" type="video/mp4">\n'
            s += '<p>Video display not supported or animation file could not be found</p>\n'
            s += '</video>'
        return s

    def render_string(self, context, ctx):
        s = ""
        just = self.get_default(None, ctx, 'justification', default='center')
        if just == 'right':
            s += '<div class="text-right">'
        elif just == 'left':
            s += '<div class="text-left">'
        elif just == 'justify':
            s += '<div class="text-justify">'
        else:
            s += '<div class="text-center">'
        tmp = '<p>' + safe_unpickle(self.payloaddata) + '</p>'
        tmp = convert_macro_slashes(tmp)
        django_engine = engines['django']
        try:
            template = django_engine.from_string('{% load data_tags %}' + tmp)
            tmp = template.render(context=ctx)
        except Exception as e:
            tmp += "<br><p><b>Macro expansion error: {}</b></p>".format(str(e))
        s += tmp + '</div>\n'
        return s

    def render_html(self, context, ctx):
        tmp = safe_unpickle(self.payloaddata)
        tmp = convert_macro_slashes(tmp)
        django_engine = engines['django']
        try:
            template = django_engine.from_string('{% load data_tags %}' + tmp)
            tmp = template.render(context=ctx)
        except Exception as e:
            tmp += "<br><p><b>Macro expansion error: {}</b></p>".format(str(e))
        return tmp + '\n'

    def get_ext_url(self, ext_view=False):
        ext_url = ""
        return ext_url

    @staticmethod
    def format_table_value(value, format_str, context=None, item=None):
        formatted_string, data_representation = format_value_general(value, format_str)
        if context is not None:
            if ('{{' in value) and ('}}' in value):
                formatted_string = TemplateEngine.context_expansion(formatted_string, context, item=item)
        return formatted_string, data_representation

    @staticmethod
    def hoverinfo(name, marker_text_rowname):
        """Generate trace hoverinfo: 'value'
        For backward compatibility, if "name" has length, then include it.
        marker_text_rowname can be 0, 1, -1 for "force name off", "force name on"
        and "use backward compatible value".
        """
        if marker_text_rowname == 1:
            return "'text+name'"
        elif marker_text_rowname == 0:
            return "'text'"
        elif len(name):
            return "'text+name'"
        return "'text'"

    def render_table(self, context, ctx):
        s = ""
        # self.payloaddata is bytes sometimes, whenever a generator is used.
        # 2 cases:
        # - ephemeral table items can be generated dynamically and are passed around in bytes
        # - permanent table items that are stored in db, when read back, they are str
        # so we handle both in safe_unpickle
        data = safe_unpickle(self.payloaddata)

        # get justification
        if 'item_justification' in data:
            self.item_justification = data['item_justification']

        # if the numpy array is empty, what's the point?
        if data['array'].size == 0:
            return s

        # We have to decode each element in the numpy array explicitly to utf-8 strings before rendering
        # BUT only if the dtype is bytes.
        # Be aware that row and col labels can be bytes as well, as these are derived from table data.
        # so they have to be decoded as well.
        if data['array'].dtype.type == numpy.bytes_:
            data = decode_table_data(data)

        # ok, pick plot or table display
        # if the incoming context picked something, use item
        # otherwise ask the data block what it wants, otherwise
        # use a table...
        # plot_type=0 : table
        # plot_type=1 : line
        # plot_type=2 : bar
        # plot_type=3 : pie
        # plot_type=4 : heatmap
        # plot_type=5 : parallel coordinates
        # plot_type=6 : sankey graph
        plot_map = {
            'table': 0,
            'line': 1,
            'bar': 2,
            'pie': 3,
            'heatmap': 4,
            'parallel': 5,
            'sankey': 6,
        }
        chosen_plot = ctx.get('plot', data.get('plot', 'table'))
        plot_type = plot_map.get(chosen_plot, 0)

        if plot_type == 0:
            # Display as a table ####################################
            s += self.render_table_as_table(data, context, ctx)
        else:
            # Display as a plot.ly plot ################################
            s += self.render_table_as_plot(plot_type, data, context, ctx)

        return s

    def render_table_as_plot(self, plot_type: int, data: dict, context: dict, ctx: dict) -> str:
        # The HTML being built
        s = ""

        # number of rows and columns
        nrows, ncols = data['array'].shape
        # tags
        row_tags = self.get_row_tags(data, context)
        col_tags = self.get_column_tags(data, context)

        # plotly.js target div
        s += '<div class="nexus-plot" id="plot_' + self.lcl_UUID + '" style="'
        if 'width' in ctx:
            s += 'width: ' + str(ctx['width']) + 'px;'
        if 'height' in ctx:
            s += 'height: ' + str(ctx['height']) + 'px;'
        s += '"></div>'
        # do we need to embed or locally reference plotly?
        plotlyjs = self.get_default(None, ctx, 'plotly', default=0, force_int=True)
        # can be referencedheader(0), embedded_payload(1), referenced_payload(2)
        payload = ""
        if plotlyjs == 1:
            pathname = os.path.join(settings.BASE_DIR, 'website', 'static', 'website', 'scripts',
                                    'plotly.min.js')
            with open(pathname, "rt", encoding='utf-8') as f:
                src = f.read()
            payload += "<script>" + src + "</script>\n"
        elif plotlyjs == 2:
            s += '<script src="/static/website/scripts/plotly.min.js"></script>\n'
        # different plot types:
        # explicit x and y -> line plot with row labels as axis titles
        # implicit x -> line/bar plot with each row as values.
        #    row labels -> legends (if only 1, Y axis?)
        #    col labels -> xaxis labels
        default_row_labels = [None] * nrows
        if plot_type == 4:
            # for a heatmap, use the row range values
            default_row_labels = list(range(nrows))
        rowlbls = self.get_row_labels(data, context, default_row_labels)
        collbls = self.get_column_labels(data, context, list(range(ncols)))

        # get the plotter x and y ranges
        x_range = self.get_default(data, ctx, 'xrange')
        y_range = self.get_default(data, ctx, 'yrange')
        if type(x_range) == str:
            try:
                _ = json.loads(x_range)
            except ValueError:
                x_range = None
        if type(y_range) == str:
            try:
                _ = json.loads(y_range)
            except ValueError:
                y_range = None

        # get the xaxis handler (and the yaxis maps)
        xaxis_obj = XAxisObj(ctx, data, rowlbls, collbls, self)
        xrows = xaxis_obj.x_row_indices()
        xaxistitle = xaxis_obj.title()
        # build up the array of Y values
        ydata = []
        xdata = []
        ytitle = []
        for j in xaxis_obj.y_row_indices():
            xd = xaxis_obj.data(j)
            xdata.append(xd)
            yd = data['array'][j]
            ydata.append(yd)
            ytitle.append(rowlbls[j])

        # titles
        yaxistitle = None
        if len(ytitle) == 1:
            yaxistitle = ytitle[0]
        yaxistitle = ctx.get('ytitle', data.get('ytitle', yaxistitle))

        # Convert titles to JavasScript use
        if xaxistitle is not None:
            xaxistitle = self.format_for_javascript(str(xaxistitle), latex=True)
        if yaxistitle is not None:
            yaxistitle = self.format_for_javascript(str(yaxistitle), latex=True)

        # should there be a legend displayed
        show_legend = self.get_default(data, ctx, 'show_legend', default=1, force_int=True)
        if show_legend:
            show_legend = 'true'
        else:
            show_legend = 'false'
        legend_position = self.get_default(data, ctx, 'legend_position', None)
        try:
            # legend_position = json.loads(str(legend_position))
            legend_position = eval(str(legend_position))
            if (type(legend_position) is not list) and (len(legend_position) != 2):
                legend_position = None
        except:
            legend_position = None
        show_legend_border = self.get_default(data, ctx, 'show_legend_border', default=0,
                                              force_int=True)

        # get the core number format(s)
        number_format = self.get_indexed_default(data, ctx, 0, 'format', default='scientific')
        xaxis_number_format = self.get_default(data, ctx, 'xaxis_format', default=number_format)
        yaxis_number_format = self.get_default(data, ctx, 'yaxis_format', default=number_format)

        # We only allow one colormap per plot
        palette = self.get_default(data, ctx, 'palette', None)
        if palette is not None:
            reverse_palette = self.get_default(data, ctx, 'palette_reverse', default=0,
                                               force_int=True)
            if palette[0] == '-':
                reverse_palette = True
                palette = palette[1:]

            legal_palettes = ['Greys', 'YlGnBu', 'Greens', 'YlOrRd', 'Bluered',
                              'RdBu', 'Reds', 'Blues', 'Picnic', 'Rainbow', 'Portland',
                              'Jet', 'Hot', 'Blackbody', 'Earth', 'Electric', 'Viridis']
            if palette in legal_palettes:
                palette_range = self.get_default(data, ctx, 'palette_range', None)
                try:
                    palette_range = json.loads(str(palette_range))
                except ValueError:
                    palette_range = None
                palette_position = self.get_default(data, ctx, 'palette_position', None)
                try:
                    # palette_position = json.loads(str(palette_position))
                    palette_position = eval(str(palette_position))
                    if (type(palette_position) is not list) and (len(palette_position) != 2):
                        palette_position = None
                except Exception:
                    palette_position = None
                palette_show = self.get_default(data, ctx, 'palette_show', default=0,
                                                force_int=True)
            else:
                palette = None
            palette_title = self.get_default(data, ctx, 'palette_title')

        # Should hoverinfo text include the rowname?
        marker_text_rowname = self.get_default(data, ctx, 'marker_text_rowname',
                                               default=-1, force_int=True)
        # marker scaling (Mx+B) applied to the marker size
        y_line_marker_scale = self.get_default(data, ctx, 'line_marker_scale', None)
        try:
            y_line_marker_scale = json.loads(str(y_line_marker_scale))
            y_line_marker_scale = [float(x) for x in y_line_marker_scale]
        except Exception:
            y_line_marker_scale = [1., 0.]

        # start the plotly.js script
        plot = "<script>\n"
        if plot_type == 4:
            # Heatmap : table is a 2D array of 'Z' values (z=f(x,y))
            number_format = self.get_default(data, ctx, 'format', default='scientific')
            # Build the data object
            dvar = f"var data_{self.lcl_UUID} = [{{"
            dvar += "type: 'heatmap',\n"

            x_title = "x"
            if xaxistitle is not None:
                x_title = xaxistitle.strip("'")
            y_title = "y"
            if yaxistitle is not None:
                y_title = yaxistitle.strip("'")

            z_data = "z:["
            z_text = "text:["
            array = data['array']
            for j in range(nrows):
                z_text += "["
                z_data += "["
                for i in range(ncols):
                    try:
                        v = float(array[j, i])
                    except ValueError:
                        v = numpy.nan
                    if numpy.isnan(v):
                        v = "null"
                        v_text = "Undefined"
                    else:
                        v_text, _ = format_value_general(v, number_format)
                    z_data += f"{v},"
                    z_text += f"'{v_text}<br>{x_title}:{str(collbls[i])}<br>{y_title}:{str(rowlbls[j])}',"
                z_data += "],\n"
                z_text += "],\n"
            z_data += "],\n"
            z_text += "],\n"

            dvar += z_data
            dvar += f"x:{str(collbls)},\n"
            dvar += f"y:{str(rowlbls)},\n"
            dvar += z_text
            dvar += "hoverongaps: false,\n"
            dvar += "hoverinfo: 'text',\n"
            if self.get_default(data, ctx, 'show_border', default=0, force_int=True):
                dvar += "xgap: 1, ygap: 1,\n"
            if palette is not None:
                dvar += f"colorscale: '{palette}',\n"
                if palette_show:
                    dvar += "showscale: true,\n"
                else:
                    dvar += "showscale: false,\n"
                if palette_range is not None:
                    dvar += f"zmin:{palette_range[0]},zmax:{palette_range[1]},\n"
                if reverse_palette:
                    dvar += "reversescale: true,\n"
                dvar += "colorbar: {\n"
                dvar += f"tickformat: '{format_plotly(number_format)}',\n"
                dvar += "},\n"
            dvar += "}];\n"
            plot += dvar

        elif plot_type == 5:
            # Parallel coordinates : Columns are the coordinates, each row is an observation
            dvar = f"var data_{self.lcl_UUID} = [{{"
            dvar += "type: 'parcoords',\n"

            # color the lines via indexed value(s)
            a_color = self.get_indexed_default(data, ctx, 0, 'line_color', default=None)
            if a_color is not None:
                dvar += "line: {\n"
                dvar += f"color: {[x for x in range(nrows)]},\n"
                dvar += "colorscale: [\n"
                for j in range(nrows):
                    a_color = self.get_indexed_default(data, ctx, j, 'line_color', default=None)
                    v = float(j)/float(nrows-1)
                    if isinstance(a_color, list):
                        dvar += f"[{v}, {a_color}],\n"
                    else:
                        dvar += f"[{v}, '{a_color}'],\n"
                dvar += "],\n"
                dvar += "},\n"

            # Now the actual data
            array = data['array']
            dvar += "dimensions: [\n"
            # Should the row labels be included as a column?
            if yaxistitle is not None:
                dvar += "{\n"
                dvar += f"range: [1, {nrows}],\n"
                dvar += f"values: {list(range(1,nrows+1))},\n"
                dvar += f"ticktext: {rowlbls},\n"
                dvar += f"tickvals: {list(range(1,nrows+1))},\n"
                dvar += f"label: {yaxistitle},\n"
                dvar += "},\n"
            # Each column has a range and specific formatting
            for i in range(ncols):
                col_format = self.get_indexed_default(data, ctx, i, 'format', default=number_format)
                dvar += "{\n"
                dvar += f"tickformat: '{format_plotly(col_format)}',\n"
                dvar += f"label: '{collbls[i]}',\n"
                # All the observations of this label type
                dvar += "values: ["
                v_range = [sys.float_info.max, -sys.float_info.max]
                for j in range(nrows):
                    try:
                        v = float(array[j, i])
                        dvar += f"{v},"
                    except ValueError:
                        v = numpy.nan
                        # This is not entirely correct, as it maps to 0.0,
                        # but it is a limitation of plotly parallel coords for now
                        # Note: if NaN is passed, the entire trace is skipped.
                        dvar += "null,"
                    v_range[0] = min(v, v_range[0])
                    v_range[1] = max(v, v_range[1])
                dvar += "],\n"
                col_min = self.get_indexed_default(data, ctx, i, 'column_minimum',
                                                   default=v_range[0])
                col_max = self.get_indexed_default(data, ctx, i, 'column_maximum',
                                                   default=v_range[1])
                dvar += f"range: [{col_min},{col_max}],\n"
                # end of dimension
                dvar += "},\n"
            # end of dimensions array
            dvar += "],\n"
            dvar += "}];\n"
            plot += dvar

        elif plot_type == 6:
            # Sankey
            # The interpretation here is as a dense matrix instead of a sparse node
            # graph.  The row and column labels are the nodes (and must be the same).
            # The row represents the "source" node and the column, the "target" node.
            # The value in the matrix is the "size" of that flow connection.  While this
            # is inefficient for sparse nodal flows, it has the advantage of allowing
            # "self organizing" inter-node links.
            #
            dvar = f"var data_{self.lcl_UUID} = [{{"
            dvar += "type: 'sankey',\n"
            dvar += "orientation: 'h',\n"
            dvar += f"valueformat: '{format_plotly(number_format)}',\n"
            dvar += "node: {\n"
            dvar += "pad: 15, thickness: 30,\n"
            dvar += f"label: {str(collbls)},\n"
            dvar += "},\n"

            link_sources = list()
            link_targets = list()
            link_values = list()
            array = data['array']
            for source in range(nrows):
                for target in range(ncols):
                    try:
                        value = float(array[source, target])
                    except ValueError:
                        value = numpy.nan
                    # if the source->target weight is > 0., treat it as a link
                    if value > 0.:
                        link_sources.append(source)
                        link_targets.append(target)
                        link_values.append(value)

            # record the links
            dvar += "link: {\n"
            dvar += f"    source: {link_sources},\n"
            dvar += f"    target: {link_targets},\n"
            dvar += f"    value: {link_values},\n"
            dvar += "},\n"

            dvar += "}];\n"
            plot += dvar

        else:
            # Line/Bar/Pie all use similar "trace" structure. Handle them all here.
            # plot_type in [1,2,3]
            # define the axes: titles, ranges, ticking...
            dvar = f"var data_{self.lcl_UUID} = ["
            if len(ydata) > 1:
                chunk = 1.0 / (float(len(ydata)))
                inset = chunk * 0.05
            else:
                chunk = 1.0
                inset = 0.0
            # create blocks for each trace
            for j in range(len(ydata)):
                # Let's get some defaults for properties
                # line_color
                y_color = self.get_indexed_default(data, ctx, j, 'line_color')
                # line_marker_opacity
                y_marker_opacity = self.get_indexed_default(data, ctx, j, 'line_marker_opacity',
                                                            default="1.0")
                # line_style
                y_line_style = self.get_indexed_default(data, ctx, j, 'line_style')
                # line_marker
                y_line_marker = self.convert_marker_to_plotly(
                    self.get_indexed_default(data, ctx, j, 'line_marker'))
                # line_marker_size
                y_line_marker_size = self.get_indexed_default(data, ctx, j, 'line_marker_size')
                # line_marker_text
                y_line_marker_text = self.get_indexed_default(data, ctx, j, 'line_marker_text')
                # line_error_bars
                y_line_error_bars = self.get_indexed_default(data, ctx, j, 'line_error_bars')
                # line_width
                y_line_width = self.get_indexed_default(data, ctx, j, 'line_width')
                # "aux" channels can be used in marker texts as v/aux[0-9].
                # The properties are: line_marker_aux[0-9]
                y_line_aux = []
                for aux in range(10):
                    y_line_aux.append(self.get_indexed_default(data, ctx, j, f'line_marker_aux{aux}'))

                # filter out values based on NaN processing
                input_data = list()
                if plot_type == 3:  # pie charts are a little different here...
                    # each row is a pie graph 'values' wedge name ('labels') is collbls
                    # the row label is the pie 'name'
                    input_data.append(collbls)
                else:
                    input_data.append(xdata[j])
                input_data.append(ydata[j])
                # Add the 4 "special" values
                tmp = xaxis_obj.get_row_reference(y_color)
                if tmp is not None:
                    input_data.append(tmp)
                tmp = xaxis_obj.get_row_reference(y_line_marker_size)
                if tmp is not None:
                    input_data.append(tmp)
                tmp = xaxis_obj.get_row_reference(y_line_error_bars)
                if tmp is not None:
                    input_data.append(tmp)

                # Add "aux" channels
                for aux in range(len(y_line_aux)):
                    # if it was set at all in the properties
                    if y_line_aux[aux]:
                        # is it a row reference?  vs a "value"
                        tmp = xaxis_obj.get_row_reference(y_line_aux[aux])
                        if tmp is not None:
                            # Schedule the row to be "cleaned"
                            input_data.append(tmp)

                # filter the data
                output_data = self.clean_plot_data(input_data)

                x_clean = output_data.pop(0)
                y_clean = output_data.pop(0)
                # Extract the "special" values (outputs become lists)
                if xaxis_obj.is_row_reference(y_color):
                    y_color = output_data.pop(0)
                if xaxis_obj.is_row_reference(y_line_marker_size):
                    y_line_marker_size = output_data.pop(0)
                if xaxis_obj.is_row_reference(y_line_error_bars):
                    y_line_error_bars = output_data.pop(0)

                # Extract cleaned "aux" channels
                for aux in range(len(y_line_aux)):
                    if y_line_aux[aux]:
                        if xaxis_obj.is_row_reference(y_line_aux[aux]):
                            y_line_aux[aux] = output_data.pop(0)

                # build the plotly 'trace' Javascript object
                plot += " var data_{} = {{\n".format(j)
                if plot_type == 2:  # Bar chart
                    if xaxis_number_format.startswith('date'):
                        tmp = convert_datelist_to_plotly_datelist(x_clean)
                    else:
                        tmp = x_clean
                    plot += "  x: {},\n".format(str(tmp))
                    if yaxis_number_format.startswith('date'):
                        tmp = convert_datelist_to_plotly_datelist(y_clean)
                    else:
                        tmp = y_clean
                    plot += "  y: {},\n".format(str(tmp))
                    plot += "  type: 'bar',\n"
                    plot += "  textposition: 'none',\n"
                    plot += "  showlegend: {},\n".format(show_legend)
                    if ytitle[j] is not None:
                        data_name = str(self.clean_label(ytitle[j]))
                    else:
                        data_name = "Row {}".format(j)
                    plot += "  name: '{}',".format(data_name)
                    # Hover info
                    plot += "  hoverinfo: 'closest',\n"
                    # the hover text by default is '(x, y) name' with x and y formatted as per number_format
                    txt = list()
                    for x, y in zip(x_clean, y_clean):
                        x_1, dummy = format_value_general(x, xaxis_number_format)
                        y_1, dummy = format_value_general(y, yaxis_number_format)
                        tmp = "({}, {})".format(x_1, y_1)
                        txt.append(tmp)
                    plot += "  text: {},\n".format(str(txt))
                    # exert explicit control
                    hoverinfo = self.hoverinfo(data_name, marker_text_rowname)
                    plot += f"  hoverinfo: {hoverinfo},\n"
                    plot += self.generate_marker_text(y_line_marker_text, x_clean, y_clean, data_name,
                                                      number_format, color=y_color,
                                                      size=y_line_marker_size,
                                                      error=y_line_error_bars, context=ctx,
                                                      aux=y_line_aux)
                    plot += "  marker: {"
                    if y_color is not None:
                        if isinstance(y_color, list):
                            plot += "color: {},\n".format(y_color)
                        else:
                            plot += "color: '{}',\n".format(y_color)
                    plot += " },\n"
                    if y_line_error_bars is not None:
                        plot += "   error_y: {\n"
                        plot += "     visible: true,\n"
                        if isinstance(y_line_error_bars, list):
                            plot += " type: 'data',\n"
                            plot += " array: {},\n".format(str(y_line_error_bars))
                        else:
                            plot += " type: 'constant',\n"
                            plot += " value: {},\n".format(y_line_error_bars)
                        if y_color is not None:
                            if isinstance(y_color, list):
                                plot += "color: {},\n".format(y_color)
                            else:
                                plot += "color: '{}',\n".format(y_color)
                        plot += "   },\n"
                elif plot_type == 3:  # Pie chart
                    plot += "  labels: {},\n".format(str(x_clean))
                    plot += "  values: {},\n".format(str(y_clean))
                    txt = []
                    for v in ydata[j]:
                        txt.append(self.clean_label(format_value_general(v, yaxis_number_format)[0]))
                    plot += "  text: {},\n".format(str(txt))
                    plot += "  textinfo: 'percent',\n"
                    hoverinfo = "'label+text+name'"
                    if marker_text_rowname == 0:
                        hoverinfo = "'label+text'"
                    plot += f"  hoverinfo: {hoverinfo},\n"
                    plot += "  domain: {{ x: [{}, {}]}},\n".format(j * chunk + inset,
                                                                   (j + 1) * chunk - inset)
                    if rowlbls[j] is not None:
                        plot += "  name: '{}',\n".format(str(self.clean_label(rowlbls[j])))
                    else:
                        plot += "  name: 'Row {}',".format(j)
                    plot += "  type: 'pie',\n"
                    colors = self.get_default(data, ctx, 'line_color')
                    if colors:
                        colors = colors[1:-1].split(',')
                        tmp = ""
                        for c in colors:
                            if ("'" in c) or ('[' in c):
                                tmp += f"{c},"
                            else:
                                tmp += f"'{c}',"
                        plot += "  marker: { colors: [" + tmp + "], }, \n"
                else:  # Line chart (scatter plot, potentially with a cardinal X axis)
                    if xaxis_number_format.startswith('date'):
                        tmp = convert_datelist_to_plotly_datelist(x_clean)
                    else:
                        tmp = x_clean
                    # add tags for lookup
                    plot += " tags: {\n"
                    y_row_idx = xaxis_obj.y_row_indices()[j]
                    # tags
                    row_tag = row_tags[y_row_idx] if row_tags else self.tags
                    tag_dict = self.get_tag_dict_from_str(row_tag)
                    for key, value in tag_dict.items():
                        plot += f"     '{key}': '{value}',\n"
                    plot += "  },\n"
                    # data
                    plot += "  x: {},\n".format(str(tmp))
                    if yaxis_number_format.startswith('date'):
                        tmp = convert_datelist_to_plotly_datelist(y_clean)
                    else:
                        tmp = y_clean
                    plot += "  y: {},\n".format(str(tmp))
                    if ytitle[j] is not None:
                        data_name = str(self.clean_label(ytitle[j]))
                    else:
                        data_name = "Row {}".format(j)
                    plot += "  name: '{}',".format(data_name)
                    name_text = self.generate_marker_text(y_line_marker_text, x_clean, y_clean,
                                                          data_name,
                                                          number_format, color=y_color,
                                                          size=y_line_marker_size,
                                                          error=y_line_error_bars, context=ctx,
                                                          aux=y_line_aux)
                    hoverinfo = self.hoverinfo(name_text, marker_text_rowname)
                    if len(name_text) > 0:
                        plot += name_text
                        plot += f"  hoverinfo: {hoverinfo},\n"
                    else:
                        # the hover text by default is '(x, y) name' with x and y formatted as per number_format
                        txt = list()
                        for x, y in zip(x_clean, y_clean):
                            x_1, dummy = format_value_general(x, xaxis_number_format)
                            y_1, dummy = format_value_general(y, yaxis_number_format)
                            tmp = "({}, {})".format(x_1, y_1)
                            txt.append(tmp)
                        plot += "  text: {},\n".format(str(txt))
                        plot += f"  hoverinfo: {hoverinfo},\n"

                    plot += "  type: 'scatter',\n"
                    # do we want a legend
                    plot += "  showlegend: {},\n".format(show_legend)
                    # pick some markers
                    if y_line_style == 'none':
                        plot += "  mode: 'markers',\n"
                    else:
                        if y_line_marker == 'none':
                            plot += "  mode: 'lines',\n"
                        else:
                            plot += "  mode: 'lines+markers',\n"

                    # marker info
                    plot += "  marker: { \n"
                    plot += "opacity: {},\n".format(y_marker_opacity)
                    if y_color is not None:
                        if isinstance(y_color, list):
                            plot += "color: {},\n".format(y_color)
                        else:
                            plot += "color: '{}',\n".format(y_color)
                    if y_line_marker is not None:
                        plot += "symbol: '{}',\n".format(y_line_marker)
                    if y_line_marker_size is not None:
                        tmp = y_line_marker_size
                        if isinstance(y_line_marker_size, list):
                            try:
                                tmp = [x * y_line_marker_scale[0] + y_line_marker_scale[1] for x in
                                       y_line_marker_size]
                            except:
                                pass
                        plot += "size: {},\n".format(tmp)

                    # palette bits
                    if palette is not None:
                        plot += "colorscale: '{}',".format(palette)
                        if palette_show:
                            plot += "showscale:true,"
                        else:
                            plot += "showscale:false,"
                        if palette_range is not None:
                            plot += "cmin:{},cmax:{}, ".format(palette_range[0], palette_range[1])
                        if reverse_palette:
                            plot += "reversescale:true,"
                        if (palette_position is not None) or (palette_title is not None):
                            plot += "colorbar:{"
                        if palette_position is not None:
                            plot += "x:{},y:{},".format(palette_position[0], palette_position[1])
                        if palette_title is not None:
                            plot += "title:'{}',titleside:'right',".format(palette_title)
                        if (palette_position is not None) or (palette_title is not None):
                            plot += "},"
                        plot += "\n"
                    # end of the marker block
                    plot += " },\n"

                    # line block
                    plot += "  line: {\n"
                    if y_color:
                        if isinstance(y_color, list):
                            pass  # plot += "color: {},\n".format(y_color)
                        else:
                            plot += "color: '{}',\n".format(y_color)
                    if y_line_width:
                        plot += "width: {},\n".format(y_line_width)
                    if y_line_style:
                        plot += "dash: '{}',\n".format(y_line_style)
                    plot += " },\n"
                    if y_line_error_bars is not None:
                        plot += "   error_y: {\n"
                        plot += "     visible: true,\n"
                        if isinstance(y_line_error_bars, list):
                            plot += " type: 'data',\n"
                            plot += " array: {},\n".format(str(y_line_error_bars))
                        else:
                            plot += " type: 'constant',\n"
                            plot += " value: {},\n".format(y_line_error_bars)
                        if y_color is not None:
                            if isinstance(y_color, list):
                                pass  # plot += "color: {},\n".format(y_color)
                            else:
                                plot += "color: '{}',\n".format(y_color)
                        plot += "   },\n"
                plot += " };\n"
                dvar += "data_{},".format(j)
            dvar += "];\n"
            plot += dvar

        # copy data to backup
        plot += f"var const_data_{self.lcl_UUID} = JSON.parse(JSON.stringify(data_{self.lcl_UUID}));\n"

        # get theme from color mode for now.
        color_mode = ctx.get("color_mode")
        if color_mode not in PLOTLY_THEMES:
            color_mode = "light"
        # get theme
        theme_info = PLOTLY_THEMES[color_mode]

        # build 'layout'
        plot += " var layout = {\n"
        # get colors
        font_color = theme_info['layout']['font']['color']
        paper_color = theme_info['layout']['paper_bgcolor']
        plot_color = theme_info['layout']['plot_bgcolor']
        # add
        plot += f'   font: {{color: "{font_color}"}},\n'
        plot += f'   paper_bgcolor: "{paper_color}",\n'
        plot += f'   plot_bgcolor: "{plot_color}",\n'
        # try the plot specific title, falling back to title if needed
        plot_title = self.get_default(data, ctx, 'plot_title', self.get_default(data, ctx, 'title'))
        if plot_title is not None:
            plot_title = self.format_for_javascript(str(plot_title), latex=True)
            plot += "   title: {},\n".format(plot_title)
        plot += 'margin: { '
        steps = ['l', 't', 'r', 'b']
        for lbl in steps:
            tmp = self.get_indexed_default(data, ctx, steps.index(lbl), 'plot_margins', default='')
            if len(tmp):
                try:
                    n = int(tmp)
                    plot += '{}: {},'.format(lbl, n)
                except:
                    pass
        plot += '},\n'
        if plot_type != 3:  # all but pie mode have "axes"
            plot += "   xaxis: {\n"
            plot += '     zeroline: true,\n'

            xaxis_theme = theme_info['layout']['xaxis']
            grid_color = xaxis_theme['gridcolor']
            zero_line_color = xaxis_theme['zerolinecolor']
            plot += f'     gridcolor: "{grid_color}",\n' \
                    f'     zerolinecolor: "{zero_line_color}",\n'

            if self.get_default(data, ctx, 'show_border', default=0, force_int=True):
                plot += "     mirror: true, showline: true,\n"
                # add color
                line_color = xaxis_theme['linecolor']
                plot += f'     linecolor: "{line_color}",\n'


            if xaxistitle is not None:
                plot += "     title: {},\n".format(xaxistitle)
            plot += "     tickformat: '{}',\n".format(format_plotly(xaxis_number_format))
            if x_range:
                plot += "     range: {}, \n".format(str(x_range))
            else:
                plot += "     autorange: true, \n"
            tmp = ctx.get('plot_xaxis_type', data.get('plot_xaxis_type', None))
            if tmp:
                plot += "     type: '{}',\n".format(tmp)
            plot += "   },\n"
            # y axis
            plot += "   yaxis: {\n"
            plot += '     zeroline: true,\n'

            yaxis_theme = theme_info['layout']['yaxis']
            grid_color = yaxis_theme['gridcolor']
            zero_line_color = yaxis_theme['zerolinecolor']
            plot += f'     gridcolor: "{grid_color}",\n' \
                    f'     zerolinecolor: "{zero_line_color}",\n'

            if self.get_default(data, ctx, 'show_border', default=0, force_int=True):
                plot += "     mirror: true, showline: true,\n"
                # add color
                line_color = yaxis_theme['linecolor']
                plot += f'     linecolor: "{line_color}",\n'

            if yaxistitle is not None:
                plot += "     title: {},\n".format(yaxistitle)
            plot += "     tickformat: '{}',\n".format(format_plotly(yaxis_number_format))
            if y_range:
                plot += "     range: {}, \n".format(str(y_range))
            else:
                plot += "     autorange: true, \n"
            tmp = ctx.get('plot_yaxis_type', data.get('plot_yaxis_type', None))
            if tmp:
                plot += "     type: '" + tmp + "',\n"
            plot += "   },\n"
            if plot_type == 2:  # Bar mode supports stacked
                if int(ctx.get('stacked', data.get('stacked', '0'))) != 0:
                    plot += "   barmode: 'stack',\n"
            plot += "     hovermode: 'closest',\n"
        # set the legend options
        plot += "  showlegend: {},\n".format(show_legend)
        if show_legend == 'true':
            plot += "   legend: {\n"
            if legend_position is not None:
                try:
                    plot += "   x:{},y:{},\n".format(legend_position[0], legend_position[1])
                except:
                    pass
            if show_legend_border > 0:
                plot += "    borderwidth: {},\n".format(show_legend_border)
            plot += "   },\n"
        plot += " };\n"  # end 'layout'
        # general options
        image_save = ""
        if int(ctx.get('save_plot_image', data.get('save_plot_image', '1'))) == 0:
            image_save = ", 'toImage'"
        plot += " var options = {\n"
        plot += "    showLink: false,\n"
        plot += "    displaylogo: false,\n"
        plot += f"    modeBarButtonsToRemove: ['sendDataToCloud', 'select2d', 'lasso2d'{image_save}],\n"
        # for backward compatibility, include these for the older plot types
        if plot_type < 4:
            plot += "    modeBarButtonsToAdd: ['toggleSpikelines', 'v1hovermode'],\n"
        plot += " };\n"
        # build the plot objects
        plot += f" pobj_{self.lcl_UUID} = document.getElementById('plot_{self.lcl_UUID}');\n"
        plot += f" Plotly.newPlot( pobj_{self.lcl_UUID}, data_{self.lcl_UUID}, layout, options);\n"
        plot += f" window.addEventListener('resize', function() {{ Plotly.Plots.resize(pobj_{self.lcl_UUID});}});\n"

        plot += f" pobj_{self.lcl_UUID}.addEventListener('filter_event', function(event) {{\n"
        plot += f"   for (let [key, value] of Object.entries(const_data_{self.lcl_UUID})) {{\n"
        plot += f"     data_{self.lcl_UUID}[key] = JSON.parse(JSON.stringify(value));\n"
        plot += "   };\n"
        plot += "   event.detail.forEach((filterDetail, key) => {\n"
        plot += "     let tempData;\n"
        plot += "     switch (key) {\n"
        plot += "       case 'plot_range_x':\n"
        plot += "         filterDetail.forEach((rangeObject, key) => {\n"
        plot += "           tempData = JSON.parse(JSON.stringify(data_{}));\n".format(self.lcl_UUID)
        plot += "           tempData.forEach((trace, index) => {\n"
        plot += "             let min = rangeObject.min;\n"
        plot += "             let max = rangeObject.max;\n"
        plot += f"             data_{self.lcl_UUID}[index]['x'] = trace['x'].filter((value) =>"
        plot += " value >= min && value <= max);\n"
        plot += f"             data_{self.lcl_UUID}[index]['y'] = trace['y'].filter((value, index) =>"
        plot += " trace['x'][index] >= min && trace['x'][index] <= max);\n"
        plot += "           });\n"
        plot += "         });\n"
        plot += "         break;\n"
        plot += "       case 'plot_range_y':\n"
        plot += "         filterDetail.forEach((rangeObject, key) => {\n"
        plot += f"           tempData = JSON.parse(JSON.stringify(data_{self.lcl_UUID}));\n"
        plot += "           tempData.forEach((trace, index) => {\n"
        plot += "             let min = rangeObject.min;\n"
        plot += "             let max = rangeObject.max;\n"
        plot += f"             data_{self.lcl_UUID}[index]['y'] = trace['y'].filter((value) =>"
        plot += " value >= min && value <= max);\n"
        plot += f"             data_{self.lcl_UUID}[index]['x'] = trace['x'].filter((value, index) =>"
        plot += " trace['y'][index] >= min && trace['y'][index] <= max);\n"
        plot += "           });\n"
        plot += "         });\n"
        plot += "         break;\n"
        plot += "       case 'tag':\n"
        plot += "         filterDetail.forEach((hiddenTags, key) => {\n"
        plot += "           if (hiddenTags.min !== undefined) {\n"
        plot += f"             data_{self.lcl_UUID}.forEach((trace, index) => {{\n"
        plot += "               if (trace.tags[key] < hiddenTags.min || trace.tags[key] > hiddenTags.max) {\n"
        plot += "                 trace.visible = 'hidden';\n"
        plot += f"                 data_{self.lcl_UUID}[index]['x'] = [];\n"
        plot += f"                 data_{self.lcl_UUID}[index]['y'] = [];\n"
        plot += "               }\n"
        plot += "             });\n"
        plot += "           } else if (key === 'Other tags') {\n"
        plot += "             hiddenTags.forEach((hiddenTag) => {\n"
        plot += f"               data_{self.lcl_UUID}.forEach((trace, index) => {{\n"
        plot += "                 if (trace.visible !== 'hidden' && trace.tags[hiddenTag] === 'True') {\n"
        plot += "                   trace.visible = 'hidden';\n"
        plot += f"                   data_{self.lcl_UUID}[index]['x'] = [];\n"
        plot += f"                   data_{self.lcl_UUID}[index]['y'] = [];\n"
        plot += "                 }\n"
        plot += "               });\n"
        plot += "             });\n"
        plot += "           } else {\n"
        plot += f"             data_{self.lcl_UUID}.forEach((trace, index) => {{\n"
        plot += "               Object.entries(trace.tags).forEach(([tagKey,tagValue]) => {\n"
        plot += "                 if (tagValue === 'True') {\n"
        plot += "                   trace.tags[tagKey] = tagKey;\n"
        plot += "                 }\n"
        plot += "               });\n"
        plot += "               if (hiddenTags.includes(trace.tags[key])) {\n"
        plot += "                 trace.visible = 'hidden';\n"
        plot += f"                 data_{self.lcl_UUID}[index]['x'] = [];\n"
        plot += f"                 data_{self.lcl_UUID}[index]['y'] = [];\n"
        plot += "               }\n"
        plot += "             });\n"
        plot += "           }\n"
        plot += "         });\n"
        plot += "         break;\n"
        plot += "       case 'single-tag':\n"
        plot += "         filterDetail.forEach((tags, key) => {\n"
        plot += "           if (tags.length) {\n"
        plot += "             let shownTag = tags[0];\n"
        plot += f"             data_{self.lcl_UUID}.forEach((trace, index) => {{\n"
        plot += "               let tagIsDefined = trace.tags[key] !== undefined;\n"
        plot += "               if (!(tagIsDefined && trace.tags[key].includes(shownTag) ||"
        plot += "                   trace.tags[shownTag] === 'True')) {\n"
        plot += "                 trace.visible = 'hidden';\n"
        plot += f"                 data_{self.lcl_UUID}[index]['x'] = [];\n"
        plot += f"                 data_{self.lcl_UUID}[index]['y'] = [];\n"
        plot += "               }\n"
        plot += "             });\n"
        plot += "           }\n"
        plot += "         });\n"
        plot += "         break;\n"
        plot += "     }\n"
        plot += "   });\n"
        plot += f"   Plotly.redraw(pobj_{self.lcl_UUID});\n"
        plot += " });\n"

        plot += f" $(document).ready(function() {{ Plotly.Plots.resize(pobj_{self.lcl_UUID}); }});\n"
        plot += "</script>\n"

        s += payload + plot

        return s

    def render_table_as_table(self, data: dict, context: dict, ctx: dict) -> str:
        # The HTML being built
        s = ""

        # Get the number of rows/columns
        nrows, ncols = data['array'].shape
        # tags
        row_tags = self.get_row_tags(data, context)
        col_tags = self.get_column_tags(data, context)

        # if printing, the style will not be None
        is_printing_pdf = TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF
        added_column_to_mask_rowlbls = False

        col_labels = self.get_column_labels(data, context)
        row_labels = self.get_row_labels(data, context)

        # we add fillers so that we have column labels always and
        # the <thead> is rendered for all cases.
        if col_labels is None:
            # sometimes, if there's no column labels, the <thead> block is completely
            # ignored out of the generated DOM, outputting an incomplete HTML table.
            # so we add a 'filler' th to give a proper table.
            # This is now controlled by a property: table_default_col_labels
            table_default_col_labels = self.get_default(data, ctx, 'table_default_col_labels',
                                                        default=1, force_int=True)
            if table_default_col_labels == 1:
                col_labels = [f"Column-{i + 1}" for i in range(ncols)]

        has_row_labels = row_labels is not None
        if not has_row_labels:
            row_labels = [None] * nrows
        else:
            # only if col lbls is an existing valid list
            if isinstance(col_labels, list):
                # there are row labels giving us an extra column at the start
                # so prepend '' to the column labels for a dummy column label.
                col_labels.insert(0, '')
                added_column_to_mask_rowlbls = True

        # Because of iteration limitations in templates,
        # we compute a zip between row labels (or a list of None)
        # and numpy array rows
        ctx['array'] = list(zip(row_labels, data['array']))
        table_title = self.get_default(data, ctx, 'table_title')
        if table_title is None:
            table_title = self.get_default(data, ctx, 'title')

        # table cell conditional formatting rules
        cell_formatting = None
        formatting_rules = self.get_default(data, ctx, 'table_cond_format', default=None)
        if formatting_rules is not None:
            formatter = ConditionalFormattingHTMLStyle()
            # if there is a row label, we insert an extra entry in col_labels we need to skip
            trimmed_column_names = col_labels
            if col_labels and added_column_to_mask_rowlbls:
                if len(col_labels):
                    trimmed_column_names = col_labels[1:]
            cell_formatting = formatter.compute_style_array(data['array'], formatting_rules,
                                                            row_names=row_labels,
                                                            col_names=trimmed_column_names)
        # overall table styling
        table_styling = ''
        # table borders
        table_bordered = self.get_default(data, ctx, 'table_bordered', default=1, force_int=True)
        if table_bordered == 1:
            table_styling += 'table-bordered '

        table_wrap_content = self.get_default(data, ctx, 'table_wrap_content', default=0,
                                              force_int=True)
        if table_wrap_content == 1:
            table_styling += 'table-wrap '
        else:
            table_styling += 'nowrap '

        # table condensation(compact)
        table_condensed = self.get_default(data, ctx, 'table_condensed', default=0, force_int=True)
        if table_condensed == 1:
            table_styling += 'table-sm table-fit-head '
            # allow condensation in the body only if wrap is OFF, otherwise they'll conflict
            if table_wrap_content == 0:
                table_styling += 'table-fit-body '

        # add the table
        s += f'<table id="table_{self.lcl_UUID}" class="table table-hover {table_styling}' \
             f'display" style="width: 100%">\n'
        # other options
        paging_option = self.get_default(data, ctx, 'table_page', default=0, force_int=True)
        paging_menu = list()
        paging_menu.append(list())
        paging_menu.append(list())
        table_pagemenu = str(self.get_default(data, ctx, 'table_pagemenu', default=""))
        # if printing, no paging menu
        if is_printing_pdf:
            table_pagemenu = ""
            paging_option = 0
        table_pagemenu = table_pagemenu.replace('[', '').replace(']', '')
        for menu in table_pagemenu.split(','):
            try:
                iv = int(menu)
                if iv < 0:
                    paging_menu[0].append(-1)
                    paging_menu[1].append("All")
                elif iv > 0:
                    paging_menu[0].append(iv)
                    paging_menu[1].append(iv)
            except:
                pass

        scrollx_option = self.get_default(data, ctx, 'table_scrollx', default=1, force_int=True)
        scrolly_option = self.get_default(data, ctx, 'table_scrolly', default=0, force_int=True)
        # if printing, scrolling
        if is_printing_pdf:
            scrollx_option = 0
            scrolly_option = 0
        if table_title is not None:
            s += ' <caption><h5 style="word-wrap: normal;">{}</h5></caption>\n'.format(
                self.clean_label(table_title, allow_multiline=True))
        else:
            # so tables without titles don't look weird
            s += ' <br>\n'

        # if a column was added for row labels
        if col_labels:
            s += ' <thead>\n'
            s += '  <tr>\n'
            col_idx = -1 if added_column_to_mask_rowlbls else 0
            for label in col_labels:
                if label is not None:
                    col_label_format = None
                    if col_idx >= 0:
                        col_label_format = self.get_indexed_default(data, ctx, col_idx,
                                                                    'format_column', default='str')
                    if col_label_format:
                        label, _ = self.format_table_value(label.strip(), col_label_format,
                                                           context=ctx, item=self)

                s += '   <th'
                if col_idx >= 0:
                    tag = col_tags[col_idx] if col_tags else self.tags
                    if tag:
                        s += f' data-tags="{tag}"'
                s += f'>{label}</th>\n'
                col_idx += 1
        else:
            # if no col labels, add an empty thead to give a complete table.
            # with empty <th>s as well, then collapse it
            s += ' <thead style="visibility: collapse;">\n'
            s += '  <tr>\n'
            # if row labels form a column.
            col_idx = 0
            total_cols = ncols
            if has_row_labels:
                col_idx = -1
                total_cols += 1
            for _ in range(total_cols):
                s += '   <th'
                if col_idx >= 0:
                    tag = col_tags[col_idx] if col_tags else self.tags
                    if tag:
                        s += f' data-tags="{tag}"'
                s += '></th>\n'
                col_idx += 1
        s += '  </tr>\n'
        s += ' </thead>\n'

        s += ' <tbody>\n'
        nan_display = self.get_default(data, ctx, 'nan_display', default='NaN')
        row_idx = 0
        is_string = data['array'].dtype.kind in "U"
        is_float = data['array'].dtype.kind in "f"
        column_max = 0
        row_tags = self.get_row_tags(data, context, [])
        col_tags = self.get_column_tags(data, context, [])
        for lbl, row in ctx['array']:
            s += f'  <tr'
            tag = row_tags[row_idx] if row_tags else self.tags
            if tag:
                s += f' data-tags="{tag}"'
            s += f'>\n'

            if lbl is not None:
                row_label_format = self.get_indexed_default(data, ctx, row_idx, 'format_row',
                                                            default='str')
                lbl, dummy = self.format_table_value(lbl.strip(), row_label_format, context=ctx,
                                                     item=self)
                s += '   <th>{}</th>\n'.format(lbl)
                if row_idx == 0:
                    column_max += 1
            column = 0
            for i in row:
                if is_string:
                    number_format = self.get_indexed_default(data, ctx, column, 'format',
                                                             default='str')
                    str_rep, sort_rep = self.format_table_value(i.strip(), number_format,
                                                                context=ctx, item=self)
                    sort_rep = sort_rep.replace('"', '')
                elif is_float:
                    number_format = self.get_indexed_default(data, ctx, column, 'format',
                                                             default='scientific')
                    if numpy.isnan(i):
                        str_rep = nan_display
                        sort_rep = nan_display
                    else:
                        str_rep, sort_rep = format_value_general(i, number_format)
                else:
                    str_rep = f"Unknown:{data['array'].dtype.kind}"
                    sort_rep = "1"
                style_string = ""
                if cell_formatting is not None:
                    conditional_style = cell_formatting[row_idx, column]
                    if conditional_style is not None:
                        style_string = f'style="{conditional_style}"'
                s += f'   <td {style_string} data-order="{sort_rep.strip()}">{str_rep}</td>\n'
                column += 1
                if row_idx == 0:
                    column_max += 1
            s += '  </tr>\n'
            row_idx += 1
        s += ' </tbody>\n'
        s += '</table>\n'

        # opts = "'scrollX': true, 'ordering': false, 'searching': false, 'select': true, 'paging':  false, 'info': false"
        # opts = "'scrollY': '200px', 'scrollCollapse': true, 'pageLength': 50, 'lengthMenu': [10, 20, 50, -1], [10, 20, 50, 'All']]"
        search_option = self.get_default(data, ctx, 'table_search', default=0, force_int=True)
        if is_printing_pdf:
            search_option = 0
        # get the sorting option ['none', 'all', 'data'] '1'=data  For the present, 'data' == 'all'
        sort_option = ctx.get('table_sort', data.get('table_sort', 'all'))
        sort_option = sort_option in ['all', 'data', '1']
        if is_printing_pdf:
            sort_option = False

        opts = '"columnDefs": ['
        for col in range(column_max):
            align = self.get_indexed_default(data, ctx, col, 'align_column', default='right')
            opts += '{{"className": "{}", "targets": {}, "cellType": "{}" }}, '.format(
                self.pick_alignment(align, "right"),
                col,
                "th" if has_row_labels and col == 0 else "td"
            )
        opts += '],'
        opts += '"info": false,'
        opts += '"orderClasses": false,'

        if search_option == 0:
            opts += '"searching": false,'

        if not sort_option:
            opts += '"ordering": false,'

        if scrollx_option != 0:
            opts += '"scrollX": true,'

        # disable pagination if 0.
        # by default, its enabled.
        if paging_option == 0:
            opts += '"paging": false,'
        # if the option is a bigger integer,
        # we take that as the initial page length.
        elif paging_option != 1:
            opts += '"pageLength": {},'.format(paging_option)

        if len(paging_menu[0]) > 0:
            opts += '"lengthMenu": {},'.format(str(paging_menu))
        else:
            # add the default menu setup only if paging is not disabled.
            # else, adding this will enable paging implicitly.
            if paging_option != 0:
                opts += '"lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],'

        # enable vertical scrolling and collapse any empty area
        if scrolly_option > 0:
            opts += '"scrollY": "{}pt", "scrollCollapse": true,'.format(scrolly_option)

        # avoid datatables when printing PDF.
        if not is_printing_pdf:
            s += render_to_string('data/item_layouts/table_filter_template.html',
                                  {'uuid': self.lcl_UUID, 'opts': opts})

        return s

    def render_tree(self, context, ctx):
        s = ""
        self.tree_count = 1
        # Note: the ctx contains template properties.  Allow properties to be set on the root item as well
        root = safe_unpickle(self.payloaddata)
        root_item = dict()
        if len(root):
            root_item = root[0]

        # get justification
        if 'item_justification' in root_item:
            self.item_justification = root_item['item_justification']
        # get the property directed state settings
        initial_state = ctx.get('tree_initial_state', root_item.get('tree_initial_state'))
        # expand/collapse turned off by default.
        tree_global_toggle = int(ctx.get('tree_global_toggle', root_item.get('tree_global_toggle', '0')))
        # apply tree entity conditional formatting rules
        formatting_rules = ctx.get('tree_cond_format', root_item.get('tree_cond_format', ''))
        if formatting_rules:
            formatter = TreeConditionalFormattingHTMLStyle()
            # This formatter embeds the formatting directly into the tree, so call it here
            for root_entity in root:
                _ = formatter.compute_style_array(root_entity, formatting_rules)
        # Start building the HTML
        tree_id = 'treeroot_' + self.lcl_UUID
        # The complete card interface uses more space than is desired, we
        # keep the card-header formatting for the radio buttons as it colors nicely,
        # but drop the 'card' divs to preserve space
        # s += '\n<div class="card">\n'
        if TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF:
            # if "printing" PDF, expand the tree and ignore item specific expansion options
            initial_state = 'expanded'
            tree_global_toggle = 0  # hide global toggles

        # tree condensation(compact)
        tree_condensed = int(ctx.get('tree_condensed', root_item.get('tree_condensed', 0)))

        if tree_global_toggle == 1:
            btn_class = "btn btn-outline-secondary"
            if tree_condensed:
                btn_class += " btn-sm"
            s += f'<div class="card-header">\n' \
                 f'  <span class="btn-group" role="group">\n' \
                 f'      <button type="button" class="tree-expand-all {btn_class}" \n' \
                 f'          data-target-tree="{tree_id}"><i class="fas fa-plus"></i>\n' \
                 f'      <button type="button" class="tree-collapse-all {btn_class}" \n' \
                 f'          data-target-tree="{tree_id}"><i class="fas fa-minus"></i>\n' \
                 f'  </span>\n' \
                 f'</div>\n'

        # See 'card' div comments above
        # s += '<div class="card-body">'

        # make the tree responsive for large numbers of columns
        s += '<div style="display:block;overflow-x:auto;white-space:nowrap;">'
        tree_styling = ''
        # tree borders
        tree_bordered = int(ctx.get('tree_bordered', root_item.get('tree_bordered', 1)))
        if tree_bordered == 1:
            tree_styling += 'table-bordered '
        # tighten up the tree if condensed mode selected
        if tree_condensed == 1:
            tree_styling += 'table-sm tree-fit '

        s += f"<table id='{tree_id}' class='table tree {tree_styling}" \
             f"table-striped' style='margin:0;border:0;padding:0;'>\n"
        # insert the actual table from the tree contents
        s += self.add_tree(root, tree_id, initial_state, 0, ctx)
        s += "</table>\n"
        s += "</div>\n"
        return s

    # should there be a column justification property?
    def add_tree(self, tree, tree_id, initial_state, parent, ctx, **kwargs):

        def get_formatted_value(input_val):
            formatted_val = str(input_val)  # handles a lot of cases...
            # formatting for the types: [float, int, datetime.datetime, str, bool, uuid.UUID, None]
            if input_val is None:
                formatted_val = ""
            elif type(input_val) == float:
                fmt = str(ctx.get('tree_format_float', 'floatdot2'))
                formatted_val = format_value_general(input_val, fmt)[0]
            elif type(input_val) == bool:
                fmt = str(ctx.get('tree_format_bool', 'True#False'))
                fmt = fmt.split('#')
                while len(fmt) < 2:
                    fmt.append("?")
                if input_val:
                    formatted_val = str(fmt[0])
                else:
                    formatted_val = str(fmt[1])
            elif type(input_val) == datetime.datetime:
                fmt = str(ctx.get('tree_format_date', 'date_44'))
                formatted_val = format_value_general(input_val, fmt)[0]
            elif type(input_val) == uuid.UUID:
                guid = None
                try:
                    fmt = str(ctx.get('tree_format_guid', 'link'))
                    item = Item.objects.get(guid__exact=str(input_val))
                    guid = item.guid
                    if fmt == 'link':
                        url = item.get_payload_url()
                        formatted_val = '<a href="{}">{}</a>'.format(url, item.name)
                    else:
                        # check perms before rendering.
                        # Just viewing a link to it don't need perms.
                        check_obj_perm('view', ctx['request'].user, item, raise_exception=True)
                        # render
                        formatted_val = item.render(ctx)
                except PermissionDenied:
                    formatted_val = '<p class="text-danger">' \
                                    '   You do not have permissions to view this item.' \
                                    '</p>'
                except Item.DoesNotExist:
                    formatted_val = "Unknown GUID: {}".format(str(input_val))
                except Exception as e:
                    formatted_val = get_render_error_html(e, target='item', guid=guid)

            if ('{{' in formatted_val) and ('}}' in formatted_val):
                formatted_val = TemplateEngine.context_expansion(formatted_val, ctx, item=self)

            return formatted_val

        html = ""
        new_kwargs = {}
        for node in tree:
            head = ""
            foot = ""
            row_style = ""
            if node.get('header', False):
                head = "<strong>"
                foot = "</strong>"
                row_style = "border-bottom:4px solid LightGray;"

            # hide self?
            hide_self = kwargs.get('hide_self', False)
            if hide_self:
                row_style += 'display: none;'

            # set state
            collapse_children = False
            # prioritize global state
            if initial_state is not None:
                collapse_children = initial_state == "collapsed"
            else:
                # use recursive state from parent if available
                if "collapse_recursive" in kwargs:
                    collapse_children = kwargs["collapse_recursive"]
                elif "expand_recursive" in kwargs:
                    collapse_children = not kwargs["expand_recursive"]
                elif "state" in node:  # else use own state
                    state = node["state"]
                    if state in ["expand", "expanded", "expandRecursive"]:
                        collapse_children = False
                        if state == "expandRecursive":
                            new_kwargs["expand_recursive"] = True
                    elif state in ["collapse", "collapsed", "collapseRecursive"]:
                        collapse_children = True
                        if state == "collapseRecursive":
                            new_kwargs["collapse_recursive"] = True
            # set state for descendant
            new_kwargs['hide_self'] = collapse_children

            node_id = "treenode_" + self.lcl_UUID + "-" + str(self.tree_count)
            children = node.get("children")
            toggle_class = ''
            target_data = ''
            state_class = ''
            if children:
                node_class = 'tree-parent'
                toggle_icon = 'fa-minus'
                state_class = 'tree-expanded'
                if collapse_children:
                    toggle_icon = 'fa-plus'
                    state_class = 'tree-collapsed'
                toggle_class = f'sub-tree-toggle fas {toggle_icon} mr-1'
                target_data = f'data-target-node="{node_id}"'
            else:
                node_class = 'tree-leaf'

            # add row
            html += f"<tr id='{node_id}' data-parent='{parent}' data-tree='{tree_id}'" \
                    f" class='tree-row {node_class} {state_class}' style='{row_style}'>\n"

            # Apply macro expansion to the key column if needed
            name_value = node.get('name', '')
            if ('{{' in name_value) and ('}}' in name_value):
                name_value = TemplateEngine.context_expansion(name_value, ctx, item=self)

            # repeat indent based on depth
            depth = kwargs.get("depth", 0)
            indent = f'<span class="treegrid-indent"></span>' * depth

            # build key
            html += f"<td>" \
                    f"{indent}<span class='treegrid-indent {toggle_class}' {target_data} style='cursor:pointer'>" \
                    f"</span>" \
                    f"{head}{name_value}{foot}</td>"
            # format the value (if any)
            value = node.get('value', None)
            # build value w/ support for multi-valued tree nodes
            if isinstance(value, list):
                # get any html styling
                html_styles = node.get('htmlstyle', [None] * len(value))
                for val, style in zip(value, html_styles):
                    if style is not None:
                        style = 'style="{}"'.format(style)
                    else:
                        style = ''
                    html += f"<td {style}>{head}{get_formatted_value(val)}{foot}</td>"
            else:
                # get any html styling
                style = node.get('htmlstyle', [None])[0]
                if style is not None:
                    style = 'style="{}"'.format(style)
                else:
                    style = ''
                html += f"<td {style}>{head}{get_formatted_value(value)}{foot}</td>"
            # close row
            html += "</tr>\n"
            # if we have children, recurse into them...
            self.tree_count += 1
            if children:
                new_kwargs["depth"] = depth + 1
                html += self.add_tree(node['children'], tree_id, initial_state, node_id, ctx, **new_kwargs)
        return html


class ItemCategoryRelation(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    category = models.ForeignKey(ItemCategory, on_delete=models.CASCADE)
    date = models.DateTimeField(verbose_name="timestamp", default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['item', 'category'], name='item_category_unique_together')
        ]


###############################
# Permission handling models #

class ItemCategoryUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(ItemCategory, on_delete=models.CASCADE)

    class Meta(UserObjectPermissionBase.Meta):
        abstract = False


class ItemCategoryGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(ItemCategory, on_delete=models.CASCADE)

    class Meta(GroupObjectPermissionBase.Meta):
        abstract = False


###############################
# Do a formal filtering operation using the query string on the src.
# src can be a list of objects (assumed to be of the same type) or a
# QuerySet() models.query.QuerySet.  If the latter, the system will use
# Q() models.Q objects to append filtering to the set and return the
# set (or a copy of the set)
#
#  Note: a query will be a string of the form:
#  {X}|{field_name}|{comparison}|{value{,value{,value}}...};{repeat...}
#  {X} can be 'A'=and or 'O'=or operation
#  {field_name} can be: i_name,i_src,i_date,i_tags,i_type,
#                       s_app,s_ver,s_date,s_tags,s_host,s_plat,s_guid,
#                       d_name,s_dir,d_fmt,d_tags,d_guid,
#  {comparison} can be: cont,ncont,eq,neq,sw,ew,gte,gt,lte,lt,guid
#  {value} may be one or more items...
#
# Simple container with a few helpful methods...
class QueryStanza:
    comp_values = {
        'cont': ['icontains', False],
        'ncont': ['icontains', True],
        'eq': ['iexact', False],
        'neq': ['iexact', True],
        'sw': ['istartswith', False],
        'ew': ['iendswith', False],
        'gt': ['gt', False],
        'gte': ['gte', False],
        'lt': ['lt', False],
        'lte': ['lte', False],
        'guid': ['exact', False],
    }

    # query_field: ['orm_field', 'orm_field_datatype']
    field_filters = {
        'i_date': ['date', 'd'],
        'i_name': ['name', 's'],
        'i_src': ['source', 's'],
        'i_type': ['type', 'l'],
        'i_tags': ['tags', 't'],
        'i_seq': ['sequence', 'n'],
        'i_guid': ['guid', 's'],
        'ic_guid': ['guid', 's'],
        'ic_date': ['date', 'd'],
        'ic_name': ['name', 's'],
        's_date': ['date', 'd'],
        's_plat': ['platform', 's'],
        's_host': ['hostname', 's'],
        's_app': ['application', 's'],
        's_ver': ['version', 's'],
        's_tags': ['tags', 't'],
        's_guid': ['guid', 's'],
        'd_name': ['filename', 's'],
        'd_dir': ['dirname', 's'],
        'd_fmt': ['format', 's'],
        'd_tags': ['tags', 't'],
        'd_guid': ['guid', 's'],
        't_name': ['name', 's'],
        't_filt': ['item_filter', 's'],
        't_types': ['report_type', 's'],
        't_mstr_chk': ['master', 'b'],
        't_date': ['date', 'd'],
        't_tags': ['tags', 't'],
        't_guid': ['guid', 's'],
    }

    def __init__(self, link, field, comparison, value, model=None):
        self._link = link
        self._field = field
        self._comp = comparison
        self._value = value
        self._model = model

    def __str__(self):
        return "QueryStanza: link:" + self._link + " field:" + self._field + " comp:" + self._comp + " value:" + str(
            self._value)

    def get_comparison(self):
        ctmp = copy.deepcopy(self.comp_values.get(self._comp, ['iexact', False]))
        return ctmp

    def get_field_model(self):
        if self._field.startswith('ic'):
            return ItemCategory
        if self._field.startswith('i'):
            return Item
        if self._field.startswith('d'):
            return Dataset
        if self._field.startswith('s'):
            return Session
        if self._field.startswith('t'):
            return Template
        return None

    def get_bool(self):
        # only look at the first item...
        return not self._value[0] in [False, 0, 'off', 'Off', 'False', 'false', '0']

    def get_Q(self):
        # get the connector
        link = Q.OR
        if self._link == 'A':
            link = Q.AND
        # build the local query Q object
        q_obj = Q()
        comparison = self.get_comparison()
        field_filter = self.field_filters.get(self._field, None)
        if field_filter and len(field_filter) >= 2:
            # field__{comp} : value(s)
            if field_filter[1] == 'l':
                # special case for the 'type' list
                # eg: type__in=['table']
                comparison[0] = 'in'
                kwargs = {field_filter[0] + '__' + comparison[0]: self._value}
                q_obj = Q(**kwargs)
            elif field_filter[1] == 'b':
                # Boolean query type (0/1/on/off/true/false strings)
                b = self.get_bool()  # returns True or False
                # the boolean field does not use `comparison`
                # eg: master=True
                kwargs = {field_filter[0]: b}
                q_obj = Q(**kwargs)
            else:
                # bring in the list of values...
                for v in self._value:
                    # dates in queries have to be timezone-aware
                    if field_filter[0].lower() == "date":
                        v = get_aware_datetime(v)

                    kwargs = {field_filter[0] + '__' + comparison[0]: v}
                    # multiple value lookups will be chained by OR.
                    q_obj.add(Q(**kwargs), Q.OR)
            # invert the test with the NOT operation
            # comparison[1] tells if we should negate it or not.
            if comparison[1]:
                q_obj = ~q_obj
        return q_obj, link

    def eval_stanza(self, obj, bGlobal, model):
        bLocal = True
        # test this stanza vs obj
        comp_values = self._value
        ctmp = self.get_comparison()
        tmp = self.field_filters.get(self._field, None)
        if tmp:
            # this search might be on a different model
            sm = self.get_field_model()
            if sm != model:
                # get the real target object
                if sm == Session:
                    target_obj = obj.session
                elif sm == Dataset:
                    target_obj = obj.dataset
                else:
                    # really an error case (someone would need to do a Template search on a data item)
                    target_obj = obj
                # get the (indirect) value to compare to
                obj_value = getattr(target_obj, tmp[0], '')
                if type(obj_value) == uuid.UUID:
                    obj_value = str(obj_value)
            else:
                # direct comparison
                obj_value = getattr(obj, tmp[0], '')
                if type(obj_value) == uuid.UUID:
                    obj_value = str(obj_value)
                if tmp[1] == 'n':
                    # handle the sequence number as a padded string
                    try:
                        obj_value = "{:08d}".format(int(obj_value))
                    except:
                        obj_value = "0"
                    working = list()
                    for tmpv in comp_values:
                        try:
                            tmps = "{:08d}".format(int(tmpv))
                            working.append(tmps)
                        except:
                            working.append("0")
                    comp_values = working
                elif tmp[1] == 'd':
                    tmp = comp_values[0]
                    if '+' not in tmp:
                        tmp += '+00:00'
                    comp_values = [parser.parse(tmp)]
                elif ctmp[0][0] == 'i':
                    # we may need to map to same case...
                    obj_value = obj_value.lower()
                    comp_values = [x.lower() for x in comp_values]
            # compare the value to self._value items...
            # two special cases:
            # first the GUID in the GUID list
            if tmp[1] == 'g':
                bLocal = obj_value in comp_values
            # second is the object option in the selected list (e.g. types)
            elif tmp[1] == 'l':
                bLocal = obj_value in comp_values
            # the generic options
            elif ctmp[0].endswith('contains'):
                bLocal = False
                if len(obj_value):
                    for v in comp_values:
                        if v in obj_value:
                            bLocal = True
            elif ctmp[0].endswith('exact'):
                bLocal = obj_value in comp_values
            elif ctmp[0].endswith('startswith'):
                bLocal = False
                for v in comp_values:
                    if obj_value.startswith(v):
                        bLocal = True
            elif ctmp[0].endswith('endswith'):
                bLocal = False
                for v in comp_values:
                    if obj_value.endswith(v):
                        bLocal = True
            elif ctmp[0].endswith('gt'):
                bLocal = False
                for v in comp_values:
                    if obj_value > v:
                        bLocal = True
            elif ctmp[0].endswith('gte'):
                bLocal = False
                for v in comp_values:
                    if obj_value >= v:
                        bLocal = True
            elif ctmp[0].endswith('lt'):
                bLocal = False
                for v in comp_values:
                    if obj_value < v:
                        bLocal = True
            elif ctmp[0].endswith('lte'):
                bLocal = False
                for v in comp_values:
                    if obj_value <= v:
                        bLocal = True
            # invert the test if needed...
            if ctmp[1]:
                bLocal = not bLocal
        # composite the stanza with the external value
        if self._link == 'A':
            return bGlobal and bLocal
        return bGlobal or bLocal


# basic entry point
# parse the query into stanzas and call the specialized handlers
def object_filter(query, queryset_src, model=None):
    # convert the query string into a list of QueryStanza objects
    q_stanzas = []
    # example query: A|i_tags|cont|chart=pie,chart=bar;A|i_name|ncont|Total;
    terms = filter(None, query.split(';'))  # pylint: disable=W1639
    for term in terms:
        q_stanza = term.split('|')
        # parse out the values into a list
        values = filter(None, q_stanza[3].split(','))  # pylint: disable=W1639
        # and strip leading/trailing spaces
        values = list(map(str.strip, values))
        if values:
            q_stanzas.append(QueryStanza(q_stanza[0], q_stanza[1], q_stanza[2], values, model=model))
    # perhaps there is nothing to do?
    # return the entire QuerySet if no Stanzas are available.
    if not q_stanzas:
        return queryset_src
    # we might be filtering a QuerySet or a List(like) object
    if isinstance(queryset_src, QuerySet):
        return object_filter_QuerySet(q_stanzas, queryset_src, model)
    else:
        return object_filter_List(q_stanzas, queryset_src, model)


# augmenting a QuerySet with another filter
def object_filter_QuerySet(q_stanzas, queryset, model=None):
    # Start with an empty query.
    main_q_obj = Q()
    # add to it with each filter stanza
    for q_stanza in q_stanzas:
        # build the basic Q object
        stanza_q_obj, link = q_stanza.get_Q()
        # this search might be on a different model
        # i.e. model of the object(s) I'm trying to search
        # might be different from the model of the field
        # I'm using to search.
        field_model = q_stanza.get_field_model()
        if field_model != model:
            # search the other model for items
            if field_model == Session:
                # todo: why is link not used in here? AND is hardcoded..what if link is OR?
                main_q_obj.add(Q(session__in=Session.objects.filter(stanza_q_obj)), Q.AND)
            elif field_model == Template:
                main_q_obj.add(Q(parent__in=Template.objects.filter(stanza_q_obj)), Q.AND)
            else:
                main_q_obj.add(Q(dataset__in=Dataset.objects.filter(stanza_q_obj)), Q.AND)
        else:
            main_q_obj.add(stanza_q_obj, link)

    return queryset.filter(main_q_obj)


# apply a set of filter stanzas to a list of objects
def object_filter_List(q_stanzas, obj_list, model=None):
    out = []
    # For each object in the list
    for obj in obj_list:
        # can we keep it?
        bKeep = True
        for q_stanza in q_stanzas:
            bKeep = q_stanza.eval_stanza(obj, bKeep, model)
        if bKeep:
            out.append(obj)
    return out
