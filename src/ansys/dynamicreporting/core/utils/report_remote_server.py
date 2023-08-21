import urllib

try:
    from PyQt5 import QtCore, QtGui, QtWidgets

    has_qt = True
except ImportError:
    has_qt = False

import collections
import configparser
import functools
import hashlib
import inspect
import json
import logging
import os
import os.path
from pathlib import Path
import pickle
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import exceptions, filelock, report_objects, report_utils
from .encoders import BaseEncoder


def disable_warn_logging(func):
    # Decorator to suppress harmless warning messages
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logging.disable(logging.WARNING)
        try:
            return func(*args, **kwargs)
        finally:
            logging.disable(logging.NOTSET)

    return wrapper


def print_allowed():
    # Note: calling print() from a pythonw interpreter (e.g. template_editor launched
    # via the icon) an cause the interpreter to crash.  We will allow print, but only
    # if this is not a pythonw instance.
    return not sys.executable.lower().endswith("pythonw.exe")


def run_nexus_utility(args, use_software_gl=False, exec_basis=None, ansys_version=None):
    # Run the nexus_utility.py script with the command and parameters in the args list
    # are we on windows
    is_windows = report_utils.enve_arch().startswith("win")
    # is_linux = report_utils.enve_arch().startswith("lin")
    # Start the work by getting the pathname to the django directory
    if ansys_version:
        report_ver = str(ansys_version)
    else:
        report_ver = report_utils.ceiversion_nexus_suffix()
    if exec_basis is None:
        exec_basis = report_utils.enve_home()
    rptdir = os.path.join(exec_basis, "nexus" + report_ver, "django")
    nexus_utility = os.path.join(exec_basis, "nexus" + report_ver, "nexus_utility.py")
    # run any DB migrations using Python 3...
    if ansys_version:
        app_file = "cpython" + str(ansys_version)
    else:
        app_file = "cpython" + report_utils.ceiversion_apex_suffix()
    app = os.path.join(exec_basis, "bin", app_file)
    if is_windows:
        app += ".bat"
    # try the absolute name and if failing, assume it is in the PATH
    if not os.path.exists(app):
        app = app_file
    # run nexus_utility.py
    params = dict(
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, cwd=rptdir
    )
    # Build the command line
    cmd = [app]
    cmd.append(nexus_utility)
    # Use software OpenGL to work around platform issues (e.g. Qt requiring OpenGL)
    if use_software_gl:
        cmd.append("-X")
    cmd.extend(args)
    if is_windows:
        params["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.call(args=cmd, **params)


class Server:
    """
    Report Server interface.

    Implements REST protocols.
    """

    def __init__(self, url=None, username=None, password=None):
        self.cur_url = url
        self.cur_username = username
        self.cur_password = password
        self.cur_servername = None
        # These are used to simplify the non-EnSight API
        self._default_session = None
        self._default_dataset = None
        self._default_session_digest = ""
        self._default_dataset_digest = ""
        self._last_error = ""
        # track the target server's version
        self._api_version = None

        self._magic_token = None

        # Keep an http session around for caching and retries
        self._http_session = requests.Session()
        retry_strategy = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._http_session.mount("http://", adapter)
        self._http_session.mount("https://", adapter)

    @property
    def api_version(self):
        """Read only version var."""
        if self._api_version is None:
            self._api_version = float(self.get_api_version()["version"])
        return self._api_version

    @property
    def acls_enabled(self):
        """Read only var to check if server has acls turned ON."""
        # DO NOT CACHE THIS! If you do, that will require a restart
        # of the temp editor when the server changes the setting,
        # which we don't want.
        return self.get_api_version().get("acls", False)

    def generate_magic_token(self, max_age=None):
        url = self.get_URL()
        if url is None:
            raise Exception("No server URL selected")
        url += "/api/auth/magic-token/"
        data = {"username": self.get_username(), "password": self.get_password()}
        if max_age is not None:
            data["max_age"] = max_age
        headers = {"Content-type": "application/json", "Accept": "application/json"}
        r = self._http_session.post(url, data=json.dumps(data), headers=headers)
        if r.status_code == requests.codes.ok:
            return r.json().get("token")
        elif r.status_code == requests.codes.bad_request:
            raise Exception("Invalid credentials to request a magic token")
        else:
            raise Exception("Unable to access the remote report server")

    def _validate_magic_token(self, token):
        url = self.get_URL()
        if url is None:
            raise Exception("No server URL selected")
        url += "/api/auth/magic-token/verify/"
        headers = {"Content-type": "application/json", "Accept": "application/json"}
        r = self._http_session.post(url, data=json.dumps({"token": token}), headers=headers)
        if r.status_code == requests.codes.ok:
            return True
        elif r.status_code == requests.codes.bad_request:
            return False
        else:
            raise Exception("Unable to access the remote report server")

    @property
    def magic_token(self):
        # if token is None or token has expired
        # verify and regen automatically so the user does not need to worry about this.
        if self._magic_token is None or not self._validate_magic_token(self._magic_token):
            self._magic_token = self.generate_magic_token()
        return self._magic_token

    @magic_token.setter
    def magic_token(self, value):
        self._magic_token = value

    @classmethod
    def get_object_digest(cls, obj):
        m = hashlib.md5()
        m.update(pickle.dumps(obj))
        return m.digest()

    @classmethod
    def add_query_to_url(cls, url, query):
        if "?" in url:
            return url + "&" + query
        return url + "?" + query

    def set_URL(self, url):
        if url == self.cur_url:
            return
        self.cur_url = url
        self.cur_servername = None

    def get_URL(self):
        return self.cur_url

    def get_url_with_magic_token(self, url=None):
        if url is None:
            url = self.get_URL()
        return self.add_query_to_url(url, f"magic_token={self.magic_token}")

    def build_request_url(self, url):
        return self.get_URL() + url

    def set_username(self, u):
        self.cur_username = u

    def set_password(self, p):
        self.cur_password = p

    def get_username(self):
        return self.cur_username

    def get_password(self):
        return self.cur_password

    def get_last_error(self):
        s = self._last_error
        self._last_error = ""
        return s

    def valid_database(self):
        if self.cur_url and self.cur_url.startswith("http"):
            return True
        return False

    @disable_warn_logging
    def get_api_version(self):
        url = self.get_URL()
        if url is None:
            raise Exception("No server URL selected")
        url += "/item/api_version/"
        auth = self.get_auth()
        r = self._http_session.get(url, auth=auth)
        if r.status_code == requests.codes.ok:
            return r.json()
        elif r.status_code == requests.codes.forbidden:
            raise exceptions.PermissionDenied("Invalid credentials to access the report server")
        else:
            raise Exception("Unable to access the remote report server")

    def get_server_name(self):
        if self.cur_servername is None:
            try:
                self.validate()
            except Exception:
                pass
        if self.cur_servername is None:
            return self.get_URL()
        return self.cur_servername

    def validate(self):
        server_info = self.get_api_version()
        if "server_name" in server_info:
            self.cur_servername = server_info["server_name"]
        self._api_version = float(server_info["version"])
        return self._api_version

    def stop_server_allowed(self):
        # this call uses the api_stop_local_test REST call to check to see
        # if the server can be shutdown by this user
        url = self.get_URL()
        if url is None:
            return False
        url += "/item/api_stop_local_test/"
        auth = self.get_auth()
        try:
            result = self._http_session.get(url, auth=auth)
            if not result.ok:
                return False
        except Exception:
            return False
        return True

    def stop_local_server(self):
        url = self.get_URL()
        if url is None:
            raise Exception("No server URL selected")
        url += "/item/api_stop_local/"
        auth = self.get_auth()
        try:
            # note this request will fail as it does not return anything!!!
            self._http_session.get(url, auth=auth)
        except Exception:
            pass
        self.set_URL(None)
        self.set_password(None)
        self.set_username(None)

    def get_auth(self):
        if self.cur_username and self.cur_password and (len(self.cur_username) > 0):
            return (self.cur_username.encode("utf-8"), self.cur_password.encode("utf-8"))
        return None

    def get_user_groups(self):
        if not self.valid_database():
            return []
        obj_uri = "/api/user-groups/"
        uri = self.build_request_url(obj_uri)
        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            return []
        try:
            return [str(obj_data.get("name")) for obj_data in r.json()]
        except Exception:
            return []

    def get_object_guids(self, objtype=report_objects.Template, query=None):
        if not self.valid_database():
            return []
        obj_uri = objtype.get_list_url()
        uri = self.build_request_url(obj_uri)
        new_api = "/api/" in uri
        if new_api:
            uri = self.add_query_to_url(uri, "fields=guid")
        else:
            uri = self.add_query_to_url(uri, "guidsonly=1")
        # treat None and "" as having no query specified
        if query:
            # translate raw queries into URL savvy text
            tmp = query.strip("\"'").replace("|", "%7C").replace(";", "%3B").replace("#", "%23")
            uri = self.add_query_to_url(uri, f"query={tmp}")
        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            return []
        try:
            if new_api:
                return [str(obj_data.get("guid")) for obj_data in r.json()]
            else:
                return [str(i) for i in r.json()["guid_list"]]
        except Exception:
            return []

    def get_objects(self, objtype=report_objects.Template, query=None):
        if not self.valid_database():
            return []
        if inspect.ismethod(objtype):
            obj_uri = getattr(
                inspect.getmodule(objtype),
                objtype.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0],
            ).get_list_url()
        else:
            obj_uri = objtype.get_list_url()
        uri = self.build_request_url(obj_uri)
        # treat None and "" as having no query specified
        if query:
            # translate raw queries into URL savvy text
            tmp = query.strip("\"'").replace("|", "%7C").replace(";", "%3B").replace("#", "%23")
            uri = self.add_query_to_url(uri, f"query={tmp}")

        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            return []
        try:
            ret = []
            for d in r.json():
                if inspect.ismethod(objtype):
                    t = objtype(d)
                else:
                    t = objtype()
                t.server_api_version = self.api_version
                t.from_json(d)
                ret.append(t)
            return ret
        except Exception:
            return []

    def get_object_from_guid(self, guid, objtype=report_objects.TemplateREST):
        if not self.valid_database():
            return None
        obj = objtype()
        obj.guid = guid
        obj_uri = obj.get_detail_url()
        uri = self.build_request_url(obj_uri)
        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            if r.status_code == requests.codes.forbidden:
                raise exceptions.PermissionDenied(
                    r.json().get("detail", "You do not have permission to perform this action.")
                )

            return None
        try:
            if inspect.ismethod(objtype):
                obj = objtype(r.json())
            obj.server_api_version = self.api_version
            obj.from_json(r.json())
            return obj
        except Exception:
            return None

    def _get_push_request_info(self, obj):
        """
        So we have been using PUT requests for both POST and PUT operations, which is
        wrong and an anti-pattern.

        As a starting point to fix this,
        we are moving towards doing the right thing beginning with
        ItemCategoryREST objects. We introduce a flag `saved` in the baseREST
        obj which will be used to identify if an obj we have was already
        saved/pushed or not. Based on this check, we return the right request.<method>
        :param obj:
        :return:
        """
        if hasattr(obj, "server_api_version"):  # only items; skip templates, etc.
            # if the object server version and the current server version do
            # not match, convert them (if possible)
            if (obj.server_api_version is not None) and (obj.server_api_version < self.api_version):
                obj.update_api_version(self.api_version)

        obj_uri, obj_data = obj.get_url_data()
        uri = self.build_request_url(obj_uri)
        new_api = "/api/" in uri
        if new_api:
            # in future, this will be applicable to all REST APIs
            if obj.saved:
                # if it was already saved, it should be an update.
                method = self._http_session.put
            else:
                method = self._http_session.post
        else:
            # to maintain backwards compat with existing/old REST APIs
            method = self._http_session.put

        return method, uri, obj_data

    def put_objects(self, in_objects):
        if not self.valid_database():
            return requests.codes.service_unavailable
        objects = in_objects
        if not isinstance(in_objects, collections.abc.Iterable):
            objects = [in_objects]
        # Pre-screen the object list.  If any of the objects reference the
        # current session or dataset and they have not yet been pushed or
        # have changed from the last time they were pushed, push them first...
        session = self.get_default_session()
        session_digest = Server.get_object_digest(session)
        dataset = self.get_default_dataset()
        dataset_digest = Server.get_object_digest(dataset)
        # only do this if either the session or dataset have changed from the last push...
        if (session_digest != self._default_session_digest) or (
            dataset_digest != self._default_dataset_digest
        ):
            for o in objects:
                if isinstance(o, report_objects.ItemREST):
                    if (o.session == session.guid) and (
                        session_digest != self._default_session_digest
                    ):
                        error = self.put_objects([session])
                        if error != requests.codes.ok:
                            return error
                        self._default_session_digest = session_digest
                    if (o.dataset == dataset.guid) and (
                        dataset_digest != self._default_dataset_digest
                    ):
                        error = self.put_objects([dataset])
                        if error != requests.codes.ok:
                            return error
                        self._default_dataset_digest = dataset_digest
        # ok, push the real objects...

        auth = self.get_auth()
        success = requests.codes.ok
        for o in objects:
            request_method, uri, obj_data = self._get_push_request_info(o)
            # the new way of json dumping before push might break older APIs so we
            # fall back to the older way.
            if self.api_version < 1:
                data = obj_data
                headers = {}
            else:
                # we need this because we now push complex structures.
                data = json.dumps(obj_data, cls=BaseEncoder)
                headers = {"Content-type": "application/json", "Accept": "application/json"}
            # Push the object
            try:
                r = request_method(uri, auth=auth, data=data, headers=headers)
            except Exception as e:
                if print_allowed():
                    print(f"Unable to push object {o}: {e}")
                raise

            # One special case: perhaps the session/dataset was deleted and the cache not invalidated?
            # In this case, we would get a 400 back and the response text would include 'Invalid pk'.  So,
            # we try to push the dataset and session again and then re-push the object.  Only try this once!
            if r.status_code == requests.codes.bad_request:  # pragma: no cover
                if isinstance(o, report_objects.ItemREST):
                    if "Invalid pk" in r.text:
                        repushed = False
                        if o.session == session.guid:
                            error = self.put_objects([session])
                            if error != requests.codes.ok:
                                return error
                            repushed = True
                        if o.dataset == dataset.guid:
                            error = self.put_objects([dataset])
                            if error != requests.codes.ok:
                                return error
                            repushed = True
                        # try one more time..
                        if repushed:
                            r = request_method(uri, auth=auth, data=data, headers=headers)
                else:
                    # the likely case here is that the session/dataset are no longer valid
                    self._last_error = r.text
                    return r.status_code
            elif r.status_code == requests.codes.forbidden:
                raise exceptions.PermissionDenied(
                    r.json().get("detail", "You do not have permission to perform this action.")
                )

            # do we need to push a file?
            file_data = o.get_url_file()
            if file_data:
                files = {"file": (file_data[1], file_data[2])}
                url = self.cur_url + file_data[0]
                try:
                    r = self._http_session.put(url, auth=auth, files=files)
                except Exception:
                    r = self._http_session.Response()
                    r.status_code = requests.codes.client_closed_request
            ret = r.status_code
            # we map 201 (created) to 200 (ok) to simplify error handling...
            if ret == requests.codes.created:
                ret = requests.codes.ok
            # we map 202 (accepted) to 200 (ok) to simplify error handling...
            if ret == requests.codes.accepted:
                ret = requests.codes.ok
            # record and errors
            if ret != requests.codes.ok:
                if ret == requests.codes.forbidden:
                    raise exceptions.PermissionDenied(
                        r.json().get("detail", "You do not have permission to perform this action.")
                    )

                self._last_error = r.text
                success = ret
        return success

    def del_objects(self, in_objects):
        if not self.valid_database():
            return requests.codes.service_unavailable
        objects = in_objects
        if not isinstance(in_objects, collections.abc.Iterable):
            objects = [in_objects]
        auth = self.get_auth()
        success = requests.codes.ok
        for o in objects:
            obj_uri, obj_data = o.get_url_data()
            uri = self.build_request_url(obj_uri)
            # delete the object
            r = self._http_session.delete(uri, auth=auth)
            ret = r.status_code
            # the output should be 204 no_content
            if ret != requests.codes.no_content:
                if ret == requests.codes.forbidden:
                    raise exceptions.PermissionDenied(
                        r.json().get("detail", "You do not have permission to perform this action.")
                    )
                success = ret
        return success

    def get_file(self, obj, fileobj):
        if self.valid_database():
            file_url = getattr(obj, "fileurl", None)
            if file_url is not None:
                # get the file
                r = report_utils.run_web_request("GET", self, file_url, stream=True)
                if r is not None:
                    if r.status_code == requests.codes.ok:
                        for chunk in r.iter_content(1024):
                            fileobj.write(chunk)
                    return r.status_code

        return requests.codes.service_unavailable

    # this method will copy all of the object (obj_type=class) that
    # match the passed query into this (self) database...
    # Allowed obj_type are "item", "template"...
    # the progress object must implement the QtProgressDialog interface methods:
    # setLabelText(), setMaximum(), setValue()
    # if progress_qt is True, text strings will be translated, etc.  Otherwise,
    # the same method are called, but w/o Qt use.
    def copy_items(
        self, source, obj_type="item", query=None, progress=None, categories=None, progress_qt=True
    ):
        copy_list = []
        # get the items to copy...
        if obj_type == "item":
            # basic objects
            objs = source.get_objects(objtype=report_objects.ItemREST, query=query)
            for o in objs:
                if categories:
                    o.categories = categories
                copy_list.append(o)
            # now the associated datasets
            dataset_set = set()
            session_set = set()
            for o in copy_list:
                dataset_set.add(o.dataset)
                session_set.add(o.session)
            nobjs = len(dataset_set) + len(session_set)
            n = 0
            if progress:
                text = "Scanning datasets..."
                if progress_qt:
                    text = QtWidgets.QApplication.translate("nexus", "Scanning datasets...")
                progress.setLabelText(text)
                progress.setMaximum(nobjs)
                progress.setValue(n)
            for guid in dataset_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.DatasetREST)
                if obj:
                    copy_list.insert(0, obj)
                n += 1
                if progress:
                    progress.setValue(n)
            # now the associated sessions
            if progress:
                text = "Scanning sessions..."
                if progress_qt:
                    text = QtWidgets.QApplication.translate("nexus", "Scanning sessions...")
                progress.setLabelText(text)
            for guid in session_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.SessionREST)
                if obj:
                    copy_list.insert(0, obj)
                n += 1
                if progress:
                    progress.setValue(n)
        elif obj_type == "template":
            # get the selected templates
            if progress:
                text = "Scanning templates..."
                if progress_qt:
                    text = QtWidgets.QApplication.translate("nexus", "Scanning templates...")
                progress.setLabelText(text)
            objs = source.get_objects(objtype=report_objects.TemplateREST, query=query)
            # record all of the GUIDs we currently have...
            copy_set = set()
            for o in objs:
                copy_list.append(o)
                copy_set.add(o.guid)
            # expand to the parent/children, looking for GUIDs we need...
            while True:
                add_set = set()
                for o in copy_list:
                    if o.parent:
                        if o.parent not in copy_set:
                            add_set.add(o.parent)
                    o.reorder_children()
                    for c in o.children:
                        if c not in copy_set:
                            add_set.add(c)
                # are we done?
                if len(add_set) == 0:
                    break
                for guid in add_set:
                    obj = source.get_object_from_guid(guid, objtype=report_objects.TemplateREST)
                    if obj:
                        copy_list.append(obj)
                    copy_set.add(guid)  # we at least tried, so avoid infinite loop...
            # It takes two passes to save templates, once without children and once with
            # The common case will handle the latter, so we handle the former here
            nobjs = len(copy_list)
            n = 0
            success = requests.codes.ok
            for obj in copy_list:
                if progress:
                    progress.setValue(n)
                    if progress_qt:
                        if progress.wasCanceled():
                            return False
                tmp_parent = obj.parent
                obj.parent = None
                tmp_children = obj.children
                obj.children = []
                ret = self.put_objects([obj])
                if ret != requests.codes.ok:
                    success = ret
                obj.parent = tmp_parent
                obj.children = tmp_children
                n += 1
            if progress:
                progress.setValue(nobjs)
            if success != requests.codes.ok:
                return False
        # Ok, put the object in the new database...
        # The progress bar should not include the secondary types: sessions, datasets
        skip_count_types = [report_objects.DatasetREST, report_objects.SessionREST]
        nobjs = 0
        for obj in copy_list:
            if type(obj) not in skip_count_types:
                nobjs += 1
        n = 0
        if progress:
            if progress_qt and has_qt:
                s = QtWidgets.QApplication.translate("nexus", "Importing:")
                s += report_utils.from_local_8bit(obj_type)
            else:
                s = f"Importing: {obj_type}"
            progress.setLabelText(s)
            progress.setMaximum(nobjs)

        for obj in copy_list:
            try:
                if progress:
                    progress.setValue(n)
                    if progress_qt:
                        if progress.wasCanceled():
                            return False
                # special case for items with file payloads
                file_url = getattr(obj, "fileurl", None)
                if file_url:
                    # need to pull the file from this url...
                    obj.fileobj = tempfile.NamedTemporaryFile()
                    if source.get_file(obj, obj.fileobj) != requests.codes.ok:
                        obj.fileobj = None
                self.put_objects([obj])
                # clean up temp file
                fileobj = getattr(obj, "fileobj", None)
                if fileobj:
                    fileobj.close()
                if type(obj) not in skip_count_types:
                    n += 1
            except Exception as e:
                if print_allowed():
                    print(f"Failure while copying {obj}: {e}")
                return False
        if progress:
            progress.setValue(nobjs)
        return True

    # The server class is the basis of the non-EnSight API
    # to simplify the API, the server maintains a current
    # session and dataset object.  The user may modify these
    # objects and if they do a put on items that reference these
    # objects, they will be automatically pushed as well.
    def get_default_session(self):
        if not self._default_session:
            self._default_session = report_objects.SessionREST()
            self._default_session_digest = ""
            self._default_session.application = "Nexus Python API"
            self._default_session.version = "1.0"
            self._default_session.hostname = platform.node()
            self._default_session.platform = report_utils.enve_arch()
        return self._default_session

    def set_default_session(self, session, validate_digest=False):
        if not isinstance(session, report_objects.SessionREST):
            raise ValueError("Session must be an instance of report_objects.SessionREST")
        self._default_session = session
        self._default_session_digest = ""
        if validate_digest:
            self._default_session_digest = self.get_object_digest(self._default_session)

    def get_default_dataset(self):
        if not self._default_dataset:
            self._default_dataset = report_objects.DatasetREST()
            self._default_dataset_digest = ""
            self._default_dataset.format = "none"
            self._default_dataset.filename = "none"
        return self._default_dataset

    def set_default_dataset(self, dataset, validate_digest=False):
        if not isinstance(dataset, report_objects.DatasetREST):
            raise ValueError("Dataset must be an instance of report_objects.DatasetREST")
        self._default_dataset = dataset
        self._default_dataset_digest = ""
        if validate_digest:
            self._default_dataset_digest = self.get_object_digest(self._default_dataset)

    def create_item_category(self, name="New category"):
        """Create a new item category."""
        item_categ = report_objects.ItemCategoryREST()
        if name:
            item_categ.name = name
        return item_categ

    def create_item(self, name="Unnamed Item", source="Nexus Python API", sequence=0):
        item = report_objects.ItemREST()
        # the item needs to know the current server's api version
        # in order to determine how to parse the server's response
        item.server_api_version = self.api_version
        item.dataset = self.get_default_dataset().guid
        item.session = self.get_default_session().guid
        if name:
            item.name = name
        if source:
            item.source = source
        if sequence:
            item.sequence = sequence
        return item

    def create_template(self, name="New Template", parent=None, report_type="Layout:basic"):
        """
        Method to create a new template Input parameters:

        name:  name of the template to create
        parent: template to use as the parent of the new template
        report_type: type of report
        """
        templ = report_objects.TemplateREST.factory({"report_type": report_type})
        templ.report_type = report_type
        if name:
            templ.name = name
        if parent is not None:
            parent.children.append(templ.guid)
            templ.parent = parent.guid
        return templ

    def _download_report(self, url, file_name, directory_name=None):
        resp = requests.get(url, allow_redirects=True)
        # get abs path
        if directory_name:
            file_path = (Path(directory_name) / Path(file_name)).resolve()
        else:
            file_path = Path(file_name).resolve()
        # write to disk
        with open(file_path, "wb") as report:
            report.write(resp.content)

    def build_url_with_query(self, report_guid, query, rest_api=False):
        url = self.get_URL()
        if rest_api:
            url += f"/api/generate-report/?view={str(report_guid)}"
        else:
            url += f"/reports/report_display/?view={str(report_guid)}"
        for key in query:
            value = query[key]
            if value is None:
                url += f"&{key}"
            else:
                url += f"&{key}={value}"
        return url

    def export_report_as_html(
        self, report_guid, directory_name, query=None, filename="index.html", no_inline_files=False
    ):
        if query is None:
            query = {}
        query["print"] = "html"
        directory_path = os.path.abspath(directory_name)
        from ansys.dynamicreporting.core.utils.report_download_html import ReportDownloadHTML

        url = self.build_url_with_query(report_guid, query)
        worker = ReportDownloadHTML(
            url=url, directory=directory_path, filename=filename, no_inline_files=no_inline_files
        )
        worker.download()

    def export_report_as_pdf(
        self,
        report_guid,
        file_name,
        query=None,
        page=None,
        parent=None,
        delay=None,
        exec_basis=None,
        ansys_version=None,
    ):
        if query is None:
            query = {}
        query["print"] = "pdf"
        url = self.build_url_with_query(report_guid, query)
        file_path = os.path.abspath(file_name)
        if has_qt and (parent is not None):
            from .report_download_pdf import NexusPDFSave

            app = QtGui.QGuiApplication.instance()
            worker = NexusPDFSave(app)
            _ = worker.save_page_pdf(url, filename=file_path, page=page, delay=delay)
            return

        # ok, there is a bug in the 3.7 implementation of subprocess where
        # args are not properly encoded under Windows.  To pass a URL, you
        # cannot use '?' and '&' chars.  So, we support base64 encodes
        # of the URLs here...
        url = report_utils.encode_url(url)
        cmd = ["report_save_pdf", url, file_path]
        if page is not None:
            page_string = "X".join(str(x) for x in page)
            cmd.append(page_string)
        if delay is not None:
            cmd.append(str(delay))
        run_nexus_utility(
            cmd, use_software_gl=True, exec_basis=exec_basis, ansys_version=ansys_version
        )

    def export_report_as_pptx(self, report_guid, file_name, query=None):
        """Method to export a report template with guid of report_guid as a pptx file of
        name file_name."""
        if query is None:
            query = {}
        query["format"] = "pptx"
        url = self.build_url_with_query(report_guid, query, rest_api=True)
        self._download_report(url, file_name)

    def get_pptx_from_report(self, report_guid, directory_name=None, query=None):
        """
        Method to scrape and download pptx files from a report.

        Since PPTX Templates are well, templates, there can be many of them possibly
        organized in a parent-child hierarchy within a report. Here, we scrape links to
        pptx files in the report and download them to the user specified directory.
        """
        if query is None:
            query = {}
        url = self.build_url_with_query(report_guid, query)
        resp = requests.get(url, allow_redirects=True)
        if resp.status_code == requests.codes.ok:
            try:
                links = report_utils.get_links_from_html(resp.text)
                for link in links:
                    url = urlparse(link)
                    q_params = dict(urllib.parse.parse_qsl(url.query))
                    file_format = q_params.get("format")
                    if file_format != "pptx":
                        continue
                    self._download_report(link, q_params["filename"], directory_name=directory_name)
            except Exception as e:
                print(f"Unable to get pptx from report '{report_guid}': {e}")
        else:
            raise Exception(f"The server returned an error code {resp.status_code}")


