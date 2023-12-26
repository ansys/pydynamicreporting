#
# *************************************************************
#  Copyright 2022-2023 ANSYS, Inc.
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

import glob
import os
import shutil
import uuid

import dateutil
import numpy
import pytz
from ceireports import nexus_version
from ceireports.exceptions import FileEncodingNotSupportedError, InvalidDateTimeException
from django.conf import settings
from django.core.files.base import File
from django.utils import timezone
from rest_framework import exceptions

from .constants import SUPPORTED_FILE_ENCODINGS, BULK_QUERY_BATCH_SIZE, BULK_QUERY_BATCH_THRESHOLD


def get_unique_id():
    return str(uuid.uuid4()).replace("-", "")


def get_nexus_version():
    return nexus_version.nexus_version


def delete_item_media(guid):
    """
    Delete any related files for an item.
    :return:
    """
    # Delete the media file(s) associated with this item
    wild = os.path.join(settings.MEDIA_ROOT, str(guid)) + '*'
    for path in glob.glob(wild):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass


def is_using_sqlite():
    """
    Check if current database is sqlite.

    :return: bool
    """
    from django.db import connection
    return connection.vendor.lower() == 'sqlite'


def check_allow_bulk_and_raise(request):
    """
    There are 3 ways of specifying what to change/delete in a bulk operation:
    1. A list of guids in the request body. eg: [{'guid': 'blah'}, {'guid': 'blah2'},...]
    2. A query param named `query` to filter items used in get_queryset(). eg: {request_url}?query=
    3. A list of guids through a query param named i_guid. eg: {request_url}?i_guid=guid1,guid2
    #3 is not used that much. fyi
    if we dont find any of these, its unfiltered and we could end up deleting everything in the db.
    so if its an unfiltered request, we deny immediately to avoid deleting the entire queryset.

    Args:
        request:

    Returns:

    """
    if not request.data and not request.query_params.get('query') and not request.query_params.get('i_guid'):
        raise exceptions.ValidationError


def get_bulk_batch_size(count):
    """
    If count exceeds a threshold, split into batches,
    otherwise use all of them at once (None)
    :param count: obj count
    :return:
    """
    batch_size = BULK_QUERY_BATCH_SIZE
    batch_threshold = BULK_QUERY_BATCH_THRESHOLD
    if is_using_sqlite():
        # reduce batch size considerably when using sqlite.
        # definitely makes the insert/update slower, but
        # that's what you pay for using sqlite.
        batch_size = batch_size // 10
        batch_threshold = batch_threshold // 10

    return batch_size if count >= batch_threshold else None


def check_encoding_and_raise(the_file):
    """
    Check the encoding of the incoming file bytestream and
    raise if encoding is not supported.

    :param the_file:
    :return:
    """

    # has to have a read() method, before proceeding.
    if not isinstance(the_file, File):
        return

    from chardet.universaldetector import UniversalDetector
    detector = UniversalDetector()

    # Also, we read the file in chunks to avoid reading a huge file
    # at once into memory.
    byte_chunk = 1000

    # max number of bytes to read
    # todo: decide on max bytes
    max_bytes = 3000

    # initial read
    data = the_file.read(byte_chunk)

    # track bytes read
    bytes_read = byte_chunk

    # Read chunks of file & feed to the detector.
    # when the detector reaches a min threshold of confidence,
    # it will set detector.done to True.
    while data:
        detector.feed(data)
        # until detector has reached a confidence level, OR n bytes
        # to avoid reading a huge file into memory.
        if detector.done or bytes_read > max_bytes:
            break

        data = the_file.read(byte_chunk)
        bytes_read += byte_chunk

    # detector.close() will do some final calculations in case
    # the detector didn’t hit its minimum confidence threshold earlier
    detector.close()

    # reset cursor to start of file, otherwise there might be nothing to read after.
    the_file.seek(0, 0)

    encoding = detector.result.get('encoding', '')
    # check and raise.. again, this is not completely reliable
    # this check is still a good trade off because when we try to decode later during item.render,
    # with utf-8 and the original encoding was something else, it will crash.
    # Note: A latin-1 result with a low chardet 'confidence' can be Windows' cp1252.
    if not encoding or encoding.lower() not in SUPPORTED_FILE_ENCODINGS:
        raise FileEncodingNotSupportedError("Based on our guess, the uploaded file is not UTF-8 encoded and "
                                            "hence not supported. If you know your file content is valid UTF-8,"
                                            " please disable the file encoding check and try again.")


