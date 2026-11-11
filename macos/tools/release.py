#!/usr/bin/env python3
"""Build and verify an Intel macOS release; never push tags or publish to GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
import tempfile

from audit_bundle import audit
from build_app import ROOT, build, run
from build_metadata import read_version


def release_source(root: Path, tag: str) -> tuple[str, str, str]:
    """Require the release tag, version, and clean source checkout to agree."""
    version, number = read_version(root / "macos")
    if tag != f"macos-v{version}":
        raise ValueError(f"Expected tag macos-v{version}, got {tag!r}")
    if run("git", "-C", root, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Release requires a clean checkout, including untracked files")
    commit = run("git", "-C", root, "rev-parse", "HEAD").strip()
    tagged = run("git", "-C", root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}").strip()
    if tagged != commit:
        raise ValueError("Release tag does not point to HEAD")
    return version, number, commit


def logged(command: list[str | Path], directory: Path, name: str,
           *, timeout: int = 600) -> str:
    """Keep complete diagnostics, including failed checks, out of published assets."""
    print(f"Running {name}…", flush=True)
    with (directory / f"{name}.stdout").open("w") as out, \
            (directory / f"{name}.stderr").open("w") as err:
        subprocess.run([str(arg) for arg in command], cwd=ROOT.parent, check=True,
                       stdout=out, stderr=err, timeout=timeout)
    return (directory / f"{name}.stdout").read_text()


def check_signing(details: str) -> None:
    if ("Authority=Developer ID Application:" not in details
            or not re.search(r"flags=.*\bruntime\b", details)
            or not re.search(r"^TeamIdentifier=(?!not set$)\S+", details, re.MULTILINE)):
        raise ValueError("Distribution requires Developer ID signing and hardened runtime")


def check_provenance(app: Path, version: str, number: str, commit: str) -> dict:
    contents = app / "Contents"
    info = plistlib.loads((contents / "Info.plist").read_bytes())
    manifest = json.loads((contents / "Resources/build-manifest.json").read_text())
    if (info["CFBundleShortVersionString"] != version or info["CFBundleVersion"] != number
            or manifest["source_commit"] != commit or manifest["source_dirty"]
            or manifest["version"] != version or manifest["build_number"] != number
            or manifest["architecture"] != "x86_64"):
        raise ValueError("Built app does not match the clean tagged source and version")
    return manifest


def zip_app(app: Path, output: Path) -> None:
    # ditto preserves framework symlinks, executable bits, and macOS metadata.
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, output)


def notarize(app: Path, profile: str, logs: Path) -> None:
    upload = logs / "notarization-upload.zip"
    zip_app(app, upload)
    result = json.loads(logged(["xcrun", "notarytool", "submit", upload,
                                "--keychain-profile", profile, "--wait", "--timeout", "30m",
                                "--output-format", "json"], logs, "notarization", timeout=1900))
    if result.get("status") != "Accepted":
        raise ValueError(f"Notarization was not accepted: {result.get('status')}; "
                         f"submission {result.get('id')}. See {logs}")
    logged(["xcrun", "stapler", "staple", app], logs, "staple")
    logged(["xcrun", "stapler", "validate", app], logs, "staple-validation")
    logged(["spctl", "--assess", "--type", "execute", "--verbose=2", app], logs, "gatekeeper")


def write_checksums(directory: Path) -> None:
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    lines = []
    for path in files:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(f"{digest}  {path.name}\n")
    (directory / "SHA256SUMS").write_text("".join(lines))


def release(tag: str, notes: Path, *, preview: bool, identity: str | None,
            profile: str | None, check_only: bool = False) -> Path | None:
    version, number, commit = release_source(ROOT.parent, tag)
    if sys.platform != "darwin" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 12):
        raise ValueError("Use Intel macOS with framework CPython 3.12 to build and run release checks")
    if preview:
        if identity or profile:
            raise ValueError("--preview cannot be combined with signing/notarization options")
        identity = "-"
    elif not identity or not identity.startswith("Developer ID Application:") or not profile:
        raise ValueError("Provide --identity 'Developer ID Application: …' and --notary-profile, "
                         "or explicitly choose --preview")
    release_notes = notes.read_text().strip()
    if not release_notes:
        raise ValueError("Release notes must not be empty")
    flavor = "preview" if preview else "notarized"
    destination = ROOT / "dist/releases" / f"{tag}-{flavor}"
    if destination.exists():
        raise FileExistsError(f"Refusing to replace existing release: {destination}")
    if check_only:
        print(f"Ready: {tag}, build {number}, {commit}, Intel {flavor}")
        return None

    (ROOT / ".build").mkdir(exist_ok=True)
    logs = Path(tempfile.mkdtemp(prefix=f"release-{tag}-", dir=ROOT / ".build"))
    print(f"Diagnostics: {logs}", flush=True)
    logged([sys.executable, "-m", "pytest", "-c", ROOT / "pyproject.toml",
            ROOT / "tests", ROOT.parent / "tests_core", "-q"], logs, "tests")
    logged([sys.executable, "-m", "ruff", "check", ROOT / "src", ROOT / "tools", ROOT / "tests"],
           logs, "lint")
    try:
        app = build(ROOT.parent, identity)
    except subprocess.CalledProcessError as error:
        (logs / "build.stderr").write_text(error.stderr or str(error))
        raise
    check_provenance(app, version, number, commit)
    report = audit(app)
    (logs / "bundle-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    if not preview:
        details = subprocess.run(["codesign", "-dv", "--verbose=4", str(app)], check=True,
                                 capture_output=True, text=True).stderr
        (logs / "signing.txt").write_text(details)
        check_signing(details)
        notarize(app, profile, logs)
        audit(app)  # Recheck the bundle after stapling.

    fixture = logs / "unselected.txt"
    fixture.write_text("This file must be inaccessible to the sandboxed app.\n")
    executable = app / "Contents/MacOS/Pagemark"
    logged([executable, "--probe-runtime", "--denied-file", fixture], logs, "runtime-probe", timeout=120)
    logged([executable, "--probe-editor"], logs, "editor-probe", timeout=120)
    if release_source(ROOT.parent, tag) != (version, number, commit):
        raise ValueError("Release source changed during the build")

    # Publish artifacts locally only after all required checks pass. A failed
    # archive/round-trip remains in the diagnostics folder, never at destination.
    assets = logs / "assets"
    assets.mkdir()
    name = f"Pagemark-{version}-macOS-x86_64{'-preview' if preview else ''}.zip"
    zip_app(app, assets / name)
    unpacked = logs / "unpacked"
    run("ditto", "-x", "-k", assets / name, unpacked)
    restored_app = unpacked / "Pagemark.app"
    audit(restored_app)
    manifest = check_provenance(restored_app, version, number, commit)
    if not preview:
        logged(["xcrun", "stapler", "validate", restored_app], logs, "archive-staple-validation")
    release_info = {"tag": tag, "commit": commit, "version": version, "build_number": number,
                    "architecture": "x86_64", "minimum_macos": "12.0", "preview": preview,
                    "notarized": not preview, "archive": name, "bundle_audit": report,
                    "build_manifest": manifest}
    (assets / "release.json").write_text(json.dumps(release_info, indent=2) + "\n")
    status = ("Developer preview: ad-hoc signed and NOT notarized. Gatekeeper may block opening."
              if preview else "Developer ID signed and notarized; ticket stapled to the app.")
    (assets / "RELEASE_NOTES.md").write_text(
        f"# Pagemark {version} for Intel Mac\n\nmacOS 12 or later; x86_64 only.\n\n{status}\n\n"
        f"{release_notes}\n\nSource: `{tag}` (`{commit}`), build {number}.\n")
    write_checksums(assets)
    destination.parent.mkdir(parents=True, exist_ok=True)
    assets.rename(destination)
    print(f"Release artifacts: {destination}", flush=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Existing macos-vX.Y.Z tag at HEAD")
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--preview", action="store_true", help="Explicit ad-hoc, non-notarized preview")
    parser.add_argument("--identity", help="Developer ID Application certificate name")
    parser.add_argument("--notary-profile", help="Credentials already stored by notarytool in Keychain")
    parser.add_argument("--check", action="store_true", help="Validate source/options without building")
    args = parser.parse_args()
    try:
        release(args.tag, args.notes, preview=args.preview, identity=args.identity,
                profile=args.notary_profile, check_only=args.check)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Release failed: {error}") from error


if __name__ == "__main__":
    main()
