import array
import base64
from html.parser import HTMLParser as BaseHTMLParser
import os
import os.path
import platform
import socket
import sys
import tempfile
from typing import List, Optional

import requests

try:
    import ceiversion
    import enve

    has_enve = True
except (ImportError, SystemError):
    has_enve = False

try:
    from PyQt5 import QtCore, QtGui

    has_qt = True
except ImportError:
    has_qt = False

try:
    import numpy

    has_numpy = True
except ImportError:
    has_numpy = False

text_type = str
"""@package report_utils
Methods that serve as a shim to the enve and ceiversion modules that may not be present
"""


def decode_url(s):
    if s.startswith("b64:"):
        tmp = s[4:].replace("_", "=")
        s = base64.b64decode(tmp).decode("utf-8")
    return s


def encode_url(s):
    s = "b64:" + base64.b64encode(s.encode("utf-8")).decode("utf-8").replace("=", "_")
    return s


def is_enve_image(img):
    if has_enve and has_qt:  # pragma: no cover
        return isinstance(img, enve.image)
    return False


def enve_image_to_data(img, guid=None):
    # Convert enve image object into a dictionary of image data or None
    # The dictionary has the keys:
    # 'width' = x pixel count
    # 'height' = y pixel count
    # 'format' = 'tif' or 'png'
    # 'file_data' = a byte array of the raw image (same content as disk file)
    if has_enve and has_qt:  # pragma: no cover
        if isinstance(img, enve.image):
            data = dict(width=img.dims[0], height=img.dims[1])
            if img.enhanced:
                with tempfile.TemporaryDirectory() as temp_dir:
                    path = os.path.join(temp_dir, "enhanced_image.tif")
                    # Save the image as a tiff file (enhanced)
                    if img.save(path, options="Compression Deflate") == 0:
                        try:
                            # Read the tiff image data back
                            with open(path, "rb") as img_file:
                                data["file_data"] = img_file.read()
                            data["format"] = "tif"
                            return data
                        except OSError:
                            return None
            else:
                # convert to QImage via ppm string I/O
                tmpimg = QtGui.QImage.fromData(img.ppm(), "ppm")
                # record the guid in the image (watermark it)
                # note: the Qt PNG format supports text keys
                tmpimg.setText("CEI_REPORTS_GUID", guid)
                # save it in PNG format in memory
                be = QtCore.QByteArray()
                buf = QtCore.QBuffer(be)
                buf.open(QtCore.QIODevice.WriteOnly)
                tmpimg.save(buf, "png")
                buf.close()
                data["format"] = "png"
                data["file_data"] = buf.data()  # returns a bytes() instance
                return data
    return None


def enve_arch():
    if has_enve:
        return enve.arch()
    return platform.system().lower()


def enve_home():
    if has_enve:
        return enve.home()
    tmp = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return tmp


def ceiversion_nexus_suffix():
    if has_enve:
        return ceiversion.nexus_suffix
    # If we are coming from pynexus, get the version from that
    try:
        from ansys.dynamicreporting.core import ansys_version

        tmp = ansys_version.replace("R", "")[-3:]
        return str(tmp)
    except Exception:
        # get "nexus###" folder name and then strip off the "nexus" bit
        tmp = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
    return tmp[5:]


def ceiversion_apex_suffix():
    if has_enve:
        return ceiversion.apex_suffix
    # Note: at present the suffix strings are in lockstep and are expected
    # to stay that way.  So the Nexus suffix (easily found by the location
    # of this file) is a reasonable proxy for the apex suffix.
    return ceiversion_nexus_suffix()


def ceiversion_ensight_suffix():
    if has_enve:
        return ceiversion.ensight_suffix
    # Note: at present the suffix strings are in lockstep and are expected
    # to stay that way.  So the Nexus suffix (easily found by the location
    # of this file) is a reasonable proxy for the ensight suffix as well.
    return ceiversion_nexus_suffix()


def platform_encoding():
    if sys.platform.startswith("win"):
        return "mbcs"
    return "utf-8"


# Python 2: unicode, str(lcl), bytes(lcl) -> str(utf8)
# Python 3: str , bytes(lcl), bytes (utf8) -> bytes(utf8)
def local_to_utf8(v, use_unicode=False):
    if sys.version_info[0] < 3:  # pragma: no cover
        if (type(v) == str) or (type(v) == bytes):
            v = v.decode(platform_encoding())
    else:
        if type(v) == bytes:
            v = v.decode(platform_encoding())
    if use_unicode:
        return v
    return v.encode("utf-8")


