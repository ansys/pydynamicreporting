# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Methods that implement core processing of the various geometry files.

These are generally applied when a file is uploaded or the Nexus version number changes.
These functions will convert files supported by the UDRW interface into AVZ files and
extract proxy data from AVZ files to simplify their display.
"""

import os
import platform
import subprocess  # nosec B78 B603 B404
import typing
import zipfile

from django.conf import settings

try:
    is_enve = True
    import enve
    from reports.engine import TemplateEngine
except Exception:
    is_enve = False


# The basic idea of the 3D geometry pipeline is that files in .csf, .ply, .scdoc, .scdocx,
#  .avz or.stl format (formats supported by udrws) are pushed into the MEDIA_ROOT directory
# on the server. The server then launches cei_apexXY_udrw2avz to convert the files to the
# format used by the server to generate entries in reports.  Currently, this operation
# results in a new subdirectory named as the geometry filename w/o any extension that is
# read by the view generation engine.  The system also tags the MEDIA_ROOT directory with
# a file containing the version of cei_apexXY_udrw2avz that was used (-i).  The first
# time the server is accessed, it checks this tag and if needed, will delete all
# the existing output from previous runs of the tool and replace them with run of the
# new version.  Thus, the version number of cei_apexXY_udrw2avz as reported with -i
# is critical for keeping a database consistent with the latest release of Nexus.


def file_can_have_proxy(filename: str) -> bool:
    """For a given filename, return True if the file format could include a proxy
    image."""
    _, extension = os.path.splitext(filename)
    return extension in (".csf", ".avz", ".scdoc", ".scdocx", ".dsco")


def file_is_3d_geometry(filename: str, file_item_only: bool = True) -> bool:
    """For a given filename, return True if the file format contains 3D geometry."""
    _, extension = os.path.splitext(filename)
    if file_item_only:
        return extension in (".scdoc", ".scdocx", ".dsco")
    return extension in (
        ".csf",
        ".stl",
        ".ply",
        ".avz",
        ".scdoc",
        ".scdocx",
        ".dsco",
    )


def get_avz_directory(csf_file: str) -> str:
    """Return the directory name for the AVZ file associated with the input CSF file."""
    return os.path.splitext(csf_file)[0]


def rebuild_3d_geometry(csf_file: str, unique_id: str = "", exec_basis: str = None):
    """Rebuild the media directory representation of the file (udrw format, avz or
    scdoc)"""
    # We are looking to convert the .csf or other udrw file to .avz with this command:
    # {dir} = item.get_payload_server_pathname() with the extension removed
    # cei_apex{ver}_udrw2avz{.bat} item.get_payload_server_pathname() {dir}/scene.avz
    #
    # input file name is: {media}/2342412421_scene.{csf,ply,stl,etc}
    # directory name is: {media}/2342412421_scene/
    # target names are: {media}/2342412421_scene/scene.avz  media/2342412421_scene/proxy.png
    #
    # Three special cases:
    # '.scdoc' -> extract thumbnail image (if any)
    # '.scdocx' -> extract thumbnail image (if any)
    # ".dsco" -> extract thumbnail image (if any)
    # '.avz' -> just extract the proxy image (if any)
    # No file conversions needed in these cases, but the proxy image (if any) is extracted as:
    # {media}/2342412421_scene/proxy.png
    avz_dir, csf_ext = os.path.splitext(csf_file)
    # make the associated directory in all cases
    try:
        os.mkdir(avz_dir)
    except OSError as e:
        print(f"Warning: unable to create 3D geometry directory: {e}")
        return
    avz_filename = csf_file
    # Easiest case, handle SCDOC, SCDOCX and DSCO files
    if csf_ext.lower() in {".scdoc", ".scdocx", ".dsco"}:
        # SCDOC / SCDOCX / DSCO files can have a thumbnail as: docProps/thumbnail.png
        with zipfile.ZipFile(avz_filename) as archive:
            for name in archive.namelist():
                if name.endswith("thumbnail.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        try:
                            with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                                output_file.write(data)
                        except OSError as e:
                            print(f"Warning: unable to extract SCDOC proxy image: {str(e)}")
        # SCDOC processing is complete
        return
    # A little sneaky here as the udrw2avz conversion can create an AVZ file with
    # a proxy image in it.  So we pass UDRW files through the pipeline first.
    if csf_ext.lower() != ".avz":  # pragma: no cover
        # convert the udrw file into a .avz file using the cei_apexXXX_udrw2avz command
        # Accept either ADR_VERSION (current) or CEI_APEX_SUFFIX (pre-rename install).
        version = getattr(settings, "ADR_VERSION", None) or getattr(settings, "CEI_APEX_SUFFIX", "")
        app = f"cei_apex{version}_udrw2avz"
        if is_enve is True:
            app = os.path.join(enve.home(), "bin", app)
        else:
            if exec_basis:
                app = os.path.join(exec_basis, "bin", app)
        create_flags = 0
        if platform.system().startswith("Win"):
            app += ".bat"
            create_flags = subprocess.CREATE_NO_WINDOW
        avz_filename = os.path.join(avz_dir, "scene.avz")
        cmd = [app, "-allframes", csf_file, avz_filename]
        try:
            subprocess.call(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=create_flags,
            )  # nosec B78 B603
        except Exception as e:
            print(f"Warning: unable to convert '{csf_file}' into AVZ format: {str(e)}")
    # At this point, if we have an original AVZ file or a converted udrw file, we
    # still look for proxy images.
    try:
        # if there is a proxy image, extract it from the AVZ archive
        with zipfile.ZipFile(avz_filename) as archive:
            for name in archive.namelist():
                if name.lower().endswith("proxy.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                            output_file.write(data)
                    break
    except Exception as e:
        print(f"Warning: unable to extract AVZ proxy image: {str(e)}")
