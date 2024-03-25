"""
All Python3 migration-related ugly hacks go here.
The name suggests that this file needs to be removed at some point.

and... trust me.. YOU DON'T WANNA READ THIS FILE.
"""

import base64
import pickle

from django.conf import settings

from ..report_framework.exceptions import SafeUnpickleException


def safe_unpickle(input_data):
    """
    Takes a str/bytes obtained from a pickle and returns the unpickled data.
    WARNING: Ideally, it will always be bytes.

    NOTE: If its a string, it was probably bytes before that and then was coerced at some point.

    Hacky way of dealing with pickle. Temp fix. Needs to go.

    :param item_type: Type of the item whose data is being unpickled
    :param input_data: str or bytes
    :return: can be any type of picklable object.
    """
    try:
        if input_data:
            if isinstance(input_data, str):
                # With the 2020R1 release, a new protocol for packing pickle.dumps() output into
                # an ASCII string by base64 encoding the bytes and adding a prefix '!@P0@!' to the
                # string. We can decode this here.
                if input_data.startswith('!@P'):
                    # the encoding looks like:
                    # s = '!@P0@!' + base64.b64encode( pickle.dumps(object, protocol=0) ).decode("utf-8")
                    # so reverse it...
                    bytes_data = base64.b64decode(input_data[6:])
                else:
                    # In python2 pickle.dumps uses the pickling protocol 0 by default,
                    # where it encodes it in latin1, giving bytes.
                    # In cases where this was stored in a TextField,
                    # Django coerces the bytes to a utf-8 (django default) string and saves it.
                    # when we access that again, we get that string, so we encode it into bytes and then
                    # pickle.load as latin1 to get the data which was pickle-dumped into the database field.
                    # This is unnecessary but we do it for backwards compatibility.
                    # WARNING: In python3, pickle.dumps will use protocol 3, which has support for bytes,
                    # but can't be unpickled in py2.
                    # NOTE: using latin1 here would cause an encode error with international text dumped in Py3.
                    bytes_data = input_data.encode('utf-8')

            elif isinstance(input_data, bytes):  # if bytes
                bytes_data = input_data
            else:
                bytes_data = bytes()

            if bytes_data:
                # We then load/decode the pickled data:
                try:
                    # be default, we follow python3's way of loading: default encoding is ascii
                    # this will work if the data was dumped using python3's pickle. Just do the usual.
                    data = pickle.loads(bytes_data)
                except Exception:
                    try:
                        data = pickle.loads(bytes_data, encoding='utf-8')
                    except Exception:
                        # if it fails, which it will if the data was dumped using python2's pickle, then:
                        # As per https://docs.python.org/3/library/pickle.html#pickle.loads,
                        # "Using encoding='latin1' is required for unpickling NumPy arrays and instances of datetime,
                        # date and time pickled by Python 2."
                        # The data does contain a numpy array. So:
                        data = pickle.loads(bytes_data, encoding='latin-1')

                        # if the stream contains international characters which were 'loaded' with latin-1,
                        # we get garbage text. We have to detect that and then use a workaround.
                        # So why not pickle-load it with utf-8 instead of this god-awful hack?
                        # Because it was originally dumped in Python2 as latin-1 and there will
                        # be a UnicodeDecodeError if you load with utf-8 in Python3.
                        # (latin-1 is not a subset of utf-8)
                        data = reconstruct_international_text(data)

                # necessary if the data was bytes before it was pickle dumped
                # in the first place. (eg: txt, html file uploads)
                if isinstance(data, bytes):
                    try:
                        data = data.decode('utf-8')
                    except UnicodeDecodeError:
                        # this is the result of forcing a non-utf8 file as utf-8
                        # for eg. during file upload. We give the data loss the user
                        # asked for with errors='ignore'
                        data = data.decode('latin-1', errors='ignore')

                return data

    except Exception as e:
        if settings.DEBUG:
            raise

        raise SafeUnpickleException(f"Unable to load the item from the database:: {e}")

    # if the input wasn't bytes or string or anything that evaluated to False, return it back
    return input_data


def reconstruct_international_text(data):
    """
    Yet another god-awful hack that fixes mojibake of international
    characters in text like row/column labels when using latin-1 to
    pickle-load.

    :param data: input data dict
    :return: reconstructed dict.
    """

    def latin1_to_utf8(input_):
        # the workaround is to use latin-1 again to get the original
        # bytestream, and this time, use utf-8 to decode.
        if isinstance(input_, str):
            return input_.encode('latin-1').decode('utf-8')
        elif isinstance(input_, list):
            # if a list has a list has a list..use recursion
            return list(map(latin1_to_utf8, val))
        else:
            # if input was a different type, .encode will fail.
            return input_

    if isinstance(data, dict):
        for key, val in data.items():
            # only reconstruct these types, otherwise pass.
            # str or list[str] is acceptable.
            if isinstance(val, str) or isinstance(val, list):
                data[key] = latin1_to_utf8(val)

    return data
