#
# *************************************************************
#  Copyright 2019-2023 ANSYS, Inc.
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
#
import datetime
import fnmatch
import shlex
from dateutil import parser

from django.utils import timezone
from dateutil.tz import tzutc
from django import template

from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe


# base date/time for float representation of dates
time_base = datetime.datetime(1970, 1, 1, 0, 0, tzinfo=tzutc())

register = template.Library()
#
#  Custom filters that can be used to format various fields
#


def generic_comp(in_value, arg, numeric):
    """Generic comparison filter

    Implement numeric_comp and lexical_comp based on the numeric arg.

    """
    value = str(in_value)
    if numeric:
        # convert the input value into a float (handles both in and float inputs)
        try:
            value = float(value)
        except ValueError:
            return f"Bad numeric_comp conversion: {in_value}"

    args = arg.split(",")
    if len(args) != 4:
        return f"Invalid comparison args: {arg}"
    cmpval = args[0]
    if numeric:
        # convert the comparison value into a float (handles both in and float inputs)
        try:
            cmpval = float(cmpval)
        except ValueError:
            return f"Bad numeric_comp conversion: {args[0]}"

    # Assume equality and override with lt or gt comparison
    out = args[2]
    if value < cmpval:
        out = args[1]
    elif value > cmpval:
        out = args[3]
    # '_' is shorthand for the input value unchanged.
    if out == "_":
        return in_value
    return out


@register.filter(name='numeric_comp')
def numeric_comp(in_value, arg):
    """Numeric comparison filter

    The filer looks like:  |numeric_comp:"cmpval,lt,eq,gt".  The value
    is first converted to a float and then compared to cmpval converted
    into a float.  The return value will be one of the strings 'lt', 'eq',
    'gt' based on the comparison.  For example:  |numeric_comp:"1.0,low,ok,high"
    will return the string "low", "ok" or "high".  An output field of '_'
    will be replaced by the original input value.
    If the conversion fails, an error message will be returned.

    """
    return generic_comp(in_value, arg, True)


@register.filter(name='lexical_comp')
def lexical_comp(in_value, arg):
    """Lexical comparison filter

    The filer looks like:  |numeric_comp:"lexical_comp,lt,eq,gt".  The value
    is first converted to a string and then compared to cmpval.
    The return value will be one of the strings 'lt', 'eq',
    'gt' based on the comparison.  For example:  |lexical_comp:"Hello,low,ok,high"
    will return the string "low", "ok" or "high" based on the lexical comparison between
    'in_value' and 'Hello".  An output field of '_' will be replaced by the original input value.
    If the conversion fails, an error message will be returned.

    """
    return generic_comp(in_value, arg, False)


@register.filter(name='sprintf')
def sprintf(value, arg):
    """Custom wrapper around Python % operator

    Enable the filter:  |sprintf:"fmtstr" where "fmtstr" is a
    legal Python % formatting string.  For example:  2.3|sprintf:"%0.3f"
    If there is not a 's' character in fmtstr, then the value is first
    converted to a float before the operation is performed.

    """
    if 's' not in arg:
        try:
            value = float(value)
        except ValueError:
            return value
    value = arg % (value)
    return value


@register.filter(name='simple_sprintf')
def simple_sprintf(value, arg):
    return format_sprintf(value, arg)


# {{date_string|text_date:"strftstring"}}
@register.filter(name='text_date')
def text_date(value, arg):
    try:
        d = parser.parse(str(value))
        value = d.strftime(arg)
    except:
        pass
    return value


# Note: nexus_anchor and nexus_link have been renamed and will be documented
# as report_anchor and report_link.  They are retained for backward compatibility.

# {{value|nexus_anchor}}
@register.filter(is_safe=True)
@stringfilter
def nexus_anchor(value):
    # Use a 0.5em offset to put a little spacing between the browser top and the anchor
    style = 'position:relative;top:-0.5em;'
    return mark_safe('<a class="nexus-anchor" style="{}" id="{}"></a>'.format(style, value))


# {{value|nexus_link:"text"}}
@register.filter(is_safe=True)
@stringfilter
def nexus_link(value, arg):
    return mark_safe('<a class="nexus-link" href="#{}">{}</a>'.format(value, arg))


# {{value|report_anchor}}
@register.filter(is_safe=True)
@stringfilter
def report_anchor(value):
    # Use a 0.5em offset to put a little spacing between the browser top and the anchor
    style = 'position:relative;top:-0.5em;'
    return mark_safe('<a class="nexus-anchor" style="{}" id="{}"></a>'.format(style, value))


# {{value|report_link:"text"}}
@register.filter(is_safe=True)
@stringfilter
def report_link(value, arg):
    return mark_safe('<a class="nexus-link" href="#{}">{}</a>'.format(value, arg))


