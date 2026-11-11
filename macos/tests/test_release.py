"""Release guards use real Git histories and verify archive provenance."""
import hashlib
import json
import plistlib
import subprocess

import pytest

from build_metadata import read_version
from release import check_provenance, check_signing, release_source, write_checksums


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Release Test")
    git(tmp_path, "config", "user.email", "release-test@example.invalid")
    (tmp_path / "macos").mkdir()
    (tmp_path / "macos/pyproject.toml").write_text(
        '[project]\nversion = "1.2.3"\n[tool.pagemark]\nbuild-number = 7\n')
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture")
    git(tmp_path, "tag", "macos-v1.2.3")
    return tmp_path


def test_clean_tag_produces_exact_source_identity(repo):
    assert release_source(repo, "macos-v1.2.3") == ("1.2.3", "7", git(repo, "rev-parse", "HEAD"))


@pytest.mark.parametrize("change", ["tracked", "untracked", "staged", "moved_head"])
def test_release_rejects_dirty_or_wrong_commit(repo, change):
    if change == "tracked":
        with (repo / "macos/pyproject.toml").open("a") as stream:
            stream.write("\n# changed\n")
    else:
        (repo / "new.txt").write_text("change")
        if change in ("staged", "moved_head"):
            git(repo, "add", "new.txt")
        if change == "moved_head":
            git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "Later commit")
    with pytest.raises(ValueError, match="clean checkout|does not point to HEAD"):
        release_source(repo, "macos-v1.2.3")


def test_release_rejects_mismatched_or_missing_tag(repo):
    with pytest.raises(ValueError, match="Expected tag"):
        release_source(repo, "macos-v1.2.4")
    git(repo, "tag", "-d", "macos-v1.2.3")
    with pytest.raises(subprocess.CalledProcessError):
        release_source(repo, "macos-v1.2.3")


@pytest.mark.parametrize("version,number", [("1.2.3-beta", 1), ("../escape", 1),
                                           ("1.2.3", 0), ("1.2.3", True)])
def test_invalid_version_metadata_is_rejected(tmp_path, version, number):
    value = str(number).lower() if isinstance(number, bool) else str(number)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n[tool.pagemark]\nbuild-number = {value}\n')
    with pytest.raises(ValueError):
        read_version(tmp_path)


def test_release_checksums_cover_actual_artifact_bytes(tmp_path):
    (tmp_path / "app.zip").write_bytes(b"test archive")
    (tmp_path / "release.json").write_text('{}\n')
    write_checksums(tmp_path)
    for line in (tmp_path / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ")
        assert digest == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    before = (tmp_path / "SHA256SUMS").read_bytes()
    write_checksums(tmp_path)
    assert (tmp_path / "SHA256SUMS").read_bytes() == before


def test_distribution_signing_requires_certificate_team_and_hardened_runtime():
    valid = 'Authority=Developer ID Application: Test\nTeamIdentifier=TEAM123\nflags=0x10000(runtime)'
    check_signing(valid)
    for invalid in (valid.replace('(runtime)', ''), valid.replace('Developer ID Application', 'Apple Development'),
                    valid.replace('TEAM123', 'not set'), 'Signature=adhoc'):
        with pytest.raises(ValueError):
            check_signing(invalid)


@pytest.mark.parametrize("bad", [None, "version", "build_number", "source_commit", "source_dirty"])
def test_bundle_provenance_must_match_tagged_checkout(tmp_path, bad):
    contents = tmp_path / "Contents"
    (contents / "Resources").mkdir(parents=True)
    (contents / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleShortVersionString": "1.2.3", "CFBundleVersion": "7"}))
    manifest = dict(version="1.2.3", build_number="7", source_commit="abc123",
                    source_dirty=False, architecture="x86_64")
    if bad:
        manifest[bad] = True if bad == "source_dirty" else "wrong"
    (contents / "Resources/build-manifest.json").write_text(json.dumps(manifest))
    if bad:
        with pytest.raises(ValueError):
            check_provenance(tmp_path, "1.2.3", "7", "abc123")
    else:
        assert check_provenance(tmp_path, "1.2.3", "7", "abc123") == manifest


@pytest.mark.parametrize("status", ["Invalid", "In Progress", None])
def test_notarization_failure_never_staples_or_assesses(tmp_path, monkeypatch, status):
    import release as module

    commands = []
    monkeypatch.setattr(module, "zip_app", lambda app, output: None)

    def logged(command, directory, name, **kwargs):
        commands.append(name)
        return json.dumps({"status": status, "id": "fixture-id"})

    monkeypatch.setattr(module, "logged", logged)
    with pytest.raises(ValueError, match="not accepted"):
        module.notarize(tmp_path / "Pagemark.app", "fixture-profile", tmp_path)
    assert commands == ["notarization"]


def test_accepted_notarization_staples_validates_and_checks_gatekeeper(tmp_path, monkeypatch):
    import release as module

    commands = []
    monkeypatch.setattr(module, "zip_app", lambda app, output: None)

    def logged(command, directory, name, **kwargs):
        commands.append(name)
        return json.dumps({"status": "Accepted", "id": "fixture-id"})

    monkeypatch.setattr(module, "logged", logged)
    module.notarize(tmp_path / "Pagemark.app", "fixture-profile", tmp_path)
    assert commands == ["notarization", "staple", "staple-validation", "gatekeeper"]