# Python 2: unicode -> str(utf8), bytes/str(utf8) -> unicode -> str(lcl)
# Python 3: str -> bytes(lcl), bytes(utf8) -> unicode -> bytes(lcl)
def utf8_to_local(v):
    if sys.version_info[0] < 3:  # pragma: no cover
        if type(v) == unicode:
            return v.encode(platform_encoding())
        v = v.decode("utf-8")
    else:
        if type(v) == bytes:
            v = v.decode("utf-8")
    return v.encode(platform_encoding())


# Python 2: bytes(utf8) or str(utf8) -> unicode, assume utf8 source encoding
# Python 3: bytes(utf8) -> str assume utf8 source encoding
def utf8_to_unicode(v):
    if sys.version_info[0] < 3:  # pragma: no cover
        if type(v) == unicode:
            return v
        if type(v) == str:
            return v.decode("utf-8")
    if type(v) == bytes:
        return v.decode("utf-8")
    return v


# Python 2: str is assumed to be encoded, unicode -> str(lcl)
# Python 3: str -> str
def to_local_8bit(v):
    if sys.version_info[0] < 3:  # pragma: no cover
        # We are already the right type: str -> str
        if type(v) == str:
            return v
        # Qt5 unicode -> 8bit str
        if type(v) == unicode:
            return v.encode(platform_encoding())
    else:
        return v
    # Error
    return v


# Python 2: str(lcl) -> unicode,  bytes(lcl) -> unicode
# Python 3: bytes(lcl) -> str
def from_local_8bit(v):
    if sys.version_info[0] < 3:  # pragma: no cover
        if type(v) == str:
            return v.decode(platform_encoding())
    if type(v) == bytes:
        return v.decode(platform_encoding())
    # Error
    return v


def convert_windows_pathname(path, long=True):
    """
    This function will convert a Windows pathname from 'long' to 'short' (8.3) or the
    reverse.

    On non-Windows platform, it does nothing.
    :param path:  The pathname to convert.
    :param long:  If True, the conversion is from 'short' to 'long', if False, from 'long' to 'short'.
    :return:  The converted pathname or if no conversion could be performed, the input pathname is returned.
    """
    if sys.platform.startswith("win"):  # pragma: no cover
        import ctypes

        bufsize = 512
        buf = ctypes.create_unicode_buffer(bufsize)
        if long:
            path_function = ctypes.windll.kernel32.GetLongPathNameW
        else:
            path_function = ctypes.windll.kernel32.GetShortPathNameW
        rv = path_function(path, buf, bufsize)
        if rv != 0 and rv <= bufsize:
            return buf.value
    return path


def run_web_request(method, server, relative_url, data=None, headers=None, stream=False):
    """
    When a request is made to REST, HTTP basic auth is used by default through requests
    when you pass (username, password) as auth.

    This will be discarded by the server if it's not a REST request. A non-REST
    interaction with the server MUST use session authentication, first login, and reuse
    that session to perform further requests.
    """
    username, passwd = server.get_auth()
    login_url = server.build_request_url("/login/")
    response = None

    session = server._http_session

    # first, login to authenticate the web session
    init_response = session.get(login_url)
    # get the csrf token post login, to use for further requests
    csrf_token = init_response.cookies.get("csrftoken")

    if csrf_token:
        # use the token and then login
        login_response = session.post(
            login_url,
            data={
                "username": username,
                "password": passwd,
                "csrfmiddlewaretoken": csrf_token,
                "next": "/",
            },
        )
        if login_response.status_code == requests.codes.ok:
            # once logged in, non-REST requests can be done using SessionAuth
            resource_url = server.build_request_url(relative_url)
            req = requests.Request(method, resource_url, data=data, headers=headers)
            prepped_req = session.prepare_request(req)
            # session.send can take many more kwargs as needed
            response = session.send(prepped_req, stream=stream)

    return response


def isSQLite3(filename):
    """
    Check if a file is a SQLite database.

    Parameters
    ----------
    str
        filename: name of the file to check

    Returns
    -------
    bool
        True: it is a valid SQLite database False: it is not
    """
    from os.path import getsize, isfile

    if not isfile(filename):
        return False
    if getsize(filename) < 100:  # SQLite database file header is 100 bytes
        return False
    with open(filename, "rb") as fd:
        header = fd.read(100)
    return header[:16] == b"SQLite format 3\x00"


