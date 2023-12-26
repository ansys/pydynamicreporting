import base64

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .constants import PICKLED_TYPES
from .models import Item


@receiver(pre_save, sender=Item)
def encode_decode_payloaddata(sender, instance, *args, **kwargs):
    """
    Base64 encode and then decode item payloaddata.
    1. Note that we are using a TextField to store payload, so we have to
    decode the bytes.
    2. This may also be used by the DRF serializer implicitly, but serializer
    passes in the decoded pickle string rather than bytes, so it wont run.
    3. This also solves another issue:
    Postgres silently truncates NULL bytes. When pickle loads it, it complains.
    to get around this, we avoid null bytes by using base64.
    4. ONLY applicable to certain item types.

    :param sender: Item class
    :param instance: the object being saved
    :param kwargs:
    :return:
    """
    if isinstance(instance.payloaddata, bytes) and instance.type in PICKLED_TYPES:
        # django 2.0+ will not accept bytes anymore, so decode explicitly.
        instance.payloaddata = '!@P1@!' + base64.b64encode(instance.payloaddata).decode("utf-8")
