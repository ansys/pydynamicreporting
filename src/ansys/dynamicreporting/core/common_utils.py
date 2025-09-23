import os
from pathlib import Path
import platform
import re

from . import DEFAULT_ANSYS_VERSION as CURRENT_VERSION
from .constants import JSON_NECESSARY_KEYS, JSON_TEMPLATE_KEYS, REPORT_TYPES
from .exceptions import InvalidAnsysPath
from .utils.exceptions import TemplateEditorJSONLoadingError


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

            dirs_to_check.append(Path(enve.home()))
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


def _check_template_name_convention(template_name):
    if template_name is None:
        return True
    parts = template_name.split("_")
    return len(parts) == 2 and parts[0] == "Template" and parts[1].isdigit()


def _check_template(template_id_str, template_attr, logger=None):
    # Check template_id_str
    if not _check_template_name_convention(template_id_str):
        raise TemplateEditorJSONLoadingError(
            f"The loaded JSON file has an invalid template name: '{template_id_str}' as the key.\n"
            "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'"
        )

    # Check parent and children template name convention
    if not _check_template_name_convention(template_attr["parent"]):
        raise TemplateEditorJSONLoadingError(
            f"The loaded JSON file has an invalid template name: '{template_attr['parent']}' "
            f"that does not have the correct name convention under the key: 'parent' of '{template_id_str}'\n"
            "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'"
        )

    for child_name in template_attr["children"]:
        if not _check_template_name_convention(child_name):
            raise TemplateEditorJSONLoadingError(
                f"The loaded JSON file has an invalid template name: '{child_name}' "
                f"that does not have the correct name convention under the key: 'children' of '{template_id_str}'\n"
                "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'"
            )

    # Check missing necessary keys
    for necessary_key in JSON_NECESSARY_KEYS:
        if necessary_key not in template_attr.keys():
            raise TemplateEditorJSONLoadingError(
                f"The loaded JSON file is missing a necessary key: '{necessary_key}'\n"
                f"Please check the entries under '{template_id_str}'."
            )

    # Add warnings to the logger about the extra keys
    if logger:
        extra_keys = []
        for key in template_attr.keys():
            if key not in JSON_TEMPLATE_KEYS:
                extra_keys.append(key)
        if extra_keys:
            logger.warning(f"There are some extra keys under '{template_id_str}': {extra_keys}")

    # Check report_type
    if not template_attr["report_type"] in REPORT_TYPES:
        raise TemplateEditorJSONLoadingError(
            f"The loaded JSON file has an invalid 'report_type' value: '{template_attr['report_type']}'"
        )

    # Check item_filter
    common_error_str = "The loaded JSON file does not follow the correct item_filter convention!\n"
    for query_stanza in template_attr["item_filter"].split(";"):
        if len(query_stanza) > 0:
            parts = query_stanza.split("|")
            if len(parts) != 4:
                raise TemplateEditorJSONLoadingError(
                    f"{common_error_str}Each part should be divided by '|', "
                    f"while the input is '{query_stanza}' under '{template_id_str}', which does not have 3 '|'s"
                )
            if parts[0] not in ["A", "O"]:
                raise TemplateEditorJSONLoadingError(
                    f"{common_error_str}The first part of the filter can only be 'A' or 'O', "
                    f"while the first part of the input is '{parts[0]}' under '{template_id_str}'"
                )
            prefix = ["i_", "s_", "d_", "t_"]
            if parts[1][0:2] not in prefix:
                raise TemplateEditorJSONLoadingError(
                    f"{common_error_str}The second part of the filter can only be '{prefix}', "
                    f"while the second part of the input is '{parts[1]}' under '{template_id_str}'"
                )
    # TODO: check 'sort_selection' and 'params'


def populate_template(id_str, attr, parent_template, create_template_func, logger=None, *args):
    _check_template(id_str, attr, logger)
    template = create_template_func(
        *args, name=attr["name"], parent=parent_template, report_type=attr["report_type"]
    )
    template.set_params(attr["params"] if "params" in attr else {})
    if "sort_selection" in attr and attr["sort_selection"] != "":
        template.set_sort_selection(value=attr["sort_selection"])
    template.set_tags(attr["tags"] if "tags" in attr else "")
    template.set_filter(filter_str=attr["item_filter"] if "item_filter" in attr else "")

    return template