def create_new_local_database(
    parent,
    directory="",
    return_info=None,
    run_local=False,
    raise_exception=False,
    exec_basis=None,
    ansys_version=None,
):
    """Create a new, empty sqlite database  If parent is not None, a QtGui will be
    used."""
    if parent and has_qt:  # pragma: no cover
        title = QtWidgets.QApplication.translate(
            "nexus", "Select an empty folder to create the database in"
        )
        fn = QtWidgets.QFileDialog.getExistingDirectory(parent, title, directory)
        if len(fn) == 0:
            return False
        db_dir = QtCore.QFileInfo(fn).absoluteFilePath()
    else:
        db_dir = os.path.abspath(directory)

    # if the directory does not exist, make it...
    try:
        # this will throw if it fails or if the directory already exists...
        os.makedirs(db_dir)
    except OSError as e:
        if not os.path.isdir(db_dir):
            if parent and has_qt:  # pragma: no cover
                msg = QtWidgets.QApplication.translate(
                    "nexus", "The selected directory could not be accessed."
                )
                QtWidgets.QMessageBox.critical(
                    parent,
                    QtWidgets.QApplication.translate("nexus", "Invalid database location"),
                    msg,
                )

            if raise_exception:
                raise exceptions.DBDirNotCreatedError(
                    f"The selected directory did not exist and an attempt to create"
                    f" it failed: {e}"
                )

            return False

    # we do not expect to see: 'db.sqlite3' or 'media' in this folder
    if os.path.isdir(os.path.join(db_dir, "media")) or os.path.isfile(
        os.path.join(db_dir, "db.sqlite3")
    ):
        if parent and has_qt:
            msg = QtWidgets.QApplication.translate(
                "nexus", "The selected directory already appears to have a database in it."
            )
            QtWidgets.QMessageBox.critical(
                parent, QtWidgets.QApplication.translate("nexus", "Invalid database location"), msg
            )

        if raise_exception:
            raise exceptions.DBExistsError(
                "The selected directory already appears to have a database in it"
            )

        return False

    # Check for Linux TZ issue
    report_utils.apply_timezone_workaround()

    try:
        if run_local:
            # Make a random string that could be used as a secret key for the database
            # take two UUID1 values, run them through md5 and concatenate the digests.
            secret_key = hashlib.md5(uuid.uuid1().bytes).hexdigest()
            secret_key += hashlib.md5(uuid.uuid1().bytes).hexdigest()
            # And make a target file (.nexdb) for auto launching of the report viewer...
            f = open(os.path.join(db_dir, "view_report.nexdb"), "w")
            if len(secret_key):
                f.write(secret_key)
            f.close()
            srcdir = os.path.join(
                report_utils.enve_home(), "nexus" + report_utils.ceiversion_nexus_suffix(), "django"
            )
            # In Python 3, we use the migration command to build the new database file and add the 'nexus'
            # superuser programmatically.  We Also stamp the current csf version into the media directory.
            os.environ["CEI_NEXUS_SECRET_KEY"] = secret_key
            os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = db_dir
            os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = db_dir
            os.environ["CEI_NEXUS_LOCAL_ALLOW_REMOTE_ACCESS"] = "1"
            os.environ["CEI_NEXUS_SERVE_STATIC_FILES"] = "1"
            os.environ["DJANGO_SETTINGS_MODULE"] = "ceireports.settings"
            # make it possible to import ceireports.settings
            if srcdir not in sys.path:
                sys.path.append(srcdir)
            error = False
            if parent and has_qt:
                QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
            try:
                import django

                django.setup()
                from django.core import management

                management.call_command("migrate")
                from django.contrib.auth.models import Group, Permission, User

                # Super user
                User.objects.create_superuser("nexus", "", "cei")
                user = User.objects.get(username="nexus")
                # Nexus group with all permissions
                group = Group.objects.create(name="nexus")
                for p in Permission.objects.all():
                    group.permissions.add(p)
                # and the nexus user
                group.user_set.add(user)
                group.save()
                os.makedirs(os.path.join(db_dir, "media"))
                from ansys.nexus.core.geofile_processing import do_geometry_update_check

                do_geometry_update_check()
            except Exception:
                error = True
            if parent and has_qt:
                QtWidgets.QApplication.restoreOverrideCursor()
            # Unset the environmental vars...
            os.environ.pop("CEI_NEXUS_SECRET_KEY")
            os.environ.pop("CEI_NEXUS_LOCAL_DB_DIR")
            os.environ.pop("CEI_NEXUS_LOCAL_MEDIA_DIR")
            os.environ.pop("CEI_NEXUS_LOCAL_ALLOW_REMOTE_ACCESS")
            os.environ.pop("CEI_NEXUS_SERVE_STATIC_FILES")
            os.environ.pop("DJANGO_SETTINGS_MODULE")
            if error:
                raise RuntimeError("Unable to generate a new database by migration.")
        else:
            # Run the nexus_utility.py script with the command 'create_new_database'
            # This will route back to this exact same code (in a different process) with
            # the run_local variable set to True.
            #
            # If you connect to a Nexus version 232 or prior, the database path is expected
            # as normal. From 241 on, the database path is expected to be encoded. So
            # a version check is needed to decide if we should encode db_dir or not.
            if ansys_version:
                report_ver = int(ansys_version)
            else:
                report_ver = int(report_utils.ceiversion_nexus_suffix())
            if report_ver > 240:
                db_dir_encoded = report_utils.encode_url(db_dir)
            else:
                db_dir_encoded = db_dir
            run_nexus_utility(
                ["create_new_database", db_dir_encoded],
                exec_basis=exec_basis,
                ansys_version=ansys_version,
            )

    except Exception as e:
        if parent and has_qt:
            msg = QtWidgets.QApplication.translate(
                "nexus", "The creation of a new, local database failed with the error:"
            )
            QtWidgets.QMessageBox.critical(
                parent,
                QtWidgets.QApplication.translate("nexus", "Database creation failed"),
                msg + str(e),
            )

        if raise_exception:
            raise exceptions.DBCreationFailedError(
                f"The creation of a new, local database failed with the error:{e}"
            )

        return False

    if type(return_info) == dict:
        return_info["directory"] = db_dir
        return True

    if parent and has_qt:
        msg = QtWidgets.QApplication.translate(
            "nexus", "A new Nexus database has been created in the folder:"
        )
        QtWidgets.QMessageBox.information(
            parent,
            QtWidgets.QApplication.translate("nexus", "Database creation successful"),
            msg + str(db_dir),
        )
    return True


