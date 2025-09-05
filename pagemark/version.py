from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional


class BuildInfo(NamedTuple):
    commit: Optional[str]
    date: Optional[str]
    dirty: bool


def _run_git(args: list[str], cwd: Optional[str] = None) -> Optional[str]:
    try:
        out = subprocess.check_output(["git", *args], cwd=cwd or os.getcwd())
        return out.decode().strip() or None
    except Exception:
        return None


def _git_root_for(path: Path) -> Optional[Path]:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=str(path))
        root = Path(out.decode().strip())
        return root if root.exists() else None
    except Exception:
        return None


def _from_git_repo() -> Optional[BuildInfo]:
    here = Path(__file__).resolve().parent
    root = _git_root_for(here)
    if not root:
        return None

    commit = _run_git(["rev-parse", "HEAD"], cwd=str(root))
    date = _run_git(["show", "-s", "--format=%cI", "HEAD"], cwd=str(root))
    dirty = False
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(root)
        ).decode()
        dirty = bool(status.strip())
    except Exception:
        pass

    return BuildInfo(commit=commit, date=date, dirty=dirty)


def _from_embedded_file() -> Optional[BuildInfo]:
    # Generated at build time by hatch build hook
    try:
        from . import _build_info  # type: ignore

        commit = getattr(_build_info, "COMMIT", None)
        date = getattr(_build_info, "DATE", None)
        if commit or date:
            return BuildInfo(commit=commit, date=date, dirty=False)
    except Exception:
        pass
    return None


def _from_direct_url() -> Optional[BuildInfo]:
    # PEP 610 direct_url.json may contain VCS commit id when installed from VCS
    try:
        dist = importlib.metadata.distribution("pagemark")
        for file in dist.files or []:
            if file.name == "direct_url.json" and file.parent and file.parent.name.endswith(".dist-info"):
                p = Path(dist.locate_file(file))
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                vcs = data.get("vcs_info") or {}
                commit = vcs.get("commit_id")
                # direct_url doesn't include date; leave as None
                if commit:
                    return BuildInfo(commit=commit, date=None, dirty=False)
    except Exception:
        pass
    return None


def get_build_info() -> BuildInfo:
    # Priority: live git repo -> embedded file -> direct_url.json -> unknowns
    for getter in (_from_git_repo, _from_embedded_file, _from_direct_url):
        info = getter()
        if info and (info.commit or info.date):
            return info
    return BuildInfo(commit=None, date=None, dirty=False)


def get_version_string() -> str:
    info = get_build_info()
    dirty_suffix = "-dirty" if info.dirty else ""
    commit_full = info.commit or "unknown"
    # Use short (7-character) git hashes when available
    commit = commit_full[:7] if commit_full != "unknown" else commit_full
    date = info.date or "unknown"
    return f"{commit}{dirty_suffix} {date}"
