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

from enum import Enum

from django.conf import settings
from django.core import signing
from django.core.exceptions import SuspiciousOperation


def unsign_hash(s, key=None, salt='django.core.signing', algorithm=None, serializer=signing.JSONSerializer,
                max_age=None):
    """
    Proxy of django.core.signing.loads but adds a kwarg "algorithm" to specify the hashing algorithm
    which signing.TimestampSigner accepts.
    Reverse of dumps(), raises BadSignature if signature fails.
    """
    # algorithm is sha-256 by default in Django 3.1+
    signer = signing.TimestampSigner(key=key, salt=salt, algorithm=algorithm)
    return signer.unsign_object(s, serializer=serializer, max_age=max_age)


def decrypt_hash(auth_hash, salt=None):
    """
    Decrypt any hash signed by Django.

    :param auth_hash:
    :param salt:
    :param max_age: maximum age of hash in seconds
    :return: dict
    """
    try:
        # decrypt it and check for obj perms burned in
        # use sha-256 by default
        decrypted_dict = unsign_hash(auth_hash, salt=salt)
    except signing.BadSignature:
        try:
            # try using sha-1 for backwards compatibility
            decrypted_dict = unsign_hash(auth_hash, salt=salt, algorithm='sha1')
        except signing.BadSignature:
            # raise a 400 if Django thinks its been tampered with.
            raise SuspiciousOperation("The authorization information is invalid.")

    return decrypted_dict


def get_version_tuple(ver_str):
    """
    Returns a tuple of the version info

    :param ver_str:
    :return:
    """
    return tuple([int(x) for x in ver_str.split(".")])


def get_render_error_html(error, *, target='element', guid=None):
    """
    Generates rendering error html block for the appropriate item name

    :param error: the exception/error
    :param target: type of the target element
    :param guid: Optional ID to embed in the html
    :return: string containing html to render
    """
    if settings.DEBUG:
        raise

    return f"""
            <div class="container-fluid" data-guid="{guid}">\n
                <div class="bs-callout bs-callout-danger">\n
                    <h2>{target.capitalize()} render error</h2>\n
                    Unfortunately, we were unable to process this {target.lower()} due to the error:<br>\n
                    <em>{error}</em>\n
                </div>\n
            </div>\n
            """


def get_unsupported_error_html(feature, print_style):
    """
    Generates unsupported error html block for the appropriate feature
    and export style.

    :param feature: the name of the unsupported feature
    :param print_style: the target format
    :return: string containing html to render
    """
    return f"""
            <div class="container-fluid text-center">\n
                <div class="alert alert-danger">\n
                    <h4>Exported {print_style.upper()} does not support {feature}</h4>\n
                </div>\n
            </div>\n
            """


class StrEnum(str, Enum):
    """Enum with a str mixin"""

    def __str__(self):
        return self.value


class IntEnum(int, Enum):
    """Enum with an int mixin"""

    def __int__(self):
        return self.value
