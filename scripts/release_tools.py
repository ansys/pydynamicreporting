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

"""Validate release tags and the distribution artifacts associated with them."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import email.parser
import email.policy
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import zipfile


TAG_PATTERN = re.compile(
    r"^v(?P<version>(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)"
    r"(?:rc(?:0|[1-9][0-9]*))?)$"
)


class ReleaseValidationError(ValueError):
    """Raised when a release tag or artifact is not safe to publish."""


@dataclass(frozen=True)
class ReleaseTag:
    """Canonical information derived from a supported release tag."""

    tag: str
    version: str
    prerelease: bool


def parse_release_tag(tag: str) -> ReleaseTag:
    """Parse a final or release-candidate tag without normalizing it."""
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ReleaseValidationError(
            f"Unsupported release tag {tag!r}. Expected vMAJOR.MINOR.PATCH or "
            "vMAJOR.MINOR.PATCHrcN with no leading zeroes."
        )
    version = match.group("version")
    return ReleaseTag(tag=tag, version=version, prerelease="rc" in version)


def validate_git_tag(release: ReleaseTag, *, require_existing: bool, require_head: bool) -> None:
    """Verify that a release tag exists and identifies the checked-out commit."""
    if require_head:
        require_existing = True
    if not require_existing:
        return

    tag_ref = f"refs/tags/{release.tag}"
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", tag_ref], check=False)
    if exists.returncode != 0:
        raise ReleaseValidationError(f"Release tag {release.tag!r} does not exist locally.")

    if require_head:
        tag_commit = subprocess.run(
            ["git", "rev-list", "-n", "1", release.tag],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if tag_commit != head_commit:
            raise ReleaseValidationError(
                f"Checked-out commit {head_commit} does not match {release.tag} ({tag_commit})."
            )


def _normalized_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _read_wheel_metadata(path: Path) -> email.message.Message:
    with zipfile.ZipFile(path) as archive:
        metadata_files = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise ReleaseValidationError(
                f"{path.name} must contain exactly one .dist-info/METADATA file."
            )
        return email.parser.BytesParser(policy=email.policy.default).parsebytes(
            archive.read(metadata_files[0])
        )


def _read_sdist_metadata(path: Path) -> email.message.Message:
    with tarfile.open(path, "r:gz") as archive:
        pkg_info_files = [
            member
            for member in archive.getmembers()
            if member.name.endswith("/PKG-INFO") and member.name.count("/") == 1
        ]
        if len(pkg_info_files) != 1:
            raise ReleaseValidationError(
                f"{path.name} must contain exactly one top-level PKG-INFO file."
            )
        extracted = archive.extractfile(pkg_info_files[0])
        if extracted is None:
            raise ReleaseValidationError(f"Unable to read PKG-INFO from {path.name}.")
        return email.parser.BytesParser(policy=email.policy.default).parsebytes(extracted.read())


def validate_artifacts(directory: Path, package_name: str, release: ReleaseTag) -> list[Path]:
    """Validate the count, name, and version of the wheel and source distribution."""
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseValidationError(
            f"Expected one wheel and one sdist in {directory}; found {len(wheels)} wheel(s) "
            f"and {len(sdists)} sdist(s)."
        )

    expected_name = _normalized_package_name(package_name)
    artifacts_and_metadata = (
        (wheels[0], _read_wheel_metadata(wheels[0])),
        (sdists[0], _read_sdist_metadata(sdists[0])),
    )
    for artifact, metadata in artifacts_and_metadata:
        actual_name = metadata.get("Name")
        actual_version = metadata.get("Version")
        if (
            actual_name is None
            or _normalized_package_name(actual_name) != expected_name
            or actual_version != release.version
        ):
            raise ReleaseValidationError(
                f"{artifact.name} contains {actual_name!r} {actual_version!r}; expected "
                f"{package_name!r} {release.version!r}."
            )
    return [wheels[0], sdists[0]]


def _write_github_outputs(release: ReleaseTag) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        return
    with Path(output_path).open("a", encoding="utf-8") as stream:
        stream.write(f"tag={release.tag}\n")
        stream.write(f"version={release.version}\n")
        stream.write(f"prerelease={str(release.prerelease).lower()}\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_expected_prerelease(release: ReleaseTag, expected: str | None) -> None:
    if expected in (None, ""):
        return
    if expected not in {"true", "false"}:
        raise ReleaseValidationError(f"Invalid prerelease state {expected!r}.")
    if release.prerelease != (expected == "true"):
        raise ReleaseValidationError(
            f"GitHub Release prerelease state {expected!r} does not match tag {release.tag!r}."
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_tag = subparsers.add_parser("validate-tag")
    validate_tag.add_argument("tag")
    validate_tag.add_argument("--require-existing", action="store_true")
    validate_tag.add_argument("--require-head", action="store_true")
    validate_tag.add_argument("--expected-prerelease")
    validate_tag.add_argument("--ref-type")

    validate_dist = subparsers.add_parser("validate-artifacts")
    validate_dist.add_argument("tag")
    validate_dist.add_argument("directory", type=Path)
    validate_dist.add_argument("package_name")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the requested release validation command."""
    args = _build_parser().parse_args(argv)
    try:
        release = parse_release_tag(args.tag)
        if args.command == "validate-tag":
            if args.ref_type not in (None, "tag"):
                raise ReleaseValidationError(
                    f"Release publication requires a tag ref, not {args.ref_type!r}."
                )
            validate_git_tag(
                release,
                require_existing=args.require_existing,
                require_head=args.require_head,
            )
            _validate_expected_prerelease(release, args.expected_prerelease)
            _write_github_outputs(release)
            print(f"Validated release tag {release.tag} for package version {release.version}.")
        else:
            artifacts = validate_artifacts(args.directory, args.package_name, release)
            for artifact in artifacts:
                print(f"Validated {artifact.name}: sha256:{_sha256(artifact)}")
    except (OSError, ReleaseValidationError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
