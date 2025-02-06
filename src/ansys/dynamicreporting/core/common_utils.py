import os
from pathlib import Path
import platform
import re

from . import DEFAULT_ANSYS_VERSION as CURRENT_VERSION
from .exceptions import AnsysVersionAbsentError, InvalidAnsysPath


def get_install_version(install_dir: Path) -> str:
    """Extracts the version number from an installation directory path, ensuring 'v###' is the last segment with exactly 3 digits.

    Expected formats:
    - Windows: C:\\Program Files\\ANSYS Inc\v252
    - Linux: /ansys_inc/v252

    Args:
        install_dir (Path): Path to the installation directory.

    Returns:
        str: Extracted version number or an empty string if not found.
    """
    match = re.fullmatch(r"[vV](\d{3})", install_dir.name)
    return match.group(1) if match else ""


def get_install_info(
    ansys_installation: str | None = None, ansys_version: str | None = None
) -> tuple[str, int]:
    """Attempts to detect the Ansys installation directory and version number.

    Args:
        ansys_installation (str, optional): Path to the Ansys installation directory. Defaults to None.
        ansys_version (str, optional): Version number to use. Defaults to None.

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
        if platform.system().startswith("Wind"):
            install_loc = Path(rf"C:\Program Files\ANSYS Inc\v{CURRENT_VERSION}\CEI")
        else:
            install_loc = Path(f"/ansys_inc/v{CURRENT_VERSION}/CEI")
        dirs_to_check.append(install_loc)

    install_dir = None
    version = None
    for dir_ in dirs_to_check:
        if dir_.is_dir():
            install_dir = dir_
            version = get_install_version(install_dir)
            break

    # use user provided version only if install dir has no version
    if version is None:
        if ansys_version:
            version = ansys_version
        else:
            raise AnsysVersionAbsentError

    config_file = install_dir / f"nexus{version}" / "django" / "manage.py"
    if not config_file.exists():
        raise InvalidAnsysPath(
            f"Unable to detect an installation in: {[str(d) for d in dirs_to_check]}"
        )

    return str(install_dir), int(version)
