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

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import platform
import re

import bleach

from .compatibility import AUTO_DETECT_INSTALL_VERSIONS, DEFAULT_ANSYS_INSTALL_VERSION
from .constants import JSON_NECESSARY_KEYS, JSON_TEMPLATE_KEYS, REPORT_TYPES
from .exceptions import InvalidAnsysPath
from .utils.exceptions import TemplateEditorJSONLoadingError

logger = logging.getLogger(__name__)


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


def _get_install_version_from_layout(install_dir: Path | None) -> int | None:
    """Infer the install version from ``nexus###`` directories when needed.

    Some explicit installation paths, such as copied Docker layouts or temp
    directories created during tests, do not include a ``v###`` segment in the
    path itself. In those cases the shipped ADR tree still exposes the version
    through its ``nexus###/django/manage.py`` layout, which is stable across
    the supported installation formats.
    """
    if install_dir is None or not install_dir.is_dir():
        return None

    detected_versions: list[int] = []
    for child in install_dir.iterdir():
        match = re.fullmatch(r"nexus(\d{3})", child.name)
        if match and (child / "django" / "manage.py").exists():
            detected_versions.append(int(match.group(1)))

    if len(detected_versions) == 1:
        return detected_versions[0]
    if len(detected_versions) > 1:
        # Surface the ambiguity so callers can understand why layout-based
        # inference fell back to a default version instead of picking one of
        # several matching ADR trees implicitly.
        logger.warning(
            "Detected multiple ADR layout versions under %s: %s. "
            "Falling back to the configured default install version.",
            install_dir,
            sorted(detected_versions),
        )
    return None


@dataclass(frozen=True)
class InstallResolution:
    """Resolved installation directory and version used by service/serverless setup."""

    install_dir: str | None
    version: int | None


def _candidate_dirs_for_install_root(install_root: Path) -> list[Path]:
    """Build candidate directories for both the new ADR and legacy CEI layouts."""
    return [install_root / "ADR", install_root / "CEI"]


def _default_install_root(version: str) -> Path:
    """Return the conventional install root for a three-digit Ansys version."""
    if platform.system().startswith("Wind"):  # pragma: no cover
        return Path(rf"C:\Program Files\ANSYS Inc\v{version}")
    return Path(f"/ansys_inc/v{version}")


def _append_unique(candidates_by_path: dict[str, Path], path: Path) -> None:
    """Preserve candidate order while avoiding duplicate filesystem probes.

    A dict preserves insertion order, so using the string path as the key keeps
    uniqueness checks constant-time without coordinating separate list/set
    state.
    """
    candidates_by_path.setdefault(str(path), path)


def _build_install_candidates(
    ansys_installation: str | None = None, ansys_version: int | None = None
) -> list[Path]:
    """Return candidate installation directories in probe order."""
    candidates_by_path: dict[str, Path] = {}

    if ansys_installation:
        # An explicit path always wins. Preserve the historical ADR -> CEI ->
        # base-directory order so callers see the same layout preference.
        for path in [
            Path(ansys_installation) / "ADR",
            Path(ansys_installation) / "CEI",
            Path(ansys_installation),
        ]:
            _append_unique(candidates_by_path, path)
        return list(candidates_by_path.values())

    if "PYADR_ANSYS_INSTALLATION" in os.environ:
        env_inst = Path(os.environ["PYADR_ANSYS_INSTALLATION"])
        for path in [env_inst / "ADR", env_inst / "CEI", env_inst]:
            _append_unique(candidates_by_path, path)

    try:
        import enve

        _append_unique(candidates_by_path, Path(enve.home()))
    except ModuleNotFoundError:
        pass

    # When callers pin ``ansys_version``, probe only that version family.
    # Otherwise use the ordered fallback list to keep implicit discovery broad
    # without resorting to repeated brute-force filesystem scans.
    versions_to_probe = (
        (str(ansys_version),) if ansys_version is not None else AUTO_DETECT_INSTALL_VERSIONS
    )

    for version in versions_to_probe:
        awp_root_key = f"AWP_ROOT{version}"
        if awp_root_key in os.environ:
            awp_root = Path(os.environ[awp_root_key])
            for path in _candidate_dirs_for_install_root(awp_root):
                _append_unique(candidates_by_path, path)

    if "CEIDEVROOTDOS" in os.environ:
        _append_unique(candidates_by_path, Path(os.environ["CEIDEVROOTDOS"]))

    for version in versions_to_probe:
        # Default install roots are the last probe source because env-based
        # overrides should remain higher precedence than machine-wide installs.
        for path in _candidate_dirs_for_install_root(_default_install_root(version)):
            _append_unique(candidates_by_path, path)

    return list(candidates_by_path.values())


