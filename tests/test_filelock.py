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

import os
from os.path import join
import platform

import pytest
from ansys.dynamicreporting.core.utils import filelock as fl

msvcrt = None
try:
    import msvcrt as msvcrt
except ImportError:
    pass
fcntl = None
try:
    import fcntl as fcntl
except ImportError:
    pass

open_mode = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC


@pytest.mark.ado_test
def test_timeout(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "time.txt")
    open(tmp_file, "a").close()
    a = fl.Timeout(lock_file=tmp_file)
    assert "could not be acquired" in a.__str__()


@pytest.mark.ado_test
def test_base_acquire(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    a.timeout = 2.0
    try:
        a.acquire(timeout=None)
        success = False
    except NotImplementedError:
        success = True
    assert success


@pytest.mark.ado_test
def test_base_release(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base2.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    a.timeout = 2.0
    try:
        a._release()
        success = False
    except NotImplementedError:
        success = True
    assert success


@pytest.mark.ado_test
def test_base_locked(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base3.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    assert a.is_locked is False


@pytest.mark.ado_test
def test_base_rel(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base4.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    assert a.release() is None


@pytest.mark.ado_test
def test_platform_lock(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "platform.txt")
    tmp_file2 = join(test_path, "platform2.txt")
    open(tmp_file, "a").close()
    a = None
    if msvcrt:
        a = fl.WindowsFileLock(lock_file=tmp_file)
    elif fcntl:
        a = fl.UnixFileLock(lock_file=tmp_file)
    else:
        pytest.skip("No platform-specific file locking module is available.")
    try:
        one = a._acquire()
    except AttributeError:
        one = None
    if a._lock_file_fd is None:
        a._lock_file_fd = os.open(tmp_file2, open_mode)
    two = a._release()
    assert one is None and two is None


@pytest.mark.ado_test
def test_soft(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "soft.txt")
    tmp_file2 = join(test_path, "soft2.txt")
    open(tmp_file, "a").close()
    a = fl.SoftFileLock(lock_file=tmp_file)
    if a._lock_file_fd is None:
        a._lock_file_fd = os.open(tmp_file2, open_mode)
    rel = a._release()
    assert rel is None


def test_nexus_filelock(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "n_lock.txt")

    lock = fl.nexus_file_lock(filename=tmp_file)

    # Debug info
    print("Resolved lock type:", type(lock))
    print("Expected FileLock type:", fl.FileLock)

    assert isinstance(lock, fl.FileLock)
