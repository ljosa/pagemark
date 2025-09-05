"""Tests for paragraph navigation via M-up/M-down."""

from pagemark.model import TextModel, CursorPosition
from pagemark.view import TerminalTextView
from pagemark.commands import CommandRegistry, BackwardParagraphCommand, ForwardParagraphCommand
from pagemark.keyboard import KeyType


def create_model_with_paragraphs(paragraphs):
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    return TextModel(v, paragraphs=paragraphs)


def test_backward_paragraph_moves_to_start_of_current_when_inside():
    m = create_model_with_paragraphs(["first para", "second para", "third"])
    # Place cursor in the middle of second paragraph
    m.cursor_position = CursorPosition(1, 3)

    m.backward_paragraph()

    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0


def test_backward_paragraph_from_start_moves_to_previous_non_empty():
    m = create_model_with_paragraphs(["first para", "second para", "third"])
    m.cursor_position = CursorPosition(1, 0)

    m.backward_paragraph()

    # At beginning of non-empty; should move to previous non-empty
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0


def test_backward_paragraph_at_document_start_no_change():
    m = create_model_with_paragraphs(["first para", "second para"])
    m.cursor_position = CursorPosition(0, 0)

    m.backward_paragraph()

    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0


def test_forward_paragraph_moves_to_next_start():
    m = create_model_with_paragraphs(["first para", "second para", "third"])
    m.cursor_position = CursorPosition(1, 5)

    m.forward_paragraph()

    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_forward_paragraph_at_last_no_change():
    m = create_model_with_paragraphs(["first para", "second para"])
    m.cursor_position = CursorPosition(1, 2)

    m.forward_paragraph()

    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 2  # unchanged


def test_command_registry_registers_alt_up_down_for_paragraphs():
    registry = CommandRegistry()

    up_cmd = registry.get_command(KeyType.ALT, 'up')
    down_cmd = registry.get_command(KeyType.ALT, 'down')

    assert isinstance(up_cmd, BackwardParagraphCommand)
    assert isinstance(down_cmd, ForwardParagraphCommand)


def test_backward_paragraph_skips_empty_paragraphs():
    m = create_model_with_paragraphs(["first", "", "second", "", "third"])
    # From inside "second" (index 2), M-up should go to its own beginning
    m.cursor_position = CursorPosition(2, 3)
    m.backward_paragraph()
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_backward_paragraph_at_beginning_of_first_non_empty_no_move():
    m = create_model_with_paragraphs(["", "alpha", "", "beta"])  # first non-empty at index 1
    m.cursor_position = CursorPosition(1, 0)
    m.backward_paragraph()
    # No previous non-empty, stay put
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0


def test_backward_paragraph_on_empty_paragraph_moves_to_previous_non_empty():
    m = create_model_with_paragraphs(["alpha", "", "", "beta"])
    # Place cursor on empty paragraph at index 2
    m.cursor_position = CursorPosition(2, 0)
    m.backward_paragraph()
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0


def test_forward_paragraph_skips_empty_paragraphs():
    m = create_model_with_paragraphs(["first", "", "second", "", "third"])
    # From anywhere in first, M-down should go to second (index 2)
    m.cursor_position = CursorPosition(0, 3)
    m.forward_paragraph()
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_forward_paragraph_from_empty_requires_two_non_empty_ahead():
    m = create_model_with_paragraphs(["one", "", "", "two"])
    m.cursor_position = CursorPosition(1, 0)  # empty paragraph
    m.forward_paragraph()
    # Only one non-empty paragraph ahead; no move
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0

def test_forward_paragraph_moves_to_next_non_empty_after_current():
    # From non-empty current, move to the next non-empty after it
    m = create_model_with_paragraphs(["one", "", "two", "", "three"])
    m.cursor_position = CursorPosition(0, 2)
    m.forward_paragraph()
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0

def test_forward_paragraph_from_empty_skips_to_second_non_empty():
    # From empty between two non-empty, jump to the second non-empty
    m = create_model_with_paragraphs(["one", "", "two", "", "three"])
    m.cursor_position = CursorPosition(1, 0)
    m.forward_paragraph()
    assert m.cursor_position.paragraph_index == 4
    assert m.cursor_position.character_index == 0
