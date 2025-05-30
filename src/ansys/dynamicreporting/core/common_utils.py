import os
from pathlib import Path
import platform
import re

from . import DEFAULT_ANSYS_VERSION as CURRENT_VERSION
from .exceptions import InvalidAnsysPath


def get_install_version(install_dir: Path) -> int | None:
    """
    Extracts the version number from an installation directory path.

        - Matches `v###` or `V###` anywhere in the path.
        - Ensures `v###` is a full segment, not inside another word.

    Expected formats:
    - Windows: C:\\Program Files\\ANSYS Inc\\v252
    - Linux: /ansys_inc/v252

    Args:
        install_dir (Path): Path to the installation directory.

    Returns:
        str: Extracted version number or an empty string if not found.
    """
    matches = re.search(r"[\\/][vV]([0-9]{3})([\\/]|$)", str(install_dir))
    return int(matches.group(1)) if matches else None


def get_install_info(
    ansys_installation: str | None = None, ansys_version: int | None = None
) -> tuple[str | None, int]:
    """Attempts to detect the Ansys installation directory and version number.

    Args:
        ansys_installation (str, optional): Path to the Ansys installation directory. Defaults to None.
        ansys_version (int, optional): Version number to use. Defaults to None.

    Returns:
        tuple[str, int]: Installation directory and version number.
    """
    dirs_to_check = []
    if ansys_installation:
        # User passed directory
        dirs_to_check = [Path(ansys_installation) / "CEI", Path(ansys_installation)]
    else:
        # Environmental variable
        if "PYADR_ANSYS_INSTALLATION" in os.environ:
            env_inst = Path(os.environ["PYADR_ANSYS_INSTALLATION"])
            # Note: PYADR_ANSYS_INSTALLATION is designed for devel builds
            # where there is no CEI directory, but for folks using it in other
            # ways, we'll add that one too, just in case.
            dirs_to_check = [env_inst / "CEI", env_inst]
        # 'enve' home directory (running in local distro)
        try:
            import enve

            dirs_to_check.append(enve.home())
        except ModuleNotFoundError:
            pass
        # Look for Ansys install using target version number
        if f"AWP_ROOT{CURRENT_VERSION}" in os.environ:
            dirs_to_check.append(Path(os.environ[f"AWP_ROOT{CURRENT_VERSION}"]) / "CEI")
        # Option for local development build
        if "CEIDEVROOTDOS" in os.environ:
            dirs_to_check.append(Path(os.environ["CEIDEVROOTDOS"]))
        # Common, default install locations
        if platform.system().startswith("Wind"):  # pragma: no cover
            install_loc = Path(rf"C:\Program Files\ANSYS Inc\v{CURRENT_VERSION}\CEI")
        else:
            install_loc = Path(f"/ansys_inc/v{CURRENT_VERSION}/CEI")
        dirs_to_check.append(install_loc)

    # find a valid installation directory
    install_dir = None
    for dir_ in dirs_to_check:
        if dir_.is_dir():
            install_dir = dir_
            break

    version = get_install_version(install_dir)
    # use user provided version only if install dir has no version
    if version is None:
        version = ansys_version or int(CURRENT_VERSION)

    # raise if ansys_installation is provided but not found
    if ansys_installation and (
        install_dir is None
        or not (install_dir / f"nexus{version}" / "django" / "manage.py").exists()
    ):
        raise InvalidAnsysPath(
            f"Unable to detect an installation in: {[str(d) for d in dirs_to_check]}"
        )
    # if it is not found and the user did not provide a path, return None
    # This is for backwards compatibility with the old behavior in the Service class
    return str(install_dir) if install_dir is not None else None, version
