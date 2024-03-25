import json
import os
import urllib
import urllib.parse

import requests
from ansys.dynamicreporting.core.utils import geofile_processing
from django.conf import settings

from ..reports.engine import TemplateEngine


class WebsocketServerInterface:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = WebsocketServerInterface()
        return cls._instance

    def __init__(self):
        # is websocketserver running at all?
        settings.REMOTE_WEBSOCKETURL = os.environ.get('CEI_NEXUS_REMOTE_WEBSOCKETURL', '')
        settings.REMOTE_VNCPASSWORD = os.environ.get('CEI_NEXUS_REMOTE_VNCPASSWORD', None)
        settings.REMOTE_WS_PORT = os.environ.get('CEI_NEXUS_REMOTE_WS_PORT', None)
        settings.REMOTE_HTML_PORT = os.environ.get('CEI_NEXUS_REMOTE_HTML_PORT', None)
        self._base_url = settings.REMOTE_WEBSOCKETURL
        self._html_port = settings.REMOTE_HTML_PORT
        self._ws_port = settings.REMOTE_WS_PORT
        # the current websocketserver state
        self._current_state = []
        # current_state is a list of dictionaries dict(name='', instances=[], common_options=dict())
        # the common_options dict may include:  dict(file_ext=[], sizes=[], verbose=0|1), etc
        # instances is an array of dictionaries dict(index=0, token='', timestamp=0.0, options=dict())

    def has_desktop_sessions(self):
        if not self.update_sessions():
            return False
        for service in self._current_state:
            if 'file_ext' not in service.get('common_options', {}):
                return True
        return False

    def get_service_by_name(self, name):
        if not self.update_sessions():
            return None
        for service in self._current_state:
            if service['name'] == name:
                return service
        return None

    def get_services(self, file_ext=None):
        services = []
        if not self.update_sessions():
            return services
        for service in self._current_state:
            ext_list = service.get('common_options', {}).get('file_ext', [])
            # Return the service if a specific filename extension is specified and it matches
            # or no filename extension is specified and there is no 'file_ext' list...
            if file_ext in ext_list:
                services.append(service)
            elif (file_ext is None) and (len(ext_list) == 0):
                services.append(service)
        return services

    def get_instance(self, token):
        if not self.update_sessions():
            return None, None
        for service in self._current_state:
            for instance in service['instances']:
                if instance['token'] == token:
                    return service, instance
        return None, None

    def update_sessions(self):
        if not self._base_url:
            return False
        try:
            if settings.WEBSOCKETSERVER_SECURITY_TOKEN:
                url = self.build_url("/v1/status", {"security_token": settings.WEBSOCKETSERVER_SECURITY_TOKEN})
            else:
                url = self.build_url("/v1/status")
            resp = requests.get(url)
            if resp.status_code != requests.codes.ok:
                return False
            self._current_state = json.loads(resp.text)
        except Exception:
            self._current_state = []
            return False
        return True

    def reserve(self, session_name, options=None):
        if not self.update_sessions():
            return None
        # /v1/reserve/local_envision?target_pathname=D:/ANSYSDev/example_envision.evsn
        url = self.build_url(f"/v1/reserve/{session_name}", options)
        # do the work
        resp = requests.get(url)
        if resp.status_code != requests.codes.ok:
            return None
        # parse the returned token (if any)
        # {"token": "5cd27076-db61-11eb-9e9f-3814288ef490"}
        token = json.loads(resp.text).get("token", None)
        self.update_sessions()
        return token

    # replace the path and query components of an existing URL
    def build_url(self, path, query=None):
        parts = list(urllib.parse.urlparse(self.url()))
        parts[2] = path
        if query:
            parts[4] = urllib.parse.urlencode(query)
        return urllib.parse.urlunparse(parts)

    def url(self, ws=False):
        url = self._base_url
        if ws:
            url += f":{self._ws_port}"
        else:
            url += f":{self._html_port}"
        return url


# Bootstrap the remote session system
def get_remote_session_configuration():
    return WebsocketServerInterface.instance()


