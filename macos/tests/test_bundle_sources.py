"""The bundle contains the same shared packages used directly by source tests."""
import hashlib
from pathlib import Path

import pytest

from build_app import SHARED_PACKAGES, copy_shared_packages


def test_shared_packages_are_copied_completely_with_source_hashes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    hashes = copy_shared_packages(root, tmp_path)
    expected = {p.relative_to(root).as_posix() for name in SHARED_PACKAGES
                for p in (root / name).rglob('*.py') if '__pycache__' not in p.parts}
    assert set(hashes) == expected
    for relative, digest in hashes.items():
        assert (tmp_path / relative).read_bytes() == (root / relative).read_bytes()
        assert digest == hashlib.sha256((root / relative).read_bytes()).hexdigest()
    assert not (tmp_path / 'pagemark').exists()


def test_bundling_rejects_a_module_symlink_outside_its_package(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    for name in SHARED_PACKAGES:
        (source / name).mkdir()
        (source / name / '__init__.py').write_text('')
    external = tmp_path / 'external.py'
    external.write_text('')
    (source / SHARED_PACKAGES[0] / 'escape.py').symlink_to(external)
    with pytest.raises(RuntimeError, match='escapes its package'):
        copy_shared_packages(source, tmp_path / 'bundle')
