"""Test help screen functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType


def test_help_command_shows_help():
    """Test that Ctrl-? shows the help screen."""
    editor = Editor()

    # Initially help should not be visible
    assert editor.help_visible == False

    # Execute help command
    editor.show_help()

    # Help should now be visible
    assert editor.help_visible == True


def test_help_dismisses_on_any_key():
    """Test that pressing any key dismisses the help screen."""
    editor = Editor()

    # Show help
    editor.show_help()
    assert editor.help_visible == True

    # Press any key (e.g., 'a')
    key_event = KeyEvent(
        key_type=KeyType.REGULAR,
        value='a',
        raw='a',
        is_alt=False,
        is_ctrl=False,
        is_sequence=False,
        code=None
    )

    editor._handle_key_event(key_event)

    # Help should be dismissed
    assert editor.help_visible == False


def test_help_screen_draw():
    """Test that help screen drawing works."""
    editor = Editor()

    # Mock the terminal to capture output
    with patch('builtins.print') as mock_print:
        editor.terminal.term = MagicMock()
        editor.terminal.term.height = 24
        editor.terminal.term.clear = Mock(return_value='[CLEAR]')
        editor.terminal.term.move_y = Mock(side_effect=lambda y: f'[MOVE_Y:{y}]')
        editor.terminal.term.hide_cursor = '[HIDE_CURSOR]'

        # Draw help screen
        editor._draw_help()

        # Check that clear was in the output
        calls = [str(call) for call in mock_print.call_args_list]
        assert any('[CLEAR]' in str(call) for call in calls)
        assert any('Help' in str(call) for call in calls)


def test_f1_triggers_help():
    """Test that F1 keybinding triggers help command."""
    from pagemark.commands import CommandRegistry, HelpCommand

    registry = CommandRegistry()

    # Check that F1 is registered
    command = registry.get_command(KeyType.SPECIAL, 'f1')
    assert command is not None
    assert isinstance(command, HelpCommand)


def test_alt_keys_not_registered_for_help():
    """Test that Alt-H and Alt-? are NOT registered for help."""
    from pagemark.commands import CommandRegistry

    registry = CommandRegistry()

    # Check that Alt-H is NOT registered for help
    h_command = registry.get_command(KeyType.ALT, 'h')
    assert h_command is None

    # Check that Alt-? is NOT registered for help
    question_command = registry.get_command(KeyType.ALT, '?')
    assert question_command is None


def test_help_not_shown_in_error_mode():
    """Test that help doesn't interfere with error mode."""
    editor = Editor()
    editor.error_mode = True

    # Try to handle F1 in error mode
    key_event = KeyEvent(
        key_type=KeyType.SPECIAL,
        value='f1',
        raw='\x1bOP',  # Common F1 sequence
        is_alt=False,
        is_ctrl=False,
        is_sequence=True,
        code=265  # F1 code
    )

    editor._handle_key_event(key_event)

    # Help should not be shown in error mode
    assert editor.help_visible == False
