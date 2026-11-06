"""Enforce portable imports and explicit OS capabilities at the shared boundary."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from pagemark_core.model import CursorPosition, TextModel
from pagemark_core import pdf_generator

ROOT = Path(__file__).resolve().parents[1]


def test_every_core_module_imports_without_either_front_end_or_native_ui():
    result = subprocess.run([sys.executable, "-I", "-c", '''
import importlib, importlib.abc, pkgutil, sys
sys.path.insert(0, sys.argv[1])
class ForbidUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'pagemark', 'pagemark_app', 'pagemark_platform', 'AppKit', 'Foundation',
            'objc', 'blessed', 'curtsies', 'pyperclip',
        }:
            raise AssertionError('Shared core imported ' + fullname)
sys.meta_path.insert(0, ForbidUI())
import pagemark_core
for module in pkgutil.walk_packages(pagemark_core.__path__, 'pagemark_core.'):
    importlib.import_module(module.name)
from types import SimpleNamespace
from pagemark_core.model import TextModel
model = TextModel(SimpleNamespace(render=lambda: None, num_columns=65), ['one two'])
model.move_end_of_line()
assert model.cursor_position.character_index == 7
model.move_beginning_of_line()
assert model.cursor_position.character_index == 0
model.kill_line()
assert model.paragraphs == ['']
''', str(ROOT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_imports_keep_identity_without_eager_terminal_initialization():
    result = subprocess.run([sys.executable, "-I", "-c", '''
import importlib, sys
sys.path.insert(0, sys.argv[1])
import pagemark
for name in ('buffer', 'coordinates', 'layout', 'navigation', 'viewport', 'text_layout',
             'font_config', 'print_formatter', 'booklet', 'rtf_parser'):
    assert importlib.import_module('pagemark.' + name) is importlib.import_module('pagemark_core.' + name)
assert 'pagemark.view' not in sys.modules
assert 'AppKit' not in sys.modules
from pagemark import TerminalTextView
assert TerminalTextView is sys.modules['pagemark.view'].TerminalTextView
''', str(ROOT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_clipboard_capability_cannot_delete_selected_text():
    model = TextModel(SimpleNamespace(render=lambda: None), ['keep'])
    model.selection_start = CursorPosition(0, 0)
    model.selection_end = CursorPosition(0, 4)
    for operation in (model.cut_selection, model.paste):
        with pytest.raises(RuntimeError, match='front end must provide clipboard'):
            operation()
        assert model.paragraphs == ['keep']
        assert model.get_selected_text() == 'keep'


def test_injected_clipboard_roundtrips_styled_selection_without_platform_imports():
    copied = []
    clipboard = SimpleNamespace(copy_text=lambda text, styles: copied.append((text, styles)),
                                paste_text=lambda: copied[-1])
    model = TextModel.from_overstrike_text(SimpleNamespace(render=lambda: None), 'A\bA',
                                          clipboard=clipboard)
    model.selection_start = CursorPosition(0, 0)
    model.selection_end = CursorPosition(0, 1)
    assert model.cut_selection()
    assert model.paragraphs == ['']
    model.paste()
    assert model.to_overstrike_text() == 'A\bA'


def test_pdf_font_files_are_explicit_and_terminal_discovery_is_an_adapter(monkeypatch):
    from pagemark import pdf_generator as terminal_pdf

    paths = []
    monkeypatch.setattr(pdf_generator.pdfmetrics, 'getRegisteredFontNames', lambda: [])
    monkeypatch.setattr(pdf_generator.pdfmetrics, 'registerFont', lambda font: None)
    monkeypatch.setattr(pdf_generator, 'TTFont', lambda name, path: paths.append(path))
    with pytest.raises(pdf_generator.FontLoadError, match='explicit font file'):
        pdf_generator.PDFGenerator('Prestige Elite Std')
    assert paths == []
    pdf_generator.PDFGenerator('Prestige Elite Std', font_paths=('selected.ttf', 'bold.ttf'))
    assert paths == ['selected.ttf', 'bold.ttf']
    monkeypatch.setattr(terminal_pdf, 'prestige_font_paths', lambda: ('system.ttf', None))
    terminal_pdf.PDFGenerator('Prestige Elite Std')
    assert paths == ['selected.ttf', 'bold.ttf', 'system.ttf']
