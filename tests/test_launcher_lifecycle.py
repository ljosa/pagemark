"""Exercise the native host's shutdown with real Python-backed Cocoa objects.

This development executable tests ownership, not App Sandbox. It uses the
production launcher and Python entry point, but a tiny probe with no windows,
network, document access or print jobs. Security acceptance uses the signed app.
"""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

import pytest


@pytest.fixture(scope="module")
def lifecycle_host(tmp_path_factory):
    if sys.platform != "darwin" or sys.version_info[:2] != (3, 12):
        pytest.skip("The native launcher requires macOS and framework Python 3.12")
    framework = Path(sys.base_prefix)
    if not (framework / "Python").is_file():
        pytest.skip("The native launcher requires a framework Python installation")
    root = Path(__file__).resolve().parents[1]
    contents = tmp_path_factory.mktemp("lifecycle") / "Test.app/Contents"
    binary = contents / "MacOS/Pagemark"
    binary.parent.mkdir(parents=True)
    runtime = contents / "Frameworks/Python.framework/Versions/3.12"
    runtime.parent.mkdir(parents=True)
    runtime.symlink_to(framework, target_is_directory=True)
    packages = contents / "Resources/python"
    packages.mkdir(parents=True)
    for name in ("objc", "AppKit", "Foundation", "CoreFoundation", "PyObjCTools"):
        spec = importlib.util.find_spec(name)
        if spec is None:
            pytest.skip(f"The native launcher test requires {name}")
        (packages / name).symlink_to(next(iter(spec.submodule_search_locations)),
                                    target_is_directory=True)
    app = packages / "pagemark_app"
    app.mkdir()
    (app / "__init__.py").write_text("")
    shutil.copy2(root / "src/pagemark_app/__main__.py", app / "__main__.py")
    (app / "probe.py").write_text('''
import AppKit as A
import sys

class LifecycleView(A.NSView):
    def __del__(self):
        print("Python-backed view released; finalizing=" + str(sys.is_finalizing()), flush=True)

def run(outcome, *, include_editor):
    assert not include_editor
    view = LifecycleView.alloc().initWithFrame_(((0, 0), (100, 100)))
    operation = A.NSPrintOperation.printOperationWithView_printInfo_(
        view, A.NSPrintInfo.sharedPrintInfo().copy())
    assert operation.view() == view
    print("Native print operation created", flush=True)
    if outcome == "exception":
        raise RuntimeError("deliberate probe failure")
    return int(outcome)
''')
    subprocess.run([
        "xcrun", "clang", "-Wall", "-Wextra", "-Werror",
        "-I" + sysconfig.get_path("include"), root / "packaging/launcher.m",
        framework / "Python", "-framework", "AppKit", "-o", binary,
    ], check=True, capture_output=True, text=True)
    return binary


@pytest.mark.parametrize(("outcome", "exit_status"), [("0", 0), ("7", 7), ("exception", 1)])
def test_cocoa_objects_release_before_python_shutdown(lifecycle_host, outcome, exit_status):
    result = subprocess.run(
        [lifecycle_host, "--probe-runtime", "--denied-file", outcome],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == exit_status, result.stdout + result.stderr
    assert "Native print operation created" in result.stdout
    assert "Python-backed view released; finalizing=" in result.stdout
    if outcome == "exception":
        # CPython may keep sys.last_exc's traceback (and the view in its frame)
        # until finalization. Its callback must still run and exit normally;
        # it must never be deferred beyond Py_RunMain to a native outer pool.
        assert "RuntimeError: deliberate probe failure" in result.stderr
    else:
        assert "Python-backed view released; finalizing=False" in result.stdout
