"""One version source for local bundles and tagged macOS releases."""
from pathlib import Path
import re
import tomllib


def read_version(root: Path) -> tuple[str, str]:
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    version = metadata["project"]["version"]
    number = metadata["tool"]["pagemark"]["build-number"]
    if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError("macOS version must have three numeric components")
    if type(number) is not int or number <= 0:
        raise ValueError("macOS build-number must be a positive integer")
    return version, str(number)
