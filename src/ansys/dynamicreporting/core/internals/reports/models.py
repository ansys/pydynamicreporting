#
# *************************************************************
#  Copyright 2017-2023 ANSYS, Inc.
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

import uuid

from django.db import models
from django.db.models import QuerySet
from django.middleware import csrf
from django.urls import reverse
from django.utils.timezone import now

from .engine import TemplateEngine
from .managers import TemplateManager


# Create your models here.
# Notes:  
# 1) datetime.now(pytz.utc) to get a proper date w/timezone
# 2) we define get_absolute_url methods, but in a template, the following also works (for an item):
# {% url 'data_session_detail' item.session.guid %} instead of
# {{ item.session.get_absolute_url }}

# definition of a report template
#
# There are a number of "types" of core templates: iterator, layout, etc
# The user can create instances of these types and parameterize them via 
# JSON objects stored in Template.params.  Some template are "TopLevel" and
# thus user visible.  These have Template.master set True.
class Template(models.Model):
    guid = models.UUIDField(verbose_name="uid", primary_key=True, default=uuid.uuid1)
    # core session information
    tags = models.CharField(verbose_name="userdata", max_length=256, blank=True, db_index=True)
    date = models.DateTimeField(verbose_name="timestamp", default=now, db_index=True)
    name = models.CharField(verbose_name="report name", max_length=255, blank=True, db_index=True)
    report_type = models.CharField(verbose_name="report type", max_length=50, blank=True, db_index=True)
    params = models.CharField(verbose_name="parameters", max_length=4096, blank=True)
    item_filter = models.CharField(verbose_name="filter", max_length=1024, blank=True)
    master = models.BooleanField(verbose_name="master template", default=True, db_index=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)
    children_order = models.TextField(verbose_name="children order", default="", blank=True)

    objects = models.Manager()  # The default manager.
    filtered_objects = TemplateManager()

    def get_children_count(self):
        return self.children.count()

    # Note: a guid is 36 chars (37 with , separator): 1024 => ~27 children
    # gets the ordered children as model objects.
    def get_ordered_children(self, guids_only=False):
        sorted_guids = self.children_order.lower().split(',')
        children = list(Template.objects.filter(parent=self))
        # return the children based on the order of guids in children_order
        ordered_children = []
        for guid in sorted_guids:
            for idx, child in enumerate(children):
                if guid == str(child.guid).lower():
                    if guids_only:
                        ordered_children.append(child.guid)
                    else:
                        ordered_children.append(child)
                    break
        return ordered_children

    # Template is essentially an ORM wrapper.  It also serves as a
    # factory to create the objects that actually do the report 
    # generation work.  This method constructs that object and
    # objects for its children...
    def get_engine(self):
        # create the object
        engine = TemplateEngine.factory(self)
        for child in self.get_ordered_children():
            # for each child template, get the engine
            child_engine = child.get_engine()
            # add child engine to the parent engine
            engine.add_child(child_engine)
            # set the parent
            child_engine.set_parent(engine)
        return engine

    def get_absolute_url(self):
        return reverse('reports_report_detail', kwargs={'guid': self.guid})

    def get_display_url(self, query='', context=None):
        if context is None:
            context = {}
        request = context.get('request', None)
        tmp = reverse('reports_report_display')
        tmp += "?view={}".format(self.guid)
        tmp += "&query={}".format(query.replace("|", "%7C").replace(";", "%3B"))
        tmp += "&usemenus={}".format(context.get('usemenus', "on"))
        tmp += "&dpi={}".format(context.get('dpi', "96."))
        tmp += "&pwidth={}".format(context.get('pwidth', "10.5"))
        if request is not None:
            tmp += "&csrfmiddlewaretoken={}".format(csrf.get_token(request))
        return tmp

    def __str__(self):
        return "%s (%s:%s)" % (self.name, self.report_type, str(self.guid))

    # apply this template object's item filter to a list of input items
    def filter_items(self, items):
        if len(self.item_filter) == 0:
            return items
        from ..data.models import object_filter, Item
        return object_filter(self.item_filter, items, model=Item)

    @classmethod
    def find(cls, request, reverse=0, sort_tag="date"):
        from ..data.models import object_filter
        # start a query
        queryset = Template.objects.all()
        if request is not None:
            # special case of an explicit GUID
            t_guid = request.GET.get('t_guid', None)
            if t_guid is not None:
                kwargs = {'guid__exact': t_guid}
                queryset = queryset.filter(**kwargs)
            else:
                queryset = object_filter(request.GET.get('query', ''), queryset, model=Template)

        # pick the sort (we can only sort QuerySets for now)
        if isinstance(queryset, QuerySet):
            if reverse:
                sort_tag = "-" + sort_tag
            return queryset.order_by(sort_tag)

        return queryset

    @classmethod
    def find_guid(cls, guid):
        try:
            report = Template.objects.get(guid__exact=guid)
        except Template.DoesNotExist:
            return None
        return report