class nexus_array:
    """
    The nexus_array object stores a multi-dimensional array of items of a specific type.

    The object is modeled roughly after the numpy array object in that the dimensionality
    of the object is stored as the shape of the array.  The dtype of the array is specified
    in a subset of the numpy dtype strings:
        'f4' = float32
        'f8' = double or float64
        'i4' = int32
        'u4' = uint32
        'i8' = int64
        'u8' = uint32
        'S{x}' = string of fixed size {x}
        'B' = int8
    """

    def __init__(self, dtype="f4", shape=(1, 1)):
        """
        Initialize a nexus_array object.

        :param dtype: The storage type of the array.
        :type dtype: str.
        :param shape: The dimensionality of the array
        :type shape: tuple.
        :returns:  nexus_array
        """
        self._strlen = 1
        self.array = None
        self.dtype = ""
        self.shape = (0,)
        self.size = 1
        self.set_dtype(dtype)
        self.set_shape(shape)
        self.set_size(shape)

    def update_array(self):
        """Update the underlying _array member to match the current _shape and _dtype
        state."""
        if (self.array is None) or (self.count(string_size=True) != len(self.array)):
            self.array = array.array(self.numpy_to_array_type(self.dtype))
            self.array.extend(range(self.count(string_size=True)))

    def count(self, string_size=False):
        """
        Get the number of items in the array.

        :param string_size: If true, the size of strings will be included in the count
        :type string_size: bool
        :returns: the number of elements in the array
        """
        count = 1
        for v in self.shape:
            count *= v
        if string_size and (self.dtype[0] == "S"):
            count *= self.element_size()
        return count

    def element_size(self):
        """Get the size of each element in bytes
        :returns: the size of each element in bytes
        """
        return self.array.itemsize * self._strlen

    def set_shape(self, value):
        self.shape = value
        self.update_array()

    def set_size(self, shape):
        size = 1
        for s in shape:
            size *= s
        self.size = size

    def set_dtype(self, value):
        if value != self.dtype:
            self.array = None
        self.dtype = value
        if self.dtype[0] == "S":
            self._strlen = int(self.dtype[1:])
        else:
            self._strlen = 1
        self.update_array()

    def _index(self, key):
        # [int] = simple array index
        # [tuple] = [slow to fast], e.g. [z,y,x]
        if type(key) != tuple:
            index = key
        else:
            index = 0
            mult = 1
            for v, d in zip(reversed(key), reversed(self.shape)):
                index += mult * v
                mult = mult * d
        if self.dtype[0] == "S":
            index *= self._strlen
        return index

    def __getitem__(self, key):
        idx = self._index(key)
        if self.dtype[0] != "S":
            return self.array[idx]
        return bytes(self.array[idx : idx + self._strlen])

    def __setitem__(self, key, value):
        idx = self._index(key)
        if self.dtype[0] != "S":
            # further encoding needed only for byte-string dtype
            self.array[idx] = value
            return
        # since we only handle byte-strings from here on.
        # convert any input that is not bytes to bytes
        tmp = value
        if not isinstance(tmp, bytes):
            tmp = str(tmp).encode("utf-8")
        tmp = tmp + (b" " * self._strlen)
        tmp_arr = array.array("B")
        tmp_arr.frombytes(tmp)
        self.array[idx : idx + self._strlen] = tmp_arr[0 : self._strlen]

    @classmethod
    def numpy_to_array_type(cls, np_dtype):
        """Convert a numpy type specification to the form used by the array module
        :param np_dtype: the numpy dtype (object or string)
        :typa np: str
        :returns: array module type specification
        """
        if has_numpy and isinstance(np_dtype, numpy.dtype):
            dtype_str = f"{str(np_dtype.kind)}{str(np_dtype.itemsize)}"
        else:
            dtype_str = np_dtype

        np_array_lookup = {
            "f4": "f",
            "f8": "d",
            "B": "B",
            "i2": "i",
            "u2": "I",
            "i4": "l",
            "u4": "L",
            "i8": "q",
            "u8": "Q",
        }

        if isinstance(dtype_str, text_type):
            if dtype_str.startswith("S"):
                return "B"
            elif dtype_str in np_array_lookup:
                return np_array_lookup[dtype_str]

        raise ValueError("Not a valid numpy dtype")

    @classmethod
    def numpy_to_na_type(cls, np_dtype):
        """
        Convert a numpy type specification to the form used by the nexus_array object
        This is effectively a re-generation of the object returned by a numpy dtype
        object into a simpler string that is used by the nexus_array object and is legal
        for the numpy_to_array_type() method.  It is basically a specialized 'str()'
        cast.

        :param np_dtype: the numpy dtype (object or string)
        :typa np: str
        :returns: nexus_array type specification
        """
        if has_numpy and isinstance(np_dtype, numpy.dtype):
            dtype_str = f"{str(np_dtype.kind)}{str(np_dtype.itemsize)}"
        else:
            dtype_str = np_dtype

        np_array_lookup = {
            "f4": "f4",
            "f8": "f8",
            "B": "B",
            "i2": "i2",
            "u2": "u2",
            "i4": "i4",
            "u4": "u4",
            "i8": "i8",
            "u8": "u8",
        }

        if isinstance(dtype_str, text_type):
            if dtype_str.startswith("S"):
                return "B"
            elif dtype_str in np_array_lookup:
                return np_array_lookup[dtype_str]

        raise ValueError("Not a valid numpy dtype")

    def to_bytes(self):
        self.update_array()
        return self.array.tobytes()

    def to_2dlist(self):
        to_list = list()
        for i in range(self.shape[0]):
            to_list.append(list())
            for j in range(self.shape[1]):
                to_list[i].append(self.__getitem__((i, j)))
        return to_list

    def to_numpy(self, writeable=False):
        if not has_numpy:
            raise ImportError
        a = numpy.frombuffer(self.array.tobytes(), dtype=self.dtype)
        a.shape = self.shape
        if writeable:
            import copy

            return copy.deepcopy(a)
        return a

    def to_json(self):
        """
        Serialize into JSON.

        :return:
        """
        return {
            "array": self.to_2dlist(),
            "shape": self.shape,
            "size": self.size,
            "dtype": self.dtype,
        }

    def from_bytes(self, value):
        self.array = array.array(self.dtype)
        self.array.frombytes(value)
        self.shape = (len(self.array), 1)

    def from_2dlist(self, value):
        dx = len(value)
        if dx == 0:
            self.set_shape((0,))
            return
        dy = len(value[0])
        self.set_shape((dx, dy))
        self.set_size(self.shape)
        # note: it is not possible/recommended to
        # guess the dtype from the elements here
        for i in range(self.shape[0]):
            for j in range(self.shape[1]):
                self.__setitem__((i, j), value[i][j])

    def from_numpy(self, value):
        if not has_numpy:
            raise ImportError
        self.dtype = self.numpy_to_na_type(value.dtype)
        self.array = array.array(self.numpy_to_array_type(self.dtype))
        self.array.frombytes(value.tobytes())
        self.shape = value.shape

    @classmethod
    def unit_test(cls):
        tmp = nexus_array(shape=(5, 3), dtype="f8")
        if tmp.count() != 5 * 3:
            raise Exception("Incorrect double array size")
        if tmp.element_size() != 8:
            raise Exception("Invalid double size")
        tmp[3, 2] = 100.0
        np = tmp.to_numpy(writeable=True)
        if np[3, 2] != 100.0:
            raise Exception("Invalid to_numpy operation")
        if np.shape != (5, 3):
            raise Exception("Invalid to_numpy shape")
        np[3, 2] = 200.0
        tmp.from_numpy(np)
        if tmp[3, 2] != 200.0:
            raise Exception("Invalid from_numpy operation")
        if tmp.shape != (5, 3):
            raise Exception("Invalid from_numpy shape")
        tmp.set_dtype("S5")
        tmp.set_shape((4, 4))
        if tmp.count() != 4 * 4:
            raise Exception("Incorrect array size")
        if tmp.element_size() != 5:
            raise Exception("Invalid string size")
        tmp[1, 1] = b"Hello"
        np = tmp.to_numpy()
        if np[1, 1] != b"Hello":
            raise Exception("Invalid string store")


