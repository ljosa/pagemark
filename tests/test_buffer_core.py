"""Check styled edits against a flat string/style oracle, without an editor."""

from itertools import product
import random

import pytest

from pagemark.buffer import StyledDocument, StyledParagraph
from pagemark.coordinates import DocumentPosition


def position(text, offset):
    before = text[:offset]
    return DocumentPosition(before.count("\n"), len(before.rsplit("\n", 1)[-1]))


def styled(text):
    parts = text.split("\n")
    masks = []
    offset = 0
    for part in parts:
        masks.append([(offset + index) % 4 for index in range(len(part))])
        offset += len(part) + 1
    return StyledDocument.from_parts(parts, masks)


def flatten(document):
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    masks = [
        flag
        for index, paragraph in enumerate(document.paragraphs)
        for flag in ((None,) if index else ()) + paragraph.styles
    ]
    return text, masks


def assert_replacement(original, start, end, inserted):
    text, masks = flatten(original)
    insertion, insert_masks = flatten(inserted)
    left, right = sorted((start, end))
    changed, cursor = original.replace(
        position(text, start), position(text, end), inserted
    )
    expected = text[:left] + insertion + text[right:]
    assert flatten(changed) == (expected, masks[:left] + insert_masks + masks[right:])
    assert cursor == position(expected, left + len(insertion))
    removed = original.slice(position(text, start), position(text, end))
    restored, _ = changed.replace(position(expected, left), cursor, removed)
    assert restored == original
    assert flatten(original) == (text, masks)
    return changed


def test_exhaustive_small_document_replacements_and_inverses():
    insertions = tuple(styled(text) for text in ("", "X", "\n", "X\nY", "\n\n", "界—"))
    for length in range(5):
        for characters in product(("a", "界", "\n"), repeat=length):
            text = "".join(characters)
            original = styled(text)
            for start, end in product(range(len(text) + 1), repeat=2):
                for inserted in insertions:
                    assert_replacement(original, start, end, inserted)


def test_generated_edit_sequences_preserve_text_styles_and_valid_cursor():
    rng = random.Random(314159)
    document = styled("a\nb")
    for _ in range(500):
        text, _ = flatten(document)
        start, end = (rng.randrange(len(text) + 1) for _ in range(2))
        inserted = styled(
            "".join(rng.choices(("a", "界", "—", "\n", "e\u0301"), k=rng.randrange(6)))
        )
        document = assert_replacement(document, start, end, inserted)


def test_style_toggle_changes_only_selected_masks():
    original = styled("abc\n\ndef")
    toggled = original.toggle_style(DocumentPosition(2, 1), DocumentPosition(0, 1), 1)
    assert flatten(toggled) == ("abc\n\ndef", [0, 1, 3, None, None, 1, 2, 3])
    cleared = toggled.toggle_style(DocumentPosition(0, 1), DocumentPosition(2, 1), 1)
    assert flatten(cleared) == ("abc\n\ndef", [0, 0, 2, None, None, 0, 2, 3])


def test_invalid_input_is_rejected_without_mutation():
    document = styled("abc")
    for point in (
        DocumentPosition(-1, 0),
        DocumentPosition(0, -1),
        DocumentPosition(1, 0),
        DocumentPosition(0, 4),
    ):
        with pytest.raises(ValueError):
            document.replace(DocumentPosition(), point, StyledDocument.plain("x"))
        assert document == styled("abc")
    with pytest.raises(ValueError):
        StyledDocument(())
    with pytest.raises(ValueError):
        StyledParagraph("a", ())
    with pytest.raises(ValueError):
        StyledParagraph("\n", (0,))
    with pytest.raises(ValueError):
        StyledDocument.from_parts([""], [])