def convert_date_format_string(fmt):
    df = (fmt + "00")[5]
    tf = (fmt + "00")[6]
    s_fmt = ""
    if df == '0':
        s_fmt += "%Y-%m-%d "
    elif df == '1':
        s_fmt += "%b %d, %Y "
    elif df == '2':
        s_fmt += "%m/%d/%Y "
    elif df == '3':
        s_fmt += "%d %b %Y "
    elif df == '4':
        s_fmt += "%x "
    if tf == '0':
        s_fmt += "%H:%M:%S"
    elif tf == '1':
        s_fmt += "%I:%M%p"
    elif tf == '2':
        s_fmt += "%H:%M:%S.%f"
    elif tf == '3':
        s_fmt = '%c'
    elif tf == '4':
        s_fmt += '%X'
    return s_fmt.strip()


# For the date_XY format:
#   X Values:
#       '_' do not include the date.
#       0: 2017-01-06
#       1: Jan 1, 2017
#       2: 01/06/2017
#       3: 1 Jan 2017
#       4: locale specific display of date
#
#   Y Values:
#       '_' do not include the time.
#       0: 13:20:00
#       1: 1:20PM
#       2: 13:20:00.000000
#       3: Locale specific display of date & time
#       4: Locale specific display of time
#
# Convert the value 'v' into a string using the format 'fmt'.
# The function returns two values, the formatted text and a
# version of the text to be used while sorting.
def format_value_general(v, in_fmt):
    fmt = in_fmt.strip()
    if fmt == 'str':
        return str(v), str(v)

    if fmt.startswith('date_'):
        s_fmt = convert_date_format_string(fmt)
        # if the value is a number, interpret it as seconds since the time_base
        try:
            seconds = float(v)
            d = time_base + datetime.timedelta(seconds=seconds)
        except:
            # try to parse the value as a date/time value
            try:
                d = parser.parse(str(v))
                # No timezone, assume server timezone
                if d.tzinfo is None:
                    d = timezone.make_aware(d, timezone=timezone.get_current_timezone())
            except:
                d = time_base
        s = d.strftime(s_fmt)
        return s, "%40.20f" % (d - time_base).total_seconds()

    try:
        value = float(v)
    except:
        return str(v), str(v)

    if fmt == 'scientific':
        fmt = "%e"
    elif fmt.startswith('scientific'):
        fmt = "%0." + fmt[10] + "e"
    elif fmt.startswith('sigfigs'):
        fmt = "%0." + fmt[7] + "g"
    elif fmt.startswith('floatdot'):
        fmt = "%0." + fmt[8] + "f"
    else:
        fmt = "%g"
    return fmt % value, "%40.20f" % value


def convert_datelist_to_plotly_datelist(arr):
    # Currently, plotly does not allow timezones and is limited to the format
    # yyyy-mm-dd HH:MM:SS.ssssss
    a = list()
    for t in arr:
        d = None
        try:
            # Try float seconds first...
            seconds = float(t)
            d = time_base + datetime.timedelta(seconds=seconds)
        except:
            try:
                # parse string next
                d = parser.parse(str(t))
            except:
                pass
        if d is None:
            a.append(t)
        else:
            v = d.replace(tzinfo=None).isoformat()
            a.append(v.replace("T", " "))
    return a


def format_sprintf(v, fmt):
    try:
        v = float(v)
    except ValueError:
        return v
    if fmt == 'scientific':
        fmt = "%e"
    elif fmt.startswith('scientific'):
        fmt = "%0." + fmt[10] + "e"
    elif fmt.startswith('sigfigs'):
        fmt = "%." + fmt[7] + "g"
    elif fmt.startswith('floatdot'):
        fmt = "%0." + fmt[8] + "f"
    else:
        fmt = "%g"
    return fmt % v


def format_plotly(fmt):
    if fmt == 'scientific':
        fmt = ".2e"
    elif fmt.startswith('scientific'):
        fmt = "0." + fmt[10] + "e"
    elif fmt.startswith('sigfigs'):
        fmt = "0." + fmt[7] + "g"
    elif fmt.startswith('floatdot'):
        fmt = "." + fmt[8] + "f"
    elif fmt.startswith('date_'):
        fmt = convert_date_format_string(fmt)
    elif fmt == "natural":
        fmt = ""
    else:
        fmt = ""
    return fmt


#
#  Allow a request to be formatted into a query string with replacement:
#     {% url 'view_name' %}?{% query_transform request a=5 b=6 %}
#
@register.simple_tag
def query_transform(request, **kwargs):
    updated = request.GET.copy()
    for k, v in kwargs.items():
        if v == '___':
            if k in updated:
                del updated[k]
        else:
            updated[k] = v
    return updated.urlencode()


# convert '/' macros into 'Z' macros
def convert_macro_slashes(s):
    s = s.replace("{{i/", "{{")
    # Note: a '/' in a macro name is illegal, we use 'Z' instead
    s = s.replace("{{if/", "{{ifZ")
    s = s.replace("{{s/", "{{sZ")
    s = s.replace("{{sf/", "{{sfZ")
    s = s.replace("{{d/", "{{dZ")
    s = s.replace("{{df/", "{{dfZ")
    s = s.replace("{{v/", "{{vZ")
    return s