class Settings:
    """Utility class to load and use configuration."""

    def __init__(self, defaults, *args, **kwargs):
        for idx, key in enumerate(defaults.keys()):
            # if kwarg is passed as positional args,
            # positional arg should take precedence
            try:
                value = args[idx]
            except IndexError:
                # fallback to defaults
                value = kwargs.get(key, defaults[key])
            setattr(self, key, value)


def find_unused_ports(
    count: int,
    start: Optional[int] = None,
    end: Optional[int] = None,
    avoid: Optional[List[int]] = None,
) -> Optional[List[int]]:
    """
    Find "count" unused ports on the host system.  A port is considered unused if it
    does not respond to a "connect" attempt.  Walk the ports from 'start' to 'end'
    looking for unused ports and avoiding any ports in the 'avoid' list.  Stop once the
    desired number of ports have been found.  If an insufficient number of ports were
    found, return None. An admin user check is used to skip [1-1023].

    :param int count: number of unused ports to find
    :param Optional[int] start: the first port to check or None (random start)
    :param Optional[int] end: the last port to check or None (full range check)
    :param Optional[List[int]] avoid: an optional list of ports not to check
    :returns Optional[List[int]]: the detected ports or None on failure
    """
    if avoid is None:
        avoid = []
    ports = list()
    # Avoid trying to use privileged ports as a non-privileged user
    is_admin = is_user_admin()
    # if no "start" specified, generate one using our pid, avoiding [0,1023]
    if start is None:
        start = (os.getpid() % 64000) + 1024
    # if start is outside [0,1023], assume we should avoid it entirely
    if start >= 1024:
        is_admin = False
    # We will scan for 65530 ports unless end is specified
    port_mod = 65530
    if end is None:
        # we will mod by port_mod, so make sure that looping will not repeat the port
        end = start + port_mod - 1
    # walk the "virtual" port range
    for base_port in range(start, end + 1):
        # Map to physical port range
        # There have been some issues with 65534+ so we stop at 65530
        port = base_port % port_mod
        # port 0 is special
        if port == 0:
            continue
        # avoid admin ports
        if is_admin and (port < 1024):
            continue
        # are we supposed to skip this one?
        if port in avoid:
            continue
        # is anyone listening?
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        if result != 0:
            ports.append(port)
        else:
            sock.close()
        if len(ports) >= count:
            return ports
    # in case we failed...
    if len(ports) < count:
        return None
    return ports


