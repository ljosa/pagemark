from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.check_output(["git", *args], cwd=str(cwd))
        return out.decode().strip() or None
    except Exception:
        return None


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pkg_dir = project_root / "pagemark"
    target_path = pkg_dir / "_build_info.py"

    commit = _run_git(["rev-parse", "HEAD"], cwd=project_root)
    date = _run_git(["show", "-s", "--format=%cI", "HEAD"], cwd=project_root)

    content = (
        "# Auto-generated at build time.\n"
        f"COMMIT = {commit!r}\n"
        f"DATE = {date!r}\n"
    )
    target_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()

