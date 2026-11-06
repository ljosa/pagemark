"""Document-owned layout reuse must preserve the canonical layout contract."""
import random

import pytest

from pagemark import layout as module
from pagemark.layout import DocumentLayout
from pagemark.model import TextModel
from pagemark.view import TerminalTextView


def paragraphs(count=400):
    return [f"Paragraph {index}. " + "one two three " * 20 for index in range(count)]


def test_long_document_edit_only_lays_out_changed_paragraph_even_after_cache_eviction(monkeypatch):
    text = paragraphs()
    before = DocumentLayout.build(text, 65)
    module.layout_paragraph.cache_clear()
    original = module.layout_paragraph
    calls = []

    def record(text, width):
        calls.append((text, width))
        return original(text, width)

    monkeypatch.setattr(module, "layout_paragraph", record)
    changed = list(text)
    changed[200] += " added text"
    after = DocumentLayout.build(changed, 65, previous=before)
    assert calls == [(changed[200], 65)]
    assert all(after.paragraphs[i] is before.paragraphs[i] for i in range(400) if i != 200)
    assert before.paragraphs[200].paragraph == text[200]
    assert after == DocumentLayout.build(changed, 65)


@pytest.mark.parametrize("width", [65, 72])
def test_reuse_matches_fresh_layout_across_edits_splits_joins_reordering_and_width_changes(width):
    rng = random.Random(410)
    text = ["- " + "é é — 字 " * 30, "", "long" * 50, "same", "same"]
    previous = DocumentLayout.build(text, width)
    for _ in range(80):
        index = rng.randrange(len(text))
        operation = rng.randrange(5)
        if operation == 0:
            text[index] += " abc—é"
        elif operation == 1:
            cut = len(text[index]) // 2
            text[index:index + 1] = [text[index][:cut], text[index][cut:]]
        elif operation == 2 and len(text) > 1:
            text[index:index + 2] = ["".join(text[index:index + 2])]
        elif operation == 3:
            text.reverse()
        else:
            width = 72 if width == 65 else 65
        incremental = DocumentLayout.build(text, width, previous=previous)
        assert incremental == DocumentLayout.build(text, width)
        previous = incremental
    assert DocumentLayout.build([], width, previous=previous) == DocumentLayout.build([], width)


def test_terminal_view_retains_unchanged_layouts_after_typing():
    view = TerminalTextView()
    view.num_rows, view.num_columns = 24, 65
    model = TextModel(view, paragraphs())
    view.render()
    before = view._layout
    module.layout_paragraph.cache_clear()
    model.replace_selection("x")
    after = view._layout
    assert after.paragraphs[0].paragraph == "x" + before.paragraphs[0].paragraph
    assert all(a is b for a, b in zip(after.paragraphs[1:], before.paragraphs[1:]))
    assert after == DocumentLayout.build(model.paragraphs, 65)