def get_aware_datetime(datetime_str):
    """
    Converts an ISO style datetime (no microseconds) to timezone aware.

    ALWAYS USE UTC ON THE SERVER SIDE. When this is served via templates,
    template tags like 'date' can be used to convert this UTC datetime to
    the user's current timezone (or settings.TIME_ZONE). We can either depend
    on that or do it this way and then return to the front-end:

    # >>> utc_dt = datetime(2002, 10, 27, 6, 0, 0, tzinfo=utc)
    # >>> loc_dt = utc_dt.astimezone(pytz.timezone('US/Eastern'))
    # >>> loc_dt.strftime(fmt)
    # '2002-10-27 01:00:00 EST-0500'

    The preferred way of dealing with times is to always work in UTC, converting
    to localtime only when generating output to be read by humans.

    :param datetime_str: ISO formatted datetime str, eg: 2019-06-17T12:30:00
    :return: tz-aware datetime
    """
    try:
        # convert the string to datetime obj
        parsed_time = dateutil.parser.isoparse(datetime_str).replace(microsecond=0)
        # if already aware, return it
        if timezone.is_aware(parsed_time):
            return parsed_time
        # set the user's set timezone (User settings -> .activate() in middleware) to the datetime
        # i.e. adds the UTC offset of the user's timezone to the datetime.
        # eg: '2019-06-17 15:20:00' becomes '2019-06-17 15:20:00+02:00' if tz is `Europe/Paris`
        localized_time = timezone.make_aware(parsed_time, timezone=timezone.get_current_timezone())
    except Exception:
        # for other weird errors, raise
        raise InvalidDateTimeException(f'The date entered ({datetime_str}) is invalid.')
    # return the time in UTC
    # eg: '2019-06-17 15:20:00+02:00' becomes '2019-06-17 15:20:00' if tz is `Europe/Paris`
    # when this is displayed by Django, the active timezone is again used to convert back.
    return localized_time.astimezone(pytz.UTC)


def decode_table_data(data):
    """
    Table data can be passed around as numpy arrays in bytes. (eg: in Generators)
    This is done for efficient manipulation, although this can change in future.
    Since this is the case now, right before we render html out of it, we will have
    to decode each element in the numpy array explicitly to utf-8 strings.

    We do this whole conversion ONLY if the numpy array's dtype is bytes.

    Be aware that row and col labels can be bytes as well, as these are derived from table data.
    so they have to be decoded as well.
    :param data: dictionary obtained after unpickling item.payloaddata
    :return: dict with utf-8 strings throughout
    """

    def bytes_to_utf8(input_):
        # use utf-8 to decode the bytestream
        if isinstance(input_, bytes):
            return input_.decode('utf-8')
        elif isinstance(input_, list):
            # if a list has a list has a list..use recursion
            return list(map(bytes_to_utf8, val))
        else:
            # if input was a different type, .decode will fail.
            return input_

    if isinstance(data, dict):
        for key, val in data.items():
            # numpy arrays have a special decode function
            if isinstance(val, (numpy.ndarray, numpy.generic)):
                data[key] = numpy.char.decode(val, encoding='utf-8')
                continue
            # if bytes or list[bytes], then we decode to a string
            if isinstance(val, bytes) or isinstance(val, list):
                data[key] = bytes_to_utf8(val)

    return data
