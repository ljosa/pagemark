#!/usr/bin/env python3
"""Build a self-contained, sandboxed app from the interpreter running this script.

No package installation or source-tree modification happens during the build.
All non-system Mach-O dependencies are copied, relocated, audited, and signed.
The build manifest records exact package versions and shared-core file hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "pyobjc-core": "12.1", "pyobjc-framework-Cocoa": "12.1",
    "reportlab": "4.4.9", "pillow": "12.1.0",
    "charset-normalizer": "3.4.4", "wcwidth": "0.2.13",
}
CORE_MODULES = (
    "buffer", "coordinates", "layout", "navigation", "viewport", "text_layout",
    "font_config", "print_formatter", "pdf_generator", "booklet",
    "model", "clipboard", "rtf_parser",
)
MACH_MAGIC = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
              b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def run(*args: str | Path) -> str:
    result = subprocess.run([str(a) for a in args], check=True, capture_output=True, text=True)
    return result.stdout


def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(4) in MACH_MAGIC


def dependencies(path: Path) -> list[str]:
    return [line.strip().split(" (compatibility", 1)[0]
            for line in run("otool", "-L", path).splitlines()[1:]
            if line.startswith("\t")]


def system_library(name: str) -> bool:
    return name.startswith(("/usr/lib/", "/System/Library/"))


def copy_runtime(app: Path) -> dict[Path, Path]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if version != "3.12" or sys.platform != "darwin":
        raise RuntimeError("Build with macOS CPython 3.12")
    original = Path(sys.base_prefix).resolve()
    binary = original / "Python"
    if not binary.is_file():
        raise RuntimeError("This builder requires a framework CPython installation")
    target = app / "Contents/Frameworks/Python.framework/Versions" / version
    target.mkdir(parents=True)
    shutil.copy2(binary, target / "Python")
    ignore = shutil.ignore_patterns(
        "site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter",
        "turtledemo", "ensurepip", "config-3.12-darwin", "_test*", "_xx*", "xx*", "*.pyc",
    )
    shutil.copytree(original / "lib" / f"python{version}",
                    target / "lib" / f"python{version}", ignore=ignore)
    resources = original / "Resources"
    (target / "Resources").mkdir()
    shutil.copy2(resources / "Info.plist", target / "Resources/Info.plist")
    framework = target.parents[1]
    (framework / "Versions/Current").symlink_to(version)
    (framework / "Python").symlink_to("Versions/Current/Python")
    (framework / "Resources").symlink_to("Versions/Current/Resources")
    origins = {p: original / p.relative_to(target) for p in target.rglob("*") if is_macho(p)}
    return origins


def copy_packages(destination: Path) -> dict[Path, Path]:
    origins = {}
    for name, expected in PACKAGES.items():
        dist = metadata.distribution(name)
        if dist.version != expected:
            raise RuntimeError(f"Expected {name}=={expected}; found {dist.version}")
        package_root = Path(dist.locate_file("")).resolve()
        for entry in dist.files or ():
            relative = Path(str(entry))
            if relative.is_absolute() or ".." in relative.parts:
                continue  # Never include external entry-point scripts.
            if "__pycache__" in relative.parts or relative.suffix == ".pyc":
                continue
            source = Path(dist.locate_file(entry))
            if not source.is_file():
                continue
            if not source.resolve().is_relative_to(package_root):
                raise RuntimeError(f"Package file escapes its installation root: {entry}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if is_macho(target):
                origins[target] = source.resolve()
    return origins


def copy_core(source: Path, destination: Path) -> dict[str, str]:
    destination.mkdir(parents=True)
    (destination / "__init__.py").write_text(
        '"""Unmodified modules from Pagemark; see build-manifest.json."""\n')
    hashes = {}
    for name in CORE_MODULES:
        module = source / "pagemark" / f"{name}.py"
        if not module.resolve().is_relative_to((source / "pagemark").resolve()):
            raise RuntimeError(f"Core source escapes its package: {module}")
        data = module.read_bytes()
        (destination / f"{name}.py").write_bytes(data)
        hashes[f"pagemark/{name}.py"] = hashlib.sha256(data).hexdigest()
    return hashes


def relocate_libraries(app: Path, origins: dict[Path, Path]) -> None:
    bundled = {source.resolve(): target for target, source in origins.items()}
    queue = list(origins)
    for target in queue:
        source = origins[target]
        ids = run("otool", "-D", target).splitlines()[1:]
        identity = ids[0].strip() if ids else None
        for name in dependencies(target):
            if system_library(name) or name == identity:
                continue
            if name.startswith("@loader_path/"):
                resolved = (source.parent / name[len("@loader_path/"):]).resolve()
            elif name.startswith("/"):
                resolved = Path(name).resolve()
            else:
                raise RuntimeError(f"Unresolved dependency {name!r} in {source}")
            if resolved not in bundled:
                if not resolved.is_file():
                    raise RuntimeError(f"Missing dependency: {resolved}")
                digest = hashlib.sha256(str(resolved).encode()).hexdigest()[:12]
                dest = app / "Contents/Frameworks/Libraries" / digest / resolved.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolved, dest)
                bundled[resolved] = dest
                origins[dest] = resolved
                queue.append(dest)
            local = "@loader_path/" + os.path.relpath(bundled[resolved], target.parent)
            target.chmod(target.stat().st_mode | 0o200)
            run("install_name_tool", "-change", name, local, target)
        if identity:
            run("install_name_tool", "-id", "@rpath/" + target.name, target)
    # Check that every runtime load is either a system library or inside this app.
    for target in origins:
        ids = run("otool", "-D", target).splitlines()[1:]
        identity = ids[0].strip() if ids else None
        for name in dependencies(target):
            if system_library(name) or name == identity:
                continue
            if not name.startswith("@loader_path/"):
                raise RuntimeError(f"External dependency after relocation: {name}")
            resolved = (target.parent / name[len("@loader_path/"):]).resolve()
            if not resolved.is_relative_to(app.resolve()) or not resolved.is_file():
                raise RuntimeError(f"Dependency escapes bundle: {name} in {target}")


def build(core: Path, identity: str) -> Path:
    stage = ROOT / ".build/Pagemark.app"
    final = ROOT / "dist/Pagemark.app"
    if stage.exists():
        shutil.rmtree(stage)
    contents = stage / "Contents"
    python = contents / "Resources/python"
    python.mkdir(parents=True)
    (contents / "MacOS").mkdir()
    origins = copy_runtime(stage)
    origins.update(copy_packages(python))
    shutil.copytree(ROOT / "src/pagemark_app", python / "pagemark_app",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    core_hashes = copy_core(core, python / "pagemark_core")
    manifest = {
        "python": sys.version.split()[0], "packages": PACKAGES, "core_files": core_hashes,
        "core_commit": run("git", "-C", core, "rev-parse", "HEAD").strip(),
        "signing": "ad-hoc development" if identity == "-" else "Developer ID",
        "hardened_runtime": identity != "-",
        "sandboxed": True,
    }
    (contents / "Resources/build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    plist = {
        "CFBundleName": "Pagemark", "CFBundleDisplayName": "Pagemark",
        "CFBundleExecutable": "Pagemark", "CFBundleIdentifier": "org.pagemark.mac",
        "CFBundlePackageType": "APPL", "CFBundleVersion": "13",
        "CFBundleShortVersionString": "0.2.11", "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True, "NSPrincipalClass": "NSApplication",
        "CFBundleDocumentTypes": [{"CFBundleTypeName": "Pagemark text",
            "CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate",
            "LSItemContentTypes": ["public.plain-text"],
            "NSDocumentClass": "PagemarkDocument"}],
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
    launcher = contents / "MacOS/Pagemark"
    framework = Path(sys.base_prefix).resolve() / "Python"
    run("xcrun", "clang", "-arch", "x86_64", "-mmacosx-version-min=12.0",
        "-Werror", "-Wall", "-Wextra", "-Wl,-headerpad_max_install_names",
        "-I" + sysconfig.get_path("include"), ROOT / "packaging/launcher.m", framework,
        "-framework", "AppKit",
        "-o", launcher)
    origins[launcher] = launcher
    relocate_libraries(stage, origins)
    manifest["native_sources"] = [
        {"bundle_path": str(target.relative_to(stage)), "name": source.name,
         "sha256_before_signing": hashlib.sha256(source.read_bytes()).hexdigest()}
        for target, source in sorted(origins.items())
    ]
    (contents / "Resources/build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Ad-hoc signatures have no Team ID; hardened runtime's library validation
    # cannot accept bundled non-platform libraries with those signatures.
    # App Sandbox remains enabled in development. Developer ID builds enable
    # hardened runtime without a disable-library-validation exception.
    sign_options = [] if identity == "-" else ["--options", "runtime", "--timestamp"]
    for target in sorted(origins, key=lambda p: len(p.parts), reverse=True):
        if target == launcher:
            continue
        run("codesign", "--force", "--sign", identity, *sign_options, target)
    framework_root = contents / "Frameworks/Python.framework"
    run("codesign", "--force", "--sign", identity, *sign_options, framework_root)
    run("codesign", "--force", "--sign", identity, *sign_options,
        "--entitlements", ROOT / "packaging/entitlements.plist", stage)
    run("codesign", "--verify", "--deep", "--strict", stage)
    final.parent.mkdir(exist_ok=True)
    if final.exists():
        shutil.rmtree(final)
    stage.rename(final)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, default=ROOT.parent / "pagemark")
    parser.add_argument("--identity", default="-", help="Signing identity; default is local ad-hoc")
    args = parser.parse_args()
    try:
        print(build(args.core.resolve(), args.identity), flush=True)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        raise SystemExit(f"Build failed: {' '.join(str(a) for a in exc.cmd)}") from exc


if __name__ == "__main__":
    main()

