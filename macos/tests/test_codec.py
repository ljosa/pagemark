from pathlib import Path
import random
import types

import pytest

from pagemark_app.codec import BOLD, UNDERLINE, StyledText, decode, encode, utf16_offsets


@pytest.mark.parametrize("raw", [b"", b"one\r\ntwo\r\n", b"A\bA _\bB _\bC\bC\n",
                                  b"_\b_", "naïve 😀 é\n".encode()])
def test_unchanged_file_preserves_exact_bytes(raw):
    assert encode(decode(raw), original=raw) == raw


def test_supported_styling_roundtrips_with_unicode_and_line_breaks():
    generator = random.Random(127)
    for _ in range(200):
        text = "".join(generator.choice("abé😀 é\n") for _ in range(40))
        styles = tuple(0 if char == "\n" else generator.randrange(4) for char in text)
        value = StyledText(text, styles)
        assert decode(encode(value)) == value


def test_ambiguous_bold_underscore_refuses_to_silently_change_style():
    with pytest.raises(ValueError, match="cannot round-trip"):
        encode(StyledText("_", (BOLD,)))
    assert decode(b"_\b_") == StyledText("_", (UNDERLINE,))


def test_save_edited_crlf_document_preserves_line_endings():
    assert encode(StyledText("a\nb\n", (0, 0, 0, 0)), b"a\r\n") == b"a\r\nb\r\n"


def test_paragraph_styles_exclude_separators():
    assert StyledText("a\n\nb", (BOLD, 0, 0, UNDERLINE)).parts() == (
        ["a", "", "b"], [[BOLD], [], [UNDERLINE]])


def test_utf16_offsets_cover_non_bmp_and_combining_characters():
    assert utf16_offsets("a😀é") == [0, 1, 3, 4, 5]


def test_decoder_matches_terminal_implementation():
    # Load only the legacy static codec, without importing/starting the terminal.
    import ast
    source = Path(__file__).resolve().parents[2] / "pagemark/model.py"
    if not source.exists():
        pytest.fail("The repository's Pagemark model is missing")
    tree = ast.parse(source.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "TextModel")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_parse_overstrike_paragraph")
    method.decorator_list = []
    namespace = {"StyleFlags": types.SimpleNamespace(UNDERLINE=UNDERLINE, BOLD=BOLD),
                 "StyleMask": list[int], "List": list}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    parse = namespace[method.name]
    rng = random.Random(41)
    for _ in range(500):
        raw = "".join(rng.choice("abc_\b😀é") for _ in range(rng.randrange(30)))
        text, styles = parse(raw)
        assert decode(raw.encode()) == StyledText(text, tuple(styles))

