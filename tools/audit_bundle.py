#!/usr/bin/env python3
"""Fail if a built app escapes its bundle or grants network/broad file access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

from build_app import ROOT, dependencies, is_macho, system_library

ALLOWED_ENTITLEMENTS = {
    "com.apple.security.app-sandbox",
    "com.apple.security.files.user-selected.read-write",
    "com.apple.security.print",
    "com.apple.security.cs.allow-jit",
}


def audit(app: Path) -> dict:
    app = app.resolve()
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    signed = subprocess.run(["codesign", "-d", "--entitlements", ":-", str(app)],
                            check=True, capture_output=True)
    entitlements = plistlib.loads(signed.stdout.rstrip(b"\x00"))
    if entitlements != dict.fromkeys(ALLOWED_ENTITLEMENTS, True):
        raise ValueError(f"Unexpected entitlements: {entitlements}")
    launcher = app / "Contents/MacOS/Pagemark"
    if not any(name.startswith("/System/Library/Frameworks/AppKit.framework/")
               for name in dependencies(launcher)):
        raise ValueError("The native launcher must link AppKit at load time")
    native_count = 0
    for path in app.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(app):
            raise ValueError(f"Symlink escapes bundle: {path}")
        if not is_macho(path):
            continue
        native_count += 1
        ids = subprocess.run(["otool", "-D", str(path)], check=True,
                             capture_output=True, text=True).stdout.splitlines()[1:]
        identity = ids[0].strip() if ids else None
        for name in dependencies(path):
            if system_library(name) or name == identity:
                continue
            if not name.startswith("@loader_path/"):
                raise ValueError(f"Non-system external library: {name} in {path}")
            resolved = (path.parent / name[len("@loader_path/"):]).resolve()
            if not resolved.is_relative_to(app) or not resolved.exists():
                raise ValueError(f"Missing/escaping library: {name} in {path}")
    manifest = json.loads((app / "Contents/Resources/build-manifest.json").read_text())
    for relative, expected in manifest["core_files"].items():
        module = app / "Contents/Resources/python/pagemark_core" / Path(relative).name
        if hashlib.sha256(module.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Shared core hash mismatch: {relative}")
    return {"signature": "valid", "entitlements": entitlements,
            "appkit_linked_at_launch": True,
            "native_binaries_checked": native_count,
            "self_contained": True, "signing": manifest["signing"],
            "hardened_runtime": manifest["hardened_runtime"],
            "size_bytes": sum(p.stat().st_size for p in app.rglob("*")
                              if p.is_file() and not p.is_symlink())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", type=Path, default=ROOT / "dist/Pagemark.app")
    args = parser.parse_args()
    print(json.dumps(audit(args.app), indent=2))

