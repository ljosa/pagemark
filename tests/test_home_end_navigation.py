"""Tests for Home/End document navigation and keybindings."""

from pagemark.model import TextModel, CursorPosition
from pagemark.view import TerminalTextView
from pagemark.commands import CommandRegistry, DocumentHomeCommand, DocumentEndCommand
from pagemark.keyboard import KeyType


def create_model(paragraphs):
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    return TextModel(v, paragraphs=paragraphs)


def test_home_moves_to_beginning_of_document():
    m = create_model(["first", "second", "third"])
    m.cursor_position = CursorPosition(1, 3)

    m.move_beginning_of_document()

    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0


def test_end_moves_to_end_of_document():
    m = create_model(["first", "second", "third"])
    m.cursor_position = CursorPosition(0, 0)

    m.move_end_of_document()

    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == len("third")


def test_registry_has_home_end_bindings():
    r = CommandRegistry()
    home_cmd = r.get_command(KeyType.SPECIAL, 'home')
    end_cmd = r.get_command(KeyType.SPECIAL, 'end')

    assert isinstance(home_cmd, DocumentHomeCommand)
    assert isinstance(end_cmd, DocumentEndCommand)

