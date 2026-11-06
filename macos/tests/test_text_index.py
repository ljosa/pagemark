"""Unicode indices must agree with whole-string reference mappings after edits."""
from bisect import bisect_left, bisect_right

import pytest

pytest.importorskip("Foundation")

from pagemark_app.codec import StyledText, utf16_offsets  # noqa: E402
from pagemark_app.native_editor import composed_boundaries  # noqa: E402
from pagemark_app.session import EditorSession  # noqa: E402
from pagemark_app.text_index import TextIndex  # noqa: E402


@pytest.mark.parametrize("text", ["", "\n\n", "a\n", "a😀\né字\n🇳🇴👩‍💻z", "a\nb\n\nc"])
def test_offsets_boundaries_and_native_ranges_match_whole_string_reference(text):
    index = TextIndex(text.split("\n"), composed_boundaries)
    offsets = utf16_offsets(text)
    stops = list(composed_boundaries(text))
    assert index.native_length == offsets[-1]
    for source in range(len(text) + 1):
        assert index.offset(index.position(source)) == source
        assert index.native_offset(source) == offsets[source]
        assert index.previous_boundary(source) == stops[max(0, bisect_left(stops, source) - 1)]
        assert index.next_boundary(source) == stops[min(len(stops) - 1, bisect_right(stops, source))]
        assert index.snap(source, "floor") == stops[max(0, bisect_right(stops, source) - 1)]
        assert index.snap(source, "ceil") == stops[min(len(stops) - 1, bisect_left(stops, source))]
    for native in range(offsets[-1] + 1):
        assert index.source_offset(native) == bisect_right(offsets, native) - 1
        assert index.source_offset(native, round_up=True) == bisect_left(offsets, native)
    assert index.source_offset(-20) == 0
    assert index.source_offset(10**9) == len(text)


def test_navigation_segments_only_current_paragraph_and_reuses_unchanged_indices():
    calls = []

    def boundaries(text):
        calls.append(text)
        return composed_boundaries(text)

    paragraphs = [f"Paragraph {i} é" for i in range(500)]
    text = "\n".join(paragraphs)
    session = EditorSession(StyledText(text, (0,) * len(text)), boundaries=boundaries)
    session.select(len(text), len(text))
    session.move("left")
    session.move("right")
    session.move("left")
    assert calls == [paragraphs[-1]]
    before = session.index
    session.insert("x")
    after = session.index
    assert all(a is b for a, b in zip(before.paragraphs[:-1], after.paragraphs[:-1]))
    assert after.word_count == session.model.count_words()
    session.move("right")
    assert calls == [paragraphs[-1], session.model.paragraphs[-1]]


def test_index_refreshes_after_split_join_undo_and_segmentation_provider_change():
    text = "a😀\né"
    session = EditorSession(StyledText(text, (0,) * len(text)), boundaries=composed_boundaries)
    before = session.snapshot()
    session.select(1, 1)
    for value in ("x\ny", "😀", "\n", ""):
        session.insert(value)
        fresh = TextIndex(session.value.text.split("\n"), composed_boundaries)
        assert session.index.source_starts == fresh.source_starts
        assert session.index.native_starts == fresh.native_starts
        assert session.index.word_count == session.model.count_words()
    session.restore(before)
    assert session.index.length == len(before.value.text)
    assert session.index.native_length == utf16_offsets(before.value.text)[-1]
    old = session.index
    session.boundaries = lambda text: list(range(len(text) + 1))
    assert session.index is not old
    assert all(a is not b for a, b in zip(old.paragraphs, session.index.paragraphs))
