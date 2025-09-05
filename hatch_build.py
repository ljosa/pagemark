"""Custom build hook for Hatchling to generate build info."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Custom build hook to generate build info file."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Run the build info generation script."""
        self._generate_build_info()
        
        # Add the generated file to artifacts
        build_data.setdefault("artifacts", []).append("pagemark/_build_info.py")

    def _generate_build_info(self) -> None:
        """Generate the _build_info.py file with git commit info."""
        project_root = Path(self.root)
        pkg_dir = project_root / "pagemark"
        target_path = pkg_dir / "_build_info.py"

        commit = self._run_git(["rev-parse", "HEAD"], cwd=project_root)
        date = self._run_git(["show", "-s", "--format=%cI", "HEAD"], cwd=project_root)

        content = (
            "# Auto-generated at build time.\n"
            f"COMMIT = {commit!r}\n"
            f"DATE = {date!r}\n"
        )
        target_path.write_text(content, encoding="utf-8")

    def _run_git(self, args: list[str], cwd: Path) -> str | None:
        """Run a git command and return its output."""
        try:
            out = subprocess.check_output(["git", *args], cwd=str(cwd))
            return out.decode().strip() or None
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            # Build should not fail just because git is unavailable
            return None