def is_user_admin() -> bool:
    """
    Check to see if the current user is likely to have root/administrator level system
    access. Under Windows, this is not a complete test, but it is a reasonable proxy.

    :returns bool: True if the current user has higher-level access permissions
    """
    try:
        # on Windows this will throw AttributeError
        return os.geteuid()
    except AttributeError:
        try:
            import ctypes

            # on non-Windows systems, this can be ModuleNotFoundError
            # on some Windows machines this can be AttributeError
            return ctypes.windll.shell32.IsUserAnAdmin() == 1
        except (ModuleNotFoundError, AttributeError):
            return False


def is_port_in_use(port: int, admin_check: bool = False) -> bool:
    """
    Check to see if a local TCP/IP port is available for potential binding. If the
    admin_check is True, mark the part as in use if it is in the range [1,1023].

    :param int port: The port number to check
    :param bool admin_check: If True, include an "admin" check for ports < 1024
    :returns bool: the detected ports or None on failure
    """
    if port <= 0:
        return False
    # if this is a "system" port, note the port as in use if one is not admin.
    if admin_check and port < 1024:
        if not is_user_admin():
            return True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", port))
    return result == 0


class HTMLParser(BaseHTMLParser):
    def __init__(self):
        super().__init__()
        self._links = []

    @property
    def links(self):
        return self._links

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href" and value != "#":
                    self._links.append(value)

    def reset(self):
        super().reset()
        self._links = []


def get_links_from_html(html):
    parser = HTMLParser()
    parser.feed(html)
    return parser.links


def apply_timezone_workaround() -> None:
    """
    Apply a workaround for known Linux system misconfigurations.

    There is a known issue on some Linux systems where the timezone configuration is
    incorrect. On these systems, the get_localzone_name() call will raise an exception
    that prevents a Django instance from starting.  This effects the Nexus server as
    well as the adr API for doing things like creating a database.

    The work-around is to try to trigger the exception early and (on failure) set the TZ
    environmental variable  to a known value and warn the user that this has been done.
    If the user sets TZ or corrects the system misconfiguration, that will also fix the
    issue.
    """
    try:
        # Attempt to trigger the misconfiguration issue.
        import tzlocal

        _ = tzlocal.get_localzone_name()
    except ModuleNotFoundError:
        # tzlocal is only used by the Django code, so if it is not present,
        return
    except KeyError as e:
        # Issue a warning
        import warnings

        msg = "The timezone of this session is not configured correctly, trying 'US/Eastern' : "
        warnings.warn(msg + str(e))
        # Try a relatively well known TZ
        os.environ["TZ"] = "US/Eastern"