def valid_user_group(user, group, remote_desktop=False, embedded_applet=False):
    # split up the string '{group}[:applet]'
    tmp = group.split(':')
    while len(tmp) < 2:
        tmp.append('')

    # remote_desktop:
    #     it not authenticated -> False
    #     if ':applet' qualifier -> False
    #     if '' -> True
    #     if 'user in group' -> True
    if remote_desktop:
        if not user.is_authenticated:
            return False
        if 'applet' in tmp[1]:
            return False
        if len(tmp[0]) == 0:
            return True
        if user.groups.filter(name=str(tmp[0])).exists():
            return True

    # embedded_applet:
    #     it not authenticated -> False
    #     if not ':applet' qualifier -> False
    #     if '' -> True
    #     if 'user in group' -> True
    if embedded_applet:
        if not user.is_authenticated:
            return False
        if 'applet' not in tmp[1]:
            return False
        if len(tmp[0]) == 0:
            return True
        if user.groups.filter(name=str(tmp[0])).exists():
            return True

    return False


def get_ext_service_available(item, ctx):
    """
    If the service associated with the filename extension used by the Data Item is defined
    and available, return True.  Otherwise, set an appropriate error message in ctx['error']
    and return False.
    """
    ext_view = item.get_default(None, ctx, 'file_allow_ext_viewer', default=1, force_int=True) == 1
    if not ext_view:
        return False
    config = get_remote_session_configuration()
    if config:
        request = ctx.get('request', {})
        if request is None:
            ctx['error'] = 'Error starting the service.'  # Not sure if this can happen
            return False
        _, extension = os.path.splitext(item.get_payload_server_pathname())
        extension = extension.replace('.', '')
        services = config.get_services(file_ext=extension)
        if len(services) > 0:
            if not request.user.is_authenticated:
                ctx['error'] = f'You must be logged in to access "{services[0]}" instances.'
                return False
            group_name = services[0].get('common_options', {}).get('group', '')
            if group_name and not valid_user_group(request.user, group_name,
                                                   embedded_applet=True):
                ctx[
                    'error'] = f'The current user is not a member of the group required for the "{services[0]}" service.'
                return False
            return True
        else:
            ctx['error'] = 'No service instances have been configured.'
            return False
    else:
        ctx['error'] = 'No service instances have been configured.'
    return False


def render_scene(item, context, ctx):
    """Generate the HTML associated with the passed scene Data Item.
    Scene objects can be '.scdoc', '.avz' or '.csf'.   If the upload was
    of a file format supported by the UDRW system, Nexus would have
    converted it into .avz ("/scene.avz").  When this is the case,
    both the WebGL and VNC renderers are legal.
    """
    s = ""
    payload_url = item.get_payload_file_url()
    # The scene file may either be a .avz file, a .scdoc file or there should be a
    # scene.avz file in a directory named the same as the uploaded file minus the extension
    base_url_name, ext = os.path.splitext(payload_url)
    imported_by_udrw = ext.lower() not in ['.avz', '.scdoc', '.glb']
    if imported_by_udrw:
        payload_url = base_url_name + '/scene.avz'
    # Is there a proxy image?  Note: it will always be in a subdirectory named by the item file.
    server_file_pathname = item.get_payload_server_pathname()
    base_name, _ = os.path.splitext(server_file_pathname)
    proxy_url = None
    if os.path.exists(os.path.join(base_name, 'proxy.png')):
        proxy_url = base_url_name + '/proxy.png'
    # AVZ path
    width = item.get_default(None, ctx, 'width', -1, force_int=True)
    if width > 0:
        width = "width:{}px;".format(width)
    else:
        width = "width:100%;"
    height = item.get_default(None, ctx, 'height', -1, force_int=True)
    use_aspect_ratio = False
    if height > 0:
        height = "height:{}px;".format(height)
    else:
        height = ""
        use_aspect_ratio = True
    s += f"<div class='avz-viewer' id='avz_viewer_{item.lcl_UUID}'"
    s += " style='display:inline-block;top:0px;left:0px;"
    s += f"{width}{height}margin:0;border:0;padding:0;fixed:absolute;background:white;'>\n"
    # create an instance of the ansys-nexus-viewer element
    # <ansys-nexus-viewer active=true aspect_ratio=1.777 src="/.../scene.avz" id="xxx"></ansys-nexus-viewer>
    #
    # Aspect ratio cases:
    # width and height specified - handled by div
    # width, no height - 1.77778 or 'proxy' image aspect ratio
    aspect = ""
    if use_aspect_ratio:
        # default to 16:9
        aspect = "aspect_ratio=1.77778"
        if proxy_url is not None:
            aspect = 'aspect_ratio="proxy"'

    # should we try to use the remote (envision) renderer
    use_remote_viewer = item.get_default(None, ctx, 'use_remote_viewer', default=0, force_int=True)
    # if printing, we will fall back to AVZ viewer
    if use_remote_viewer and (TemplateEngine.get_print_style() is None):
        # is there a renderer configured for the (original) uploaded file
        if get_ext_service_available(item, ctx):
            # EnVision viewer
            if proxy_url:
                if item.media_auth_hash:
                    proxy_url += f'?media_auth={item.media_auth_hash}'
            else:
                aspect = 'aspect_ratio="proxy"'
                proxy_url = "/ansys/nexus/images/proxy_viewer.png"
            proxy_str = f'{aspect} proxy_img="{proxy_url}"'
            file_payload_path = item.get_payload_server_pathname()
            s += f'<ansys-nexus-viewer renderer="envnc" src="{file_payload_path}" {proxy_str} renderer_options=\'{{"http": "{settings.CEI_NEXUS_NGINX_URL}", "ws": "{settings.CEI_NEXUS_NGINX_URL}/websockify", "security_token": "{settings.WEBSOCKETSERVER_SECURITY_TOKEN}" }}\'></ansys-nexus-viewer>'
            s += "</div>\n"
            return s
        else:
            # we will fall back to the AVZ viewer, so erase any error
            _ = ctx.pop('error', None)

    # The AVZ viewer pipeline
    # if there is no proxy image, default to active
    # if not, specify the proxy image and default to inactive
    active = "active=true"
    if TemplateEngine.get_print_style() == TemplateEngine.PrintStyle.PDF:
        # not setting a source ensures that the default proxy is shown
        active = "active=false"
    if proxy_url is not None:
        active = f'proxy_img="{proxy_url}" active=false'
    source = f'src="{payload_url}"'
    # GLB uses the three.js renderer
    renderer = ""
    if ext.lower() == ".glb":
        renderer = 'renderer="three"'
    s += f'<ansys-nexus-viewer {renderer} {active} {aspect} {source} id="avz_comp_{item.lcl_UUID}">'
    s += '</ansys-nexus-viewer>\n'
    s += "</div>\n"
    return s


