import os
from os.path import join
import platform

import pytest

try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None

from ansys.dynamicreporting.core.utils import filelock as fl

open_mode = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC


@pytest.mark.ado_test
def test_timeout(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "time.txt")
    open(tmp_file, "a").close()
    a = fl.Timeout(lock_file=tmp_file)
    assert "could not be acquired" in a.__str__()


@pytest.mark.ado_test
def test_base_acquire(request) -> bool:
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
def test_base_release(request) -> bool:
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
def test_base_locked(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base3.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    assert a.is_locked is False


@pytest.mark.ado_test
def test_base_rel(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "base4.txt")
    open(tmp_file, "a").close()
    a = fl.BaseFileLock(lock_file=tmp_file)
    assert a.release() is None


@pytest.mark.ado_test
def test_platform_lock(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "platform.txt")
    tmp_file2 = join(test_path, "platform2.txt")
    open(tmp_file, "a").close()
    if msvcrt:
        a = fl.WindowsFileLock(lock_file=tmp_file)
    elif fcntl:
        a = fl.UnixFileLock(lock_file=tmp_file)
    try:
        one = a._acquire()
    except AttributeError:
        one = None
    if a._lock_file_fd is None:
        a._lock_file_fd = os.open(tmp_file2, open_mode)
    two = a._release()
    assert one is None and two is None


@pytest.mark.ado_test
def test_soft(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "soft.txt")
    tmp_file2 = join(test_path, "soft2.txt")
    open(tmp_file, "a").close()
    a = fl.SoftFileLock(lock_file=tmp_file)
    if a._lock_file_fd is None:
        a._lock_file_fd = os.open(tmp_file2, open_mode)
    rel = a._release()
    assert rel is None


def test_nexus_filelock(request) -> bool:
    test_path = join(request.fspath.dirname, "test_data")
    tmp_file = join(test_path, "n_lock.txt")
    try:
        success = type(fl.nexus_file_lock(filename=tmp_file)) is fl.FileLock
    except OSError:  # Error due to not being able to get os.getlogin() on the machine
        success = True
    else:
        success = False
    if "win" in platform.system().lower():
        success = True
    assert success
