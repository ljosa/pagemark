"""Regression tests for model-level bugs (BUG-10, BUG-11, BUG-12, BUG-20)."""

from unittest.mock import Mock, patch

from pagemark.model import TextModel, CursorPosition


def create_test_model(paragraphs):
    view = Mock()
    view.render = Mock()
    view.num_columns = 20
    view.start_paragraph_index = 0
    view.end_paragraph_index = len(paragraphs)
    return TextModel(view, paragraphs=paragraphs)


# --- BUG-10: center_line must move styles with their characters ---

def test_center_line_keeps_styles_on_characters():
    model = create_test_model(["BOLD"])
    model.styles = [[1, 1, 1, 1]]
    model.cursor_position = CursorPosition(0, 0)

    assert model.center_line() is True

    para = model.paragraphs[0]
    styles = model.styles[0]
    assert para == "        BOLD"
    assert len(styles) == len(para)
    assert styles == [0] * 8 + [1, 1, 1, 1]


def test_center_line_with_existing_leading_spaces_keeps_styles():
    model = create_test_model(["  ab  "])
    model.styles = [[0, 0, 1, 2, 0, 0]]
    model.cursor_position = CursorPosition(0, 0)

    assert model.center_line() is True

    para = model.paragraphs[0]
    styles = model.styles[0]
    assert para.strip() == "ab"
    assert len(styles) == len(para)
    lead = len(para) - len(para.lstrip())
    assert styles[lead:lead + 2] == [1, 2]
    assert all(s == 0 for s in styles[:lead])


def test_center_line_empty_paragraph_clears_styles():
    model = create_test_model(["   "])
    model.styles = [[1, 1, 1]]
    assert model.center_line() is True
    assert model.paragraphs[0] == ""
    assert model.styles[0] == []


# --- BUG-11: paste must sanitize clipboard content ---

def paste_with_clipboard(model, text, styles=None):
    with patch("pagemark.model.ClipboardManager.paste_text",
               return_value=(text, styles)):
        model.paste()


def test_paste_normalizes_crlf():
    model = create_test_model([""])
    paste_with_clipboard(model, "line1\r\nline2\rline3")
    assert model.paragraphs == ["line1", "line2", "line3"]


def test_paste_replaces_tabs_and_drops_control_chars():
    model = create_test_model([""])
    paste_with_clipboard(model, "a\tb\x07c\x00d\x93e")
    assert model.paragraphs == ["a bcde"]


def test_paste_keeps_nbsp():
    model = create_test_model([""])
    paste_with_clipboard(model, "\xa0 bullet")
    assert model.paragraphs == ["\xa0 bullet"]


def test_paste_converts_unicode_spaces_to_plain_space():
    # em space, narrow NBSP, ideographic space: must not vanish and glue
    # the surrounding words together
    model = create_test_model([""])
    paste_with_clipboard(model, "10 000 wide　ok")
    assert model.paragraphs == ["10 000 wide ok"]


def test_center_line_cursor_clamped_when_trailing_spaces_removed():
    model = create_test_model(["hi        "])
    model.cursor_position = CursorPosition(0, 10)  # in the trailing spaces

    assert model.center_line() is True
    para = model.paragraphs[0]
    assert model.cursor_position.character_index <= len(para)


def test_paste_styled_keeps_styles_aligned_after_sanitizing():
    model = create_test_model([""])
    # The \x01 must be dropped along with its style entry.
    paste_with_clipboard(model, "ab\x01c", styles=[[1, 1, 0, 2]])
    assert model.paragraphs == ["abc"]
    assert model.styles == [[1, 1, 2]]


def test_paste_styled_multiparagraph_sanitized():
    model = create_test_model([""])
    paste_with_clipboard(model, "a\tb\nc", styles=[[1, 1, 1], [2]])
    assert model.paragraphs == ["a b", "c"]
    assert model.styles == [[1, 1, 1], [2]]


# --- BUG-12: insert_text must honor an explicit position ---

def test_insert_text_at_explicit_position():
    model = create_test_model(["hello world", "second"])
    model.cursor_position = CursorPosition(1, 3)  # cursor elsewhere

    model.insert_text("XX", position=CursorPosition(0, 5))

    assert model.paragraphs[0] == "helloXX world"
    assert model.paragraphs[1] == "second"
    # Cursor ends up after the inserted text.
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 7


# --- BUG-20: transpose_words cursor lands after the transposed region ---

def test_transpose_words_cursor_at_end_of_region():
    model = create_test_model(["cat elephant"])
    model.cursor_position = CursorPosition(0, 3)

    model.transpose_words()

    assert model.paragraphs[0] == "elephant cat"
    assert model.cursor_position.character_index == len("elephant cat")


def test_transpose_words_repeated_walks_forward():
    model = create_test_model(["one two three"])
    model.cursor_position = CursorPosition(0, 3)

    model.transpose_words()
    assert model.paragraphs[0] == "two one three"
    model.transpose_words()
    assert model.paragraphs[0] == "two three one"