def render_file(item, context, ctx):
    """
    Generate the HTML associated with the passed file Data Item.
    This can be a download link or a 3D viewer.   Note: the file types
    supported by this system are specified by websocketserver filetype
    mappings (and the get_ext_service_available() interface).
    """
    file_payload_url = item.get_payload_file_url()
    if item.media_auth_hash:
        file_payload_url += f'?media_auth={item.media_auth_hash}'
    file_payload_path = item.get_payload_server_pathname()
    # any potential proxy image?
    proxy_img = ""
    proxy_filename = os.path.join(os.path.splitext(item.get_payload_server_pathname())[0],
                                  "proxy.png")
    # Use the proxy image associated with the payload, or fallback to a default proxy image.
    if os.path.isfile(proxy_filename):
        proxy_url = os.path.splitext(item.get_payload_file_url())[0]
        proxy_url += "/proxy.png"
    else:
        proxy_url = "/ansys/nexus/images/proxy_viewer.png"

    if item.media_auth_hash:
        proxy_url += f'?media_auth={item.media_auth_hash}'

    # Not all file formats can have proxy images.  This will suppress the "proxy_viewer.png" for
    # these cases.
    if geofile_processing.file_can_have_proxy(item.get_payload_server_pathname()):
        style = 'width:auto;height:auto;max-height:100%;max-width:100%;'
        proxy_img = f'<p><img src="{proxy_url}" style="{style}"></p>'

    # if "printing" then just return the proxy image
    if TemplateEngine.get_print_style() is not None:
        return proxy_img

    # get ext url
    ext_service_available = get_ext_service_available(item, ctx)
    # if there is an external viewer (VNC) specified, include a link to it
    if ext_service_available:
        proxy_str = ""
        if len(proxy_url) > 0:
            proxy_str = f'aspect_ratio="proxy" proxy_img="{proxy_url}"'
        ext_view_html = f'<ansys-nexus-viewer renderer="envnc" src="{file_payload_path}" {proxy_str} renderer_options=\'{{"http": "{settings.CEI_NEXUS_NGINX_URL}", "ws": "{settings.CEI_NEXUS_NGINX_URL}/websockify", "security_token": "{settings.WEBSOCKETSERVER_SECURITY_TOKEN}" }}\'></ansys-nexus-viewer>'
    else:
        ext_view_html = proxy_img
    return f'{ext_view_html}<p><em>File: <a href="{file_payload_url}">Download {str(item.name)}</a></em></p>\n'