def resolve_install_info(
    ansys_installation: str | None = None, ansys_version: int | None = None
) -> InstallResolution:
    """Resolve installation details while preserving ``get_install_info()`` semantics."""
    candidates = _build_install_candidates(
        ansys_installation=ansys_installation, ansys_version=ansys_version
    )

    install_dir: Path | None = None
    for candidate_dir in candidates:
        if candidate_dir.is_dir():
            install_dir = candidate_dir
            break

    version = get_install_version(install_dir)
    if version is None:
        version = _get_install_version_from_layout(install_dir)
    if version is None:
        version = ansys_version or int(DEFAULT_ANSYS_INSTALL_VERSION)

    if ansys_installation and (
        install_dir is None
        or not (install_dir / f"nexus{version}" / "django" / "manage.py").exists()
    ):
        raise InvalidAnsysPath(f"Unable to detect an installation in: {[str(d) for d in candidates]}")

    return InstallResolution(
        install_dir=str(install_dir) if install_dir is not None else None,
        version=version,
    )


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
    resolution = resolve_install_info(
        ansys_installation=ansys_installation, ansys_version=ansys_version
    )
    # Preserve the historical tuple return type for external callers while
    # the internal resolver returns a typed record for service/serverless code.
    return resolution.install_dir, resolution.version


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
    if template_attr["report_type"] not in REPORT_TYPES:
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


PROPERTIES_EXEMPT = {
    "link_text",
    "userdef_name",
    "filter_x_title",
    "filter_y_title",
    "labels_column",
    "labels_row",
    "title",
    "line_marker_text",
    "plot_title",
    "xtitle",
    "ytitle",
    "ztitle",
    "nan_display",
    "table_title",
    "image_title",
    "slider_title",
    "TOCName",
}


def _check_string_for_html(value: str, field_name: str) -> None:
    """Helper function to validate that a string does not contain HTML content.

    Args:
        value: String value to validate
        field_name: Name of the field being validated for error messages

    Raises:
        ValueError: If the string contains HTML content
    """
    cleaned_string = bleach.clean(value, strip=True)
    if cleaned_string != value:
        raise ValueError(f"{field_name} contains HTML content. Value: {value}")


def check_dictionary_for_html(data):
    for key, value in data.items():
        # Do not validate HTML key
        if key == "HTML":
            continue

        # Recursive case for nested dictionaries
        if isinstance(value, dict):
            # Specific checks for properties key
            if key == "properties":
                subdict = {k: v for k, v in value.items() if k not in PROPERTIES_EXEMPT}
                check_dictionary_for_html(subdict)
            else:
                check_dictionary_for_html(value)

        # Check for lists
        elif isinstance(value, list):
            check_list_for_html(value, key)

        # Main check for strings
        elif isinstance(value, str):
            _check_string_for_html(value, key)

        # Ignore other types
        else:
            continue


def check_list_for_html(value_list, key):
    for item in value_list:
        if isinstance(item, str):
            _check_string_for_html(item, key)
        elif isinstance(item, dict):
            check_dictionary_for_html(item)
        elif isinstance(item, list):
            check_list_for_html(item, key)
        else:
            continue