# Utility method for killing a local server at Python exit...
def stop_background_local_server(server_dirname: str, reason: str = "pythonserverapi_atexit"):
    # write a shutdown file into the directory and let the core handle it...
    pathname = os.path.join(server_dirname, "shutdown")
    try:
        with open(pathname, mode="w", encoding="utf8") as f:
            f.write(reason)
    except Exception as e:
        if print_allowed():
            print(
                f"Error: unable to cause the Nexus server in {server_dirname} to shutdown.\n{str(e)}"
            )
    # Wait for the status file to be removed.  One of the last steps in
    # the Nexus server shutdown sequence is to remove this file.  We will
    # give it a minute or so to respond before returning.
    pathname = os.path.join(server_dirname, "nexus.status")
    start_time = time.time()
    while (time.time() - start_time) < 120.0:
        # if the file is removed, we will assume the server is shutdown
        if not os.path.isfile(pathname):
            break
        # don't burn up a CPU
        time.sleep(0.01)


# Delete the database
def delete_database(db_dir: str):
    # Delete the database directory and all its content
    if not validate_local_db(db_dir):
        # Validate the directory database before deleting it
        if print_allowed():
            print(f"Error: we are asked to delete the database but {db_dir} is not a database dir")
    else:
        try:
            # Check if there is a nexus.status file. If yes, it means there is a Nexus service running on that
            # database. Check if the hostname matches the local machine. If not, do not delete the database
            # If it's the same, give it some time for the service to shut down. If in this window of time the
            # nexus.status file is finally deleted, now delete the database directory.
            marked_to_delete = True
            pathname = os.path.join(db_dir, "nexus.status")
            if os.path.isfile(pathname):
                marked_to_delete = False  # assume something is wrong.
                fp = open(pathname, encoding="utf8")
                config = configparser.ConfigParser(interpolation=None)
                config.read_file(fp, source=pathname)
                if config.has_section("system"):
                    if config.has_option("system", "hostname"):
                        if config.get("system", "hostname") == platform.node():
                            marked_to_delete = True
            if marked_to_delete:
                start_time = time.time()
                while (time.time() - start_time) < 120.0:
                    time.sleep(0.01)
                    if not os.path.isfile(pathname):
                        shutil.rmtree(db_dir, ignore_errors=True)
                        if not os.path.isdir(db_dir):
                            # If db_dir does not exist any more, exit. Otherwise, stay in the while loop
                            break
        except Exception as e:
            if print_allowed():
                print(f"Error: can not delete {db_dir} with error:\n{str(e)}")


