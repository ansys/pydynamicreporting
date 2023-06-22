"""
Methods that implement core processing of the various geometry files.

These are generally applied when a file is uploaded or the Nexus version number changes.
These functions will convert files supported by the UDRW interface into AVZ files and
extract proxy data from AVZ and EVSN files to simplify their display.
"""
import glob
import io
import os
import platform
import shutil
import subprocess
import typing
import zipfile

from django.conf import settings

try:
    is_enve = True
    import enve
    from reports.engine import TemplateEngine
except Exception:
    is_enve = False


def get_evsn_proxy_image(filename: str) -> typing.Union[bytearray, None]:
    """Extract and return any PNG proxy image that could be found in the input EVSN
    file."""
    # From liben/proxy_image.cpp
    proxyimage_header = bytearray([0x66, 0x36, 0xBB, 0x82, 0x87, 0x8E, 0x11, 0xEC, 0xAE, 0x6D])
    proxyimage_trailer = bytearray([0x67, 0x5F, 0x81, 0x9C, 0x87, 0x8E, 0x11, 0xEC, 0x9D, 0x6C])
    # Look for the trailer.  It will be in the last 1k of the file and will look like this
    #   proxyimage_header (10bytes)
    #   size_of_png_data (4bytes)
    #   png_data (size_of_png_data bytes)
    #   size_of_png_data (4bytes)
    #   proxyimage_trailer (10bytes)
    with open(filename, "rb") as fp:
        # read the last 1024 bytes of the file
        fp.seek(-1024, io.SEEK_END)
        data = fp.read(1024)
        file_length = fp.tell()  # because we read last 1k bytes, filepos should be at the end
        # find the trailer
        try:
            offset = data.index(proxyimage_trailer)
        except ValueError:
            return None
        # get the length of the PNG block (4 bytes before the trailer)
        offset -= 4
        if offset < 0:
            return None
        # read little endian 32bit length
        png_length = (
            data[offset]
            + 256 * data[offset + 1]
            + 256 * 256 * data[offset + 2]
            + 256 * 256 * 256 * data[offset + 3]
        )
        # offset is the location of the trailer 32bit length value in the last 1k bytes, so
        file_pos = file_length - 1024 + offset
        # back up in the file by the header size, png payload size and the header 32bit length value
        file_pos -= png_length + len(proxyimage_header) + 4
        # Position for the read
        fp.seek(file_pos)
        # Verify the header
        hdr = fp.read(len(proxyimage_header))
        if hdr != proxyimage_header:
            return None
        # (re)verify the png block size
        data = fp.read(4)
        png_length2 = data[0] + 256 * data[1] + 256 * 256 * data[2] + 256 * 256 * 256 * data[3]
        if png_length != png_length2:
            return None
        # ok, we should have the png data now
        data = fp.read(png_length)
        return data
    return None


# The basic idea of the 3D geometry pipeline is that files in .csf, .ply, .scdoc, .avz or
# .stl format (formats supported by udrws) are pushed into the MEDIA_ROOT directory on the
# server. The server then launches cei_apexXY_udrw2avz to convert the files to the format
# used by the server to generate entries in reports.  Currently, this operation results
# in a new subdirectory named as the geometry filename w/o any extension that is read by
# the view generation engine.  The system also tags the MEDIA_ROOT directory with a
# file containing the version of cei_apexXY_udrw2avz that was used (-i).  The first
# time the server is accessed, it checks this tag and if needed, will delete all
# the existing output from previous runs of the tool and replace them with run of the
# new version.  Thus, the version number of cei_apexXY_udrw2avz as reported with -i
# is critical for keeping a database consistent with the latest release of Nexus.


def file_can_have_proxy(filename: str) -> bool:
    """For a given filename, return True if the file format could include a proxy
    image."""
    _, extension = os.path.splitext(filename)
    return extension in (".csf", ".avz", ".evsn", ".ens", ".scdoc")


def file_is_3d_geometry(filename: str, file_item_only: bool = True) -> bool:
    """For a given filename, return True if the file format contains 3D geometry."""
    _, extension = os.path.splitext(filename)
    if file_item_only:
        return extension in (".evsn", ".ens", ".scdoc")
    return extension in (".csf", ".stl", ".ply", ".avz", ".evsn", ".ens", ".scdoc")


def rebuild_3d_geometry(csf_file: str, unique_id: str, exec_basis: str = None):
    """Rebuild the media directory representation of the file (udrw format, avz, scdoc
    or evsn)"""
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
    # '.avz' -> just extract the proxy image (if any)
    # '.evsn' -> extract the proxy image (if any)
    # No file conversions needed in these cases, but the proxy image (if any) is extracted as:
    # {media}/2342412421_scene/proxy.png
    avz_dir, csf_ext = os.path.splitext(csf_file)
    # make the associated directory in all cases
    try:
        os.mkdir(avz_dir)
    except OSError:
        print(f"Warning: unable to create 3D geometry directory: {avz_dir}")
        return
    avz_filename = csf_file
    # Easiest case, handle SCDOC files
    if csf_ext.lower() == ".scdoc":
        # SCDOC files can have a thumbnail as: docProps/thumbnail.png
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
    # Easy case, handle EVSN
    elif csf_ext.lower() == ".evsn":
        # EVSN handling is entirely different, so handle it all here
        png = get_evsn_proxy_image(avz_filename)
        if png is not None:
            try:
                with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                    output_file.write(png)
            except OSError as e:
                print(f"Warning: unable to extract EVSN proxy image: {str(e)}")
        # EVSN processing is complete
        return
    # Handle the ENS (EnSight session file) case
    elif csf_ext.lower() == ".ens":
        # this is a zip formatted file with a file named "preview.png" which is the proxy
        with zipfile.ZipFile(avz_filename) as archive:
            for name in archive.namelist():
                if name.lower() == "preview.png":
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        try:
                            with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                                output_file.write(data)
                        except OSError as e:
                            print(f"Warning: unable to extract ENS proxy image: {str(e)}")
        # ENS processing is complete
        return
    # A little sneaky here as the udrw2avz conversion can create an AVZ file with
    # a proxy image in it.  So we pass UDRW files through the pipeline first.
    if csf_ext.lower() != ".avz":  # pragma: no cover
        # convert the udrw file into a .avz file using the cei_apexXXX_udrw2avz command
        app = f"cei_apex{settings.CEI_APEX_SUFFIX}_udrw2avz"
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
            )
        except Exception:
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
    except Exception:
        print(f"Warning: unable to extract AVZ proxy image: {str(e)}")
