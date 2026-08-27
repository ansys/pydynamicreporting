# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
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

from io import BytesIO
from pathlib import Path
import tarfile
import zipfile

import pytest

from scripts.release_tools import ReleaseValidationError
from scripts.release_tools import _write_github_outputs
from scripts.release_tools import main
from scripts.release_tools import parse_release_tag
from scripts.release_tools import validate_artifacts


def _write_artifacts(directory: Path, *, name: str, version: str) -> None:
    metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\n".encode()
    wheel = directory / f"ansys_dynamicreporting_core-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"ansys_dynamicreporting_core-{version}.dist-info/METADATA", metadata)

    sdist = directory / f"ansys_dynamicreporting_core-{version}.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo(f"ansys_dynamicreporting_core-{version}/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, BytesIO(metadata))


@pytest.mark.parametrize(
    ("tag", "version", "prerelease"),
    [("v1.0.0", "1.0.0", False), ("v1.0.0rc1", "1.0.0rc1", True)],
)
def test_parse_release_tag(tag: str, version: str, prerelease: bool) -> None:
    release = parse_release_tag(tag)
    assert release.version == version
    assert release.prerelease is prerelease


@pytest.mark.parametrize(
    "tag",
    ["1.0.0", "v1.0", "v1.0.0.dev1", "v1.0.0a1", "v01.0.0", "v1.0.0rc01"],
)
def test_parse_release_tag_rejects_unsupported_tags(tag: str) -> None:
    with pytest.raises(ReleaseValidationError, match="Unsupported release tag"):
        parse_release_tag(tag)


def test_validate_tag_command_rejects_branch_ref(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-tag", "v1.0.0", "--ref-type", "branch"]) == 1
    assert "requires a tag ref" in capsys.readouterr().err


def test_validate_tag_command_rejects_prerelease_mismatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate-tag", "v1.0.0rc1", "--expected-prerelease", "false"]) == 1
    assert "does not match tag" in capsys.readouterr().err


def test_write_github_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    _write_github_outputs(parse_release_tag("v1.0.0rc1"))
    assert output.read_text(encoding="utf-8").splitlines() == [
        "tag=v1.0.0rc1",
        "version=1.0.0rc1",
        "prerelease=true",
    ]


def test_validate_artifacts(tmp_path: Path) -> None:
    _write_artifacts(tmp_path, name="ansys-dynamicreporting-core", version="1.0.0rc1")
    artifacts = validate_artifacts(
        tmp_path, "ansys-dynamicreporting-core", parse_release_tag("v1.0.0rc1")
    )
    assert {artifact.suffix for artifact in artifacts} == {".whl", ".gz"}


def test_validate_artifacts_rejects_version_mismatch(tmp_path: Path) -> None:
    _write_artifacts(tmp_path, name="ansys-dynamicreporting-core", version="1.0.0")
    with pytest.raises(ReleaseValidationError, match="expected"):
        validate_artifacts(tmp_path, "ansys-dynamicreporting-core", parse_release_tag("v1.0.0rc1"))