def validate_local_db_version(db_dir, version_max=None, version_min=None):
    """
    Check the version number from the file in the media directory
    :param db_dir: The directory to check the version number of
    :param version_max: The maximum version number supported
    :param version_min: The minimum version number supported
    :return: True if the database version number is valid
    """
    if version_min is None:
        version_min = -1.0
    if version_max is None:
        version_max = float(report_utils.ceiversion_nexus_suffix()) / 10.0  # 201 -> 20.1
    version_file = os.path.join(os.path.abspath(db_dir), "media", "csf_conversion_version")
    if not os.path.isfile(version_file):
        return True
    try:
        with open(version_file) as f:
            # String will have the form:  xy.z0 or xy.z0Rq
            # we compare vs xy.z portion of the float which is the release version
            # the Rq portion is used to allow for multiple revisions during development
            number = float(f.readline().split("R")[0])
            if number > version_max:
                return False
            if number < version_min:
                return False
    except Exception:
        return False
    return True


def validate_local_db(db_dir, version_check=False, version_max=None, version_min=None):
    """
    Verify that the database directory contains the sqlite database file and a media
    directory By default, the version number is not checked.

    If one wants the version number checked,
    the parameter should be set to the maximum allowed version number (float).
    :param db_dir: The directory to check the version number of
    :param version_check: If true, check the release number
    :param version_max: The maximum version number supported (defaulted to validate_local_db_version)
    :param version_min: The minimum version number supported (defaulted to validate_local_db_version)
    :return: True if the database is valid
    """
    database_dir = os.path.abspath(db_dir)
    if not os.path.isfile(os.path.join(database_dir, "db.sqlite3")):
        return False
    if not os.path.isdir(os.path.join(database_dir, "media")):
        return False
    if version_check:
        if not validate_local_db_version(
            database_dir, version_max=version_max, version_min=version_min
        ):
            return False
    return True


