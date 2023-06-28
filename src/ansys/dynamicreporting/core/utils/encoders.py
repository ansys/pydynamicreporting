import datetime
import json
import uuid

from .report_utils import nexus_array

try:
    import numpy

    has_numpy = True
except ImportError:
    has_numpy = False


class BaseEncoder(json.JSONEncoder):
    """
    Provides base encoding operations.

    .. warning::
       The ``isinstance()`` checks **always** come first.
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            representation = obj.isoformat()
            if representation.endswith("+00:00"):
                representation = representation[:-6] + "Z"
            return representation
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, bytes):
            return obj.decode()
        elif hasattr(obj, "__getitem__"):
            cls = list if isinstance(obj, (list, tuple)) else dict
            try:
                return cls(obj)
            except Exception:
                pass
        elif hasattr(obj, "__iter__"):
            return tuple(item for item in obj)

        return super().default(obj)


class PayloaddataEncoder(BaseEncoder):
    """
    Provides the ``JSONEncoder`` subclass, which knows how to encode item.payloaddata.

    This class supports encoding of these datatypes: float, int, datetime.datetime, str,
    bool, uuid.UUID, and None. Only these datatypes need to explicitly be taken care of:
    numpy, nexus_array, datetime.datetime, and uuid.UUID. The other datayptes are taken
    care of by JSON.

    .. warning::
       This ``default`` method is completely dependent on the fact that user input will
       contain only the above accepted data types. If the list above changes, the code
       below must handle that.
    """

    def default(self, obj):
        # first check if there's numpy before using its imports
        if has_numpy and isinstance(obj, numpy.ndarray):
            # numpy arrays
            return obj.tolist()
        elif isinstance(obj, nexus_array):
            # Nexus arrays.
            return obj.to_2dlist()

        return super().default(obj)
