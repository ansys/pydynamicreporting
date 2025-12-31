import datetime
import json
import uuid
from typing import Any

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

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            representation = o.isoformat()
            if representation.endswith("+00:00"):
                representation = representation[:-6] + "Z"
            return representation
        elif isinstance(o, uuid.UUID):
            return str(o)
        elif isinstance(o, bytes):
            return o.decode()
        elif hasattr(o, "__getitem__"):
            cls = list if isinstance(o, (list, tuple)) else dict
            try:
                return cls(o)
            except Exception as e:  # nosec
                error_str = f"Object of type {type(o).__name__} is not JSON serializable: "
                error_str += str(e)
                raise TypeError(error_str)
                pass
        elif hasattr(o, "__iter__"):
            return tuple(item for item in o)

        return super().default(o)


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

    def default(self, o: Any) -> Any:
        # first check if there's numpy before using its imports
        if has_numpy and isinstance(o, numpy.ndarray):
            # numpy arrays
            return o.tolist()
        elif isinstance(o, nexus_array):
            # Nexus arrays.
            return o.to_2dlist()

        return super().default(o)