def launch_local_database_server(
    parent,
    directory="",
    no_directory_prompt=False,
    port=8000,
    connect=None,
    terminate_on_python_exit=False,
    delete_db_on_python_exit=False,
    username="nexus",
    password="cei",
    verbose=True,
    return_info=None,
    use_debug=False,
    raise_exception=False,
    use_system_tray=None,
    server_timeout=180.0,
    parent_process=None,
    exec_basis=None,
    ansys_version=None,
    **kwargs,
):
    """
    Start up a local Django server for a local sqlite file.  If parent is not None, a
    QtGui will be used to fill in missing inputs.  By default, if
    terminate_on_python_exit is False and a Qt parent has been specified, the server
    launched will include an icon and menu in the system tray, making it possible for a
    user to stop the server via a GUI.  If use_system_tray is set to True or False, it
    will be used to override the interpretation of terminate_on_python_exit as a flag
    for the system tray.

    :param parent:  If using Qt, this is the parent to all Qt dialogs.  In non-Qt cases, None should be passed.
    :param str directory: The database directory to launch the server from.
    :param bool no_directory_prompt: Do not prompt the user for a directory if a parent is specified.
    :param int port: The default port to start the server on.  0=select one dynamically.
    :param Server connect: If set to a Server instance, fill in the URL and other details for the launched server.
    :param bool terminate_on_python_exit: If True, the server will be killed via Python atexit() method.
    :param bool delete_db_on_python_exit: if True and also terminate_on_python_exit True, the database will
        be deleted via Python atexit() method.
    :param str username: The username to access the database with
    :param str password: The password to access the database with
    :param bool verbose: If True, increase the verbosity of output
    :param dict return_info: If set to a dictionary, will return the 'directory' and 'port' of the launched server.
    :param bool use_debug: If True, the server will be run in debug mode.
    :param bool raise_exception: If True, the function will raise exceptions on errors instead of returning False
    :param bool use_system_tray: If True (and parent is not None), a GUI will be placed in the system tray.  See above.
    :param float server_timeout: Number of seconds to continue to try to connect to the new server before giving up.
    :param int parent_process: If provided, when the specified process id terminates, stop the Nexus server.

    :param int instance_count: Number of Nexus server instances [1-10] to launch
    :param str server_hostname: Hostname to run the server on (external hostname)
    :param int internal_base_port: Port number base to allocate server instances, etc.  0=select dynamically
    :param bool remote_session: Enable/disable remote sessions Default: False.
    :param int local_sessions_ensight: Number of simultaneous local EnSight sessions to allow. Default: 0.
    :param int local_sessions_envision: Number of simultaneous local EnVision sessions to allow. Default: 0.
    :param str server_name: Human readable name to use for the database.
    :param str postgresql_url: URL to the PostgreSQL database to use: "postgresql://user:password@host:port/database"
    :param bool acls: Enable/disable per-item ACL functionality (default: False).
    :param bool allow_remote_access: If False, access to the server will only be allowed from localhost.
    :param bool allow_iframe_embedding: Allow Nexus pages to be displayed in iframes (default: False).
    :param int max_upload_size: Maximum size of a data item upload in megabytes [1,20000] (default: 5000).
    :param str exec_basis: path to the CEI installation to use for the nexus_launcher command.
    :param ansys_version int: version corresponding to the launcher

    :return bool: True on success and False on failure.

    :raises: TypeError, ServerPortUnavailableError, DBNotFoundError, ServerPortInUseError,
        ServerLaunchError, ServerConnectionError
    """

    # Valid kwargs keys
    valid_keys = [
        "instance_count",
        "server_hostname",
        "internal_base_port",
        "remote_session",
        "local_sessions_ensight",
        "local_sessions_envision",
        "server_name",
        "postgresql_url",
        "acls",
        "allow_remote_access",
        "allow_iframe_embedding",
        "max_upload_size",
    ]
    # convert kwargs into a settings override dictionary
    settings = dict()
    for key, value in kwargs.items():
        if key not in valid_keys:
            if raise_exception:
                raise TypeError(f'Unknown keyword: "{key}"')
            else:
                return False
        else:
            # integers are valid, bool -> true,false, skip None
            if type(value) is int:
                settings[key] = str(value)
            elif type(value) is bool:
                settings[key] = str(value).lower()
            elif value is not None:
                settings[key] = str(value)

    if return_info is None:
        return_info = dict()

    # Check for Linux TZ issue
    report_utils.apply_timezone_workaround()

    # Try to use a lock file to prevent port scanning collisions
    # We create a lockfiles in the user's home directory.  Under windows, we use LOCALAPPDATA to avoid
    # the case where a home dir may be mounted remotely, potentially causing permission issues when writing.
    # On all other OSes we fall back to ~
    homedir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    api_lock_filename = os.path.join(homedir, ".nexus_api.lock")
    # Nexus uses two lockfiles:
    #    .nexus.lock is held whenever port scanning is going on.  It can be held by this function or by nexus_launcher
    #    .nexus_api.lock is used by the Python API to ensure exclusivity (e.g. while a server is launching)
    local_lock = None
    try:
        # create a file lock
        local_lock = filelock.nexus_file_lock(api_lock_filename)
        local_lock.acquire()
    except Exception:
        pass
    # We may need to do port scanning
    if port is None:
        lock_filename = os.path.join(homedir, ".nexus.lock")
        scanning_lock = None
        try:
            # create a file lock
            scanning_lock = filelock.nexus_file_lock(lock_filename)
            scanning_lock.acquire()
        except Exception:
            pass
        # Note: QWebEngineView cannot access http over 65535, so limit ports to 65534
        ports = report_utils.find_unused_ports(1)
        port = -1
        if ports:
            port = ports[0]

        if scanning_lock:
            scanning_lock.release()
        if port == -1:
            if raise_exception:
                raise exceptions.ServerPortUnavailableError(
                    "Unable to find an unused port to run the server"
                )
            return False

    # Handle the directory
    if parent and has_qt:  # pragma: no cover
        # skip the directory prompt if directory is valid
        if no_directory_prompt:
            db_dir = os.path.abspath(directory)
        else:
            f = QtWidgets.QApplication.translate("nexus", "Nexus database (db.sqlite3)")
            fn = QtWidgets.QFileDialog.getOpenFileName(
                parent,
                QtWidgets.QApplication.translate("nexus", "Select the database file"),
                directory,
                f,
                f,
                QtWidgets.QFileDialog.DontConfirmOverwrite,
            )[0]
            if len(fn) == 0:
                if local_lock:
                    local_lock.release()
                return False
            db_dir = QtCore.QFileInfo(fn).absoluteDir().absolutePath()

        # we expect to see: 'manage.py' and 'media' in this folder
        if not validate_local_db(db_dir):
            msg = QtWidgets.QApplication.translate(
                "nexus", "The selected database file does not appear to be a valid database."
            )
            QtWidgets.QMessageBox.critical(
                parent, QtWidgets.QApplication.translate("nexus", "Invalid database"), msg
            )
            if local_lock:
                local_lock.release()
            if raise_exception:
                raise exceptions.DBNotFoundError(
                    "The database file and/or the media directory does not exist."
                )
            return False

        # Check the version number of the database
        if not validate_local_db_version(db_dir):
            msg = QtWidgets.QApplication.translate(
                "nexus",
                "The selected database is newer than the version supported by this version of Nexus.",
            )
            msg += QtWidgets.QApplication.translate(
                "nexus", "\nPlease use a more recent version of the software to start this server."
            )
            QtWidgets.QMessageBox.critical(
                parent, QtWidgets.QApplication.translate("nexus", "Newer database detected"), msg
            )
            if local_lock:
                local_lock.release()
            return False

        # if in verbose mode, let the user adjust the port number
        if verbose:
            # Pick a port number
            title = QtWidgets.QApplication.translate("nexus", "Select local Nexus server port")
            msg = QtWidgets.QApplication.translate(
                "nexus", "Select the port where the local Nexus server will be launched"
            )
            port, ok = QtWidgets.QInputDialog.getInt(parent, title, msg, port, 1024, 65534)
            if not ok:
                if local_lock:
                    local_lock.release()
                return False
    else:
        db_dir = os.path.abspath(directory)
        # Check both the files and version
        if not validate_local_db(db_dir, version_check=True, version_max=ansys_version):
            if local_lock:
                local_lock.release()
            if raise_exception:
                # if the DB was found, it means the failure was from the version check that followed.
                if validate_local_db(db_dir):
                    raise exceptions.DBVersionInvalidError(
                        "The database version number is incorrect. "
                        "It was likely generated by a newer version of Nexus."
                    )
                else:
                    raise exceptions.DBNotFoundError(
                        "The database file and/or the media directory does not exist."
                    )
            return False

    # Check to see if there is already a server running on this URI
    # build a server and try it

    tmp_server = Server(url=f"http://127.0.0.1:{port}", username=username, password=password)
    try:
        # validate will throw exceptions or return a float.
        _ = tmp_server.validate()
        # if we have a valid version number, then do not start a server!!!
        if parent and has_qt:
            msg = QtWidgets.QApplication.translate(
                "nexus",
                "There appears to be a local Nexus server already running on that port.\nPlease stop that server first or select a different port.",
            )
            QtWidgets.QMessageBox.critical(
                parent, QtWidgets.QApplication.translate("nexus", "Server already running"), msg
            )
        if local_lock:
            local_lock.release()
        if raise_exception:
            raise exceptions.ServerPortInUseError(
                "There appears to be a local Nexus server already running on that port.\nPlease stop that server first or select a different port."
            )
        return False
    except Exception:
        pass

    # Start the busy cursor
    if parent and has_qt:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

    # Here we run nexus_launcher with the following command line:
    # nexus_launcher.bat start --db_directory {dirname} --server_port {port} --internal_base_port {port} --instance_count 1
    # we might add:
    # --debug    if running in debug mode
    # --tray 1   if we are not terminating on exit and we have a Qt interface
    # Note: for the time being, we force the django instance count to be one.  This is in line with the older
    # implementation of the API and is needed for things like coverage tests.  We can consider relaxing this
    # in the future.
    if exec_basis:
        exename = os.path.join(exec_basis, "bin", "nexus_launcher" + str(ansys_version))
    else:
        exename = os.path.join(
            report_utils.enve_home(),
            "bin",
            "nexus_launcher" + report_utils.ceiversion_nexus_suffix(),
        )
    is_windows = report_utils.enve_arch().startswith("win")
    if is_windows:
        exename += ".bat"
    command = [
        exename,
        "start",
        "--db_directory",
        db_dir,
        "--server_port",
        str(port),
    ]

    if parent_process:
        command.extend(["--parent_process", str(parent_process)])

    if verbose:
        command.extend(["--verbose", "1"])

    if use_debug:
        command.extend(["--debug", "1"])

    # kwargs to be passed on the command line
    for key, value in settings.items():
        command.extend([f"--{key}", value])

    # if we are running in a mode where we know Qt is ok
    # we will enable the system tray interface.
    local_use_tray = not terminate_on_python_exit
    if use_system_tray is not None:
        local_use_tray = use_system_tray
    if local_use_tray and parent and has_qt:
        command.extend(["--tray", "1"])

    # Capture stderr to leverage nexus_launcher CLI error checking.  Grabbing stdout as well, but not
    # used at the moment
    params = dict(
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, cwd=db_dir
    )
    if is_windows:
        params["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        params["close_fds"] = True

    # Actually try to launch the server
    try:
        # Run the launcher to start the server
        # Note: this process only returns if the server is shutdown or there is an error
        monitor_process = subprocess.Popen(command, **params)
    except Exception as e:
        if parent and has_qt:
            QtWidgets.QApplication.restoreOverrideCursor()
            msg = QtWidgets.QApplication.translate(
                "nexus", "Launching a server for the selected local database failed. Error:"
            )
            QtWidgets.QMessageBox.critical(
                parent, QtWidgets.QApplication.translate("nexus", "Unable to launch"), msg + str(e)
            )
        if local_lock:
            local_lock.release()
        if raise_exception:
            raise exceptions.ServerLaunchError(
                f"Launching a server for the selected local database failed: {e}"
            )
        return False

    # Verify the new server is running and responding.
    t0 = time.time()
    while True:
        monitor_alive = monitor_process.poll() is None
        # if we ran out of patience or the monitor process is dead, we have an error
        if ((time.time() - t0) > server_timeout) or (not monitor_alive):
            if parent and has_qt:
                QtWidgets.QApplication.restoreOverrideCursor()
                msg = QtWidgets.QApplication.translate(
                    "nexus", "Unable to connect to the launched local Nexus server."
                )
                QtWidgets.QMessageBox.critical(
                    parent, QtWidgets.QApplication.translate("nexus", "Unable to launch"), msg
                )
            # If it is still alive, try to tell the monitor to shut down
            if monitor_alive:
                stop_background_local_server(db_dir, reason="python API")
            # return the error
            if local_lock:
                local_lock.release()
            if raise_exception:
                msg = "Server monitoring process lost. Unable to connect to local Nexus server."
                if monitor_alive:
                    msg = f"Connection timeout. Unable to connect to local Nexus server in {server_timeout} seconds."
                else:
                    output_text = monitor_process.stderr.read().decode("utf-8")
                    idx = output_text.find("error: ")
                    if idx > 0:
                        # just the "error: ..." text.
                        msg = output_text[idx:]
                        # replace '--' to make the messages generally match the keywords
                        msg = msg.replace("argument --", "argument ")
                raise exceptions.ServerConnectionError(msg)
            return False
        try:
            # If we can validate the server, then it is up and running
            _ = tmp_server.validate()
            break
        except exceptions.PermissionDenied:
            stop_background_local_server(db_dir)
            raise exceptions.ServerConnectionError(
                "Access to server denied.  Potential username/password error."
            )
        except Exception:
            # we will try again
            pass

    # detach from stdout, stderr to avoid buffer blocking
    monitor_process.stderr.close()
    monitor_process.stdout.close()

    # Allow another API launch to continue
    if local_lock:
        local_lock.release()

    if parent and has_qt:
        QtWidgets.QApplication.restoreOverrideCursor()
        if verbose:
            hostname = settings.get("server_hostname", "127.0.0.1")
            msg = QtWidgets.QApplication.translate("nexus", "A new server has been launched at")
            msg += f" <a href='http://{hostname}:{port}'>http://{hostname}:{port}</a>"
            QtWidgets.QMessageBox.information(
                parent, QtWidgets.QApplication.translate("nexus", "Nexus server launched"), msg
            )
    # go ahead and assign the connection to any server we were passed
    if connect is not None:
        connect.set_URL(tmp_server.get_URL())
        connect.set_username(tmp_server.get_username())
        connect.set_password(tmp_server.get_password())
    # if requested, we can kill the server on termination of the Python interpreter
    if terminate_on_python_exit:
        # Two implementations here, depending on the caller
        try:
            # For code running in the EnSight embedded interpreter, atexit is never called.  We
            # use the 'trf' monitor system to handle this case instead.  This is needed to handle
            # command language playback.
            import ensight

            # Note: if the ensight type hint stub is included, the error will
            # happen in the ensight.query() call as an AttributeError
            preferences_path = ensight.query(ensight.PREFERENCESPATH)
            idx = 0
            while idx < 10000:
                s = f"nexus_server_{os.getpid()}_{idx}.dat"
                filename = os.path.join(preferences_path, s)
                if os.path.isfile(filename):
                    idx += 1
                    continue
                fp = open(filename, "wb")
                fp.write(f"{os.getpid()} {db_dir}\n".encode())
                if delete_db_on_python_exit:
                    # If we want to delete the database, then use pid = -2 to mark this in the file
                    fp.write(f"-2 {db_dir}\n".encode())
                fp.close()
                break
        except (ModuleNotFoundError, AttributeError):
            # For other, cpython cases like the template_editor, we use the standard atexit system.
            import atexit

            if delete_db_on_python_exit:
                atexit.register(delete_database, db_dir)
            atexit.register(stop_background_local_server, db_dir)

    # return some handy info
    return_info["directory"] = db_dir
    return_info["port"] = port
    return True
