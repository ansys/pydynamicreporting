import glob
import os
import platform
import shutil
import subprocess

from ansys.dynamicreporting.core.utils import geofile_processing
from django.conf import settings
from reports.engine import TemplateEngine


def do_geometry_update_check():
    """
    Verify/update the csf files in the media directory
    """
    # get the existing version
    path = os.path.join(settings.MEDIA_ROOT, "csf_conversion_version")
    try:
        with open(path, "rt", encoding='utf-8') as f:
            old_version = f.read()
        old_version = old_version.strip()
    except:
        old_version = "unknown"
    # get the new version
    new_version = old_version
    app = 'cei_apex{}_udrw2avz'.format(settings.CEI_APEX_SUFFIX)
    create_flags = 0
    # Note: should we be using a detached process (8) here?  It could lead to a race condition???
    if platform.system().startswith("Win"):
        app += '.bat'
        create_flags = subprocess.CREATE_NO_WINDOW
    cmd = [app, "-i"]
    try:
        new_version = subprocess.check_output(cmd, stdin=subprocess.DEVNULL, creationflags=create_flags).decode("utf-8")
        new_version = new_version.strip()
    except Exception as e:
        pass
    if old_version != new_version:
        print(f"New version of the 3D geometry engine detected ('{old_version}' vs '{new_version}')")
        print("Converting existing 3D geometry to new version...")
        # get the files we need to process in some way
        filenames = list()
        for ext in ["*.csf", "*.ply", "*.stl", "*.avz", "*.scdoc", "*.evsn", "*.ens"]:
            filenames.extend(glob.glob(os.path.join(settings.MEDIA_ROOT, ext)))
        for filename in filenames:
            root, ext = os.path.splitext(filename)
            # remove old versions
            try:
                # a peer level .js file
                os.remove(filename + ".js")
            except:
                pass
            try:
                # a subdirectory with the same name as the file w/o the extension
                shutil.rmtree(root)
            except:
                pass
            # Generate the new geometry representation
            unique_id = os.path.basename(root)[:36]
            unique_id = unique_id.replace("-", "")
            geofile_processing.rebuild_3d_geometry(filename, unique_id)
        print("3D Geometry conversion complete.")
        with open(path, "wt", encoding='utf-8') as f:
            f.write(new_version + "\n")


def get_ext_service_available(item, ctx):
    """
    If the service associated with the filename extension used by the Data Item is defined
    and available, return True.  Otherwise, set an appropriate error message in ctx['error']
    and return False.
    """
    ext_view = item.get_default(None, ctx, 'file_allow_ext_viewer', default=1, force_int=True) == 1
    if not ext_view:
        return False
    from website.views import (get_remote_session_configuration,
                               valid_user_group)
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
                ctx['error'] = f'The current user is not a member of the group required for the "{services[0]}" service.'
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
    imported_by_udrw = ext.lower() not in ['.avz', '.scdoc']
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
    s += f'<ansys-nexus-viewer {active} {aspect} {source} id="avz_comp_{item.lcl_UUID}">'
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

