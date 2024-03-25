from django.core import signing


def generate_media_auth_hash(dict_to_hash, salt):
    """
    Generate a signed hash for item media urls using session key
    as the salt

    :param dict_to_hash: data dict
    :param salt: salt to use

    :return: base64 value
    """
    return signing.dumps(dict_to_hash, salt=salt, compress=True)
