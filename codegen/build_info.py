"""
Generate the _build_info.py file.

Usage
-----

`python build_info.py`
"""

import datetime
import os
import subprocess


def generate() -> None:
    """Create the ansys/dynamicreporting/core/build_info.py file."""
    root = os.path.dirname(__file__)
    os.chdir(root)

    now = datetime.datetime.now()

    cmd = ["git", "rev-parse", "--short", "HEAD"]
    ret = subprocess.run(cmd, capture_output=True)
    git_hash = ret.stdout.decode().strip()

    cmd = ["git", "branch", "--show-current"]
    ret = subprocess.run(cmd, capture_output=True)
    git_branch = ret.stdout.decode().strip()

    cmd = ["git", "describe", "--tags"]
    ret = subprocess.run(cmd, capture_output=True)
    git_describe = "unknown"
    if ret.returncode == 0:
        git_describe = ret.stdout.decode().strip()

    target = "../src/ansys/dynamicreporting/core/build_info.py"
    print(
        f"Generating build_info.py file: {now.isoformat()}, {git_branch}, {git_hash}, {git_describe}"
    )
    with open(target, "w") as fp:
        # Write license header
        fp.write("# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.\n")
        fp.write("# SPDX-License-Identifier: MIT\n")
        fp.write("#\n")
        fp.write("#\n")
        fp.write("# Permission is hereby granted, free of charge, to any person obtaining a copy\n")
        fp.write(
            '# of this software and associated documentation files (the "Software"), to deal\n'
        )
        fp.write("# in the Software without restriction, including without limitation the rights\n")
        fp.write("# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n")
        fp.write("# copies of the Software, and to permit persons to whom the Software is\n")
        fp.write("# furnished to do so, subject to the following conditions:\n")
        fp.write("#\n")
        fp.write(
            "# The above copyright notice and this permission notice shall be included in all\n"
        )
        fp.write("# copies or substantial portions of the Software.\n")
        fp.write("#\n")
        fp.write('# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n')
        fp.write("# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n")
        fp.write("# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n")
        fp.write("# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n")
        fp.write(
            "# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        )
        fp.write(
            "# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        )
        fp.write("# SOFTWARE.\n")
        fp.write("\n")
        # Write build information
        fp.write("# Build information\n")
        fp.write(f'BUILD_DATE = "{now.isoformat()}"\n')
        fp.write(f'BUILD_HASH = "{git_hash}"\n')
        fp.write(f'BUILD_BRANCH = "{git_branch}"\n')
        fp.write(f'BUILD_DESCRIPTION = "{git_describe}"\n')


if __name__ == "__main__":
    generate()