# Walk the string and expand {{}} macros with values in context
def expand_string_context(s, context, wildcard=None):
    if isinstance(s, str):
        pos = s.find("{{")
        while pos >= 0:
            try:
                pos2 = s[pos:].find("}}")
                if pos2 < 0:
                    break
                key = s[pos:pos + pos2 + 2].strip("{} ")
                # if there are formatting commands, preserve them
                tail = ""
                if "|" in key:
                    tail_pos = key.find("|")
                    tail = key[tail_pos:]
                # one special case: for symmetry we map i/keyname to keyname
                # this provides symmetry with the 'd/' and 's/' cases
                if key.startswith('i/'):
                    key = key[2:]
                elif len(key) > 2:
                    # '/' is illegal in Django macros, so we convert to 'Z' internally
                    if key[1] == '/':
                        key = key[:1] + 'Z' + key[2:]
                    elif key[2] == '/':
                        key = key[:2] + 'Z' + key[3:]
                # is the key in the context?
                if key in context:
                    # start with simple replacement
                    value = str(context[key])
                    if tail:
                        # if there is a tail, substitute {{value|tail}}
                        value = "{{" + value + tail + "}}"
                    # substitute
                    s = s[:pos] + value + s[pos + pos2 + 2:]
                if wildcard:
                    if wildcard in key:
                        tag_match = fnmatch.filter(list(context.keys()), key.replace('{', '').replace('}',''))
                        if len(tag_match) > 0:
                            value = tag_match[0]
                            s = s[:pos] + value + s[pos + pos2 + 2:]
                pos2 = pos + 2
                pos = s[pos2:].find("{{")
                if pos >= 0:
                    pos += pos2
            except:
                pos = -1
    return s


# Walk the dictionary and expand {{}} macros with values in the context
def expand_dictionary_context(d, context):
    for key, value in d.items():
        if isinstance(value, str) and ('{{' in value):
            d[key] = expand_string_context(value, context)
    return


def split_quoted_string_list(s, delimiter=None):
    '''Split a string into a list at shlex determined locations, properly handling quoted strings'''
    tmp = shlex.shlex(s)
    if delimiter is not None:
        tmp.whitespace = delimiter
    else:
        tmp.whitespace += ','
    # only split at the whitespace chars
    tmp.whitespace_split = True
    # we do not have comments
    tmp.commenters = ''
    out = list()
    while True:
        token = tmp.get_token()
        token = token.strip()
        if (token.startswith("'") and token.endswith("'")) or (token.startswith('"') and token.endswith('"')):
            token = token[1:-1]
        if len(token) == 0:
            break
        out.append(token)
    return out


# used to preview a tagging transform
@register.simple_tag
def apply_tag_operation(tags, operation, name, value):
    return do_retag_operation(tags, operation, name, value)


def fix_space(input_str):
    '''
    Address spaces. Tags can have spaces both in the tag name and
    in the tag value. This routine checks for possible situations
    and adds single or double quotes as needed


    Parameters
    ----------
    input_str: str
        String to check and fix
    
    Returns
    -------
    str
        The corrected string

    '''
    if input_str is None:
        return ''
    if ' ' not in input_str:
        return input_str
    else:
        if '"' in input_str:
            # if it has double quotes,
            # place it inside single quotes
            return f"'{input_str}'"
        else:
            return f'"{input_str}"'


def do_retag_operation(curr_tags, operation, tag_name, tag_value):
    # do nothing if empty
    if not tag_name:
        return curr_tags
    # build dict
    tag_dict = {}
    # make sure cases like foo='a bar example' work (use shlex.split)
    for tag in shlex.split(curr_tags):
        if '=' in tag:
            name, value = tag.split('=')
        else:
            name, value = (tag, None)

        if name:
            tag_dict[name] = value
    # "1" // Add a tag
    # "2" // Remove a tag
    # "3" // Replace a tag
    if operation == "1":
        # Add tag. If it already exists, replace it
        tag_dict[tag_name] = tag_value
    elif operation == "2":
        # delete the tag if it exists
        if tag_name in tag_dict:
            # delete only if value is not specified or
            # if specified and matches existing value
            if tag_value is None or tag_value == tag_dict[tag_name]:
                del tag_dict[tag_name]
    elif operation == "3":
        # replace the tag (and value) only if it exists
        if tag_name in tag_dict:
            tag_dict[tag_name] = tag_value
    # rebuild
    rebuilt_tags = ""
    for name, value in tag_dict.items():
        rebuilt_tags += fix_space(name)
        rebuilt_tags += '='
        rebuilt_tags += fix_space(value)
        # separate tags by a space
        rebuilt_tags += " "

    return rebuilt_tags.rstrip()
