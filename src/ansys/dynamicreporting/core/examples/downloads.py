"""Functions to download sample datasets from the Ansys example data repository."""

import logging
import os
from pathlib import Path
import re
from urllib import parse, request

import ansys.dynamicreporting.core as adr


class RemoteFileNotFoundError(FileNotFoundError):
    """Raised on an attempt to download a non-existent remote file."""

    def __init__(self, url):
        """Initializes RemoteFileNotFoundError."""
        super().__init__(f"{url} does not exist.")


def uri_validator(url: str) -> bool:
    try:
        result = parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False


def check_url_exists(url: str) -> bool:
    """Check if a URL exists.

    Parameters
    ----------
    url : str
        URL to check

    Returns
    -------
    bool
        True if the URL exists, False otherwise
    """
    if uri_validator(url) is False:
        logging.debug(f"Passed url is invalid: {url}\n")
        return False
    try:
        with request.urlopen(url) as response:
            return response.status == 200
    except Exception:
        return False


def get_url_content(url: str) -> str:
    """Get the content of a URL.

    Parameters
    ----------
    url : str
        URL to get content from

    Returns
    -------
    str
        content of the URL
    """
    with request.urlopen(url) as response:
        return response.read()


def _get_file_url(file_name: str, directory: str | None = None) -> str:
    """Get file URL."""
    if directory:
        return (
            "https://github.com/ansys/example-data/raw/refs/heads/master/pydynamicreporting/"
            f"{directory}/{file_name}"
        )
    return f"https://github.com/ansys/example-data/raw/refs/heads/master/pydynamicreporting/{file_name}"


def _retrieve_file(
    url: str,
    file_name: str,
    save_path: str | None = None,
) -> str:
    """Download specified file from specified URL."""
    file_name = os.path.basename(file_name)
    if save_path is None:
        save_path = os.getcwd()
    else:
        save_path = os.path.abspath(save_path)
    local_path = os.path.join(save_path, file_name)
    # First check if file has already been downloaded
    logging.debug(f"Checking if {local_path} already exists...")
    if os.path.isfile(local_path) or os.path.isdir(local_path):
        logging.debug("File already exists.")
        return local_path

    logging.debug("File does not exist. Downloading specified file...")

    # Check if save path exists
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # Download file
    logging.debug(f'Downloading URL: "{url}"')
    content = get_url_content(url)
    with open(local_path, "wb") as f:
        f.write(content)

    logging.debug("Download successful.")
    return local_path


def download_file(
    file_name: str,
    directory: str | None = None,
    save_path: str | None = None,
) -> str:
    """Download specified example file from the Ansys example data repository.

    Parameters
    ----------
    file_name : str
        File to download.
    directory : str, optional
        Ansys example data repository directory where specified file is located. If not specified, looks for the file
        in the root directory of the repository.
    save_path : str, optional
        Path to download the specified file to.

    Raises
    ------
    RemoteFileNotFoundError
        If remote file does not exist.

    Returns
    -------
    str
        file path of the downloaded or already existing file.

    Examples
    --------
    >>> from ansys.dynamicreporting.core import examples
    >>> file_path = examples.download_file("bracket.iges", "geometry")
    >>> file_path
    '/home/user/.local/share/adr_core/examples/bracket.iges'
    """

    url = _get_file_url(file_name, directory)
    if not check_url_exists(url):
        raise RemoteFileNotFoundError(url)
    return _retrieve_file(url, file_name, save_path)
