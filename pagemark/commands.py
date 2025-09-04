"""Command pattern implementation for editor actions."""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, TYPE_CHECKING
from .keyboard import KeyType

if TYPE_CHECKING:
    from .editor import Editor
    from .keyboard import KeyEvent


class EditorCommand(ABC):
    """Base class for editor commands."""
    
    @abstractmethod
    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        """Execute the command.
        
        Args:
            editor: Editor instance
            key_event: The key event that triggered this command
            
        Returns:
            True if the command modified the document
        """
        pass


class MovementCommand(EditorCommand):
    """Base class for cursor movement commands."""
    
    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        """Movement commands don't modify the document."""
        # Clear selection on non-shift movement
        editor.model.clear_selection()
        self._move(editor, key_event)
        editor.view.update_desired_x()
        return False
    
    @abstractmethod
    def _move(self, editor: 'Editor', key_event: 'KeyEvent'):
        """Perform the movement."""
        pass


class LeftCharCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.left_char()


class RightCharCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.right_char()


class UpLineCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.view.move_cursor_up()


class DownLineCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.view.move_cursor_down()


class LeftWordCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.left_word()


class RightWordCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.right_word()


class BeginningOfLineCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.move_beginning_of_line()


class EndOfLineCommand(MovementCommand):
    def _move(self, editor, key_event):
        editor.model.move_end_of_line()


class EditCommand(EditorCommand):
    """Base class for editing commands."""
    
    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        """Editing commands modify the document."""
        self._edit(editor, key_event)
        editor.view.update_desired_x()
        return True
    
    @abstractmethod
    def _edit(self, editor: 'Editor', key_event: 'KeyEvent'):
        """Perform the edit."""
        pass


class BackspaceCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor._handle_backspace()


class DeleteCharCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.delete_char()


class KillLineCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.kill_line()


class KillWordCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.backward_kill_word()


class ForwardKillWordCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.kill_word()


class InsertNewlineCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.insert_text('\n')


class InsertTextCommand(EditCommand):
    def _edit(self, editor, key_event):
        char = key_event.value
        # Filter out control characters
        if ord(char[0]) >= 32 or char == '\t':
            # Delete any selection first
            if editor.model.selection_start is not None:
                editor.model.delete_selection()
            editor.model.insert_text(char)


class SystemCommand(EditorCommand):
    """Base class for system commands like save, quit, print."""
    
    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        """System commands don't modify document content directly."""
        self._execute_system(editor, key_event)
        return False
    
    @abstractmethod
    def _execute_system(self, editor: 'Editor', key_event: 'KeyEvent'):
        """Perform the system action."""
        pass


class QuitCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        if editor.modified:
            editor.prompt_mode = 'quit_confirm'
        else:
            editor.running = False


class SaveCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        editor._handle_save()


class PrintCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        editor._handle_print()


class HelpCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        editor.show_help()


class WordCountCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        word_count = editor.model.count_words()
        editor.status_message = f"{word_count} words"


class CenterLineCommand(EditCommand):
    def _edit(self, editor, key_event):
        success = editor.model.center_line()
        if not success:
            editor.status_message = "Cannot center multi-line paragraph"


class TransposeCharsCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.transpose_chars()


class TransposeWordsCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.transpose_words()


class CapitalizeWordCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.capitalize_word()


class UpcaseWordCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.upcase_word()


class DowncaseWordCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.downcase_word()


class SelectionMovementCommand(MovementCommand):
    """Base class for shift+arrow selection movements.

    Important: Do NOT clear selection on shift-modified movement. Preserve
    the original anchor and extend/shrink the selection as the cursor moves.
    """

    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        # Start selection if not already started
        if editor.model.selection_start is None:
            editor.model.start_selection()

        # Perform the movement without clearing selection
        self._selection_move(editor, key_event)

        # Update selection end to current cursor and draw
        editor.model.update_selection_end()
        editor.view.update_desired_x()
        editor.view.render()
        return False

    def _selection_move(self, editor, key_event):
        """Override this to implement specific movement."""
        pass

    # Implement abstract method to satisfy MovementCommand, though
    # SelectionMovementCommand overrides execute and doesn't use this path.
    def _move(self, editor, key_event):
        self._selection_move(editor, key_event)


class ShiftLeftCommand(SelectionMovementCommand):
    def _selection_move(self, editor, key_event):
        editor.model.left_char()


class ShiftRightCommand(SelectionMovementCommand):
    def _selection_move(self, editor, key_event):
        editor.model.right_char()


class ShiftUpCommand(SelectionMovementCommand):
    def _selection_move(self, editor, key_event):
        editor.view.move_cursor_up()


class ShiftDownCommand(SelectionMovementCommand):
    def _selection_move(self, editor, key_event):
        editor.view.move_cursor_down()


class CutCommand(EditCommand):
    def _edit(self, editor, key_event):
        if editor.model.cut_selection():
            editor.status_message = "Selection cut"
        else:
            editor.status_message = "No selection"


class CopyCommand(SystemCommand):
    def _execute_system(self, editor, key_event):
        if editor.model.copy_selection():
            editor.status_message = "Selection copied"
        else:
            editor.status_message = "No selection"


class PasteCommand(EditCommand):
    def _edit(self, editor, key_event):
        editor.model.paste()


class CommandRegistry:
    """Registry for mapping key combinations to commands."""
    
    def __init__(self):
        self._commands: Dict[Tuple[KeyType, str], EditorCommand] = {}
        self._setup_default_commands()
    
    def _setup_default_commands(self):
        """Set up the default command mappings."""
        # Movement commands
        self.register((KeyType.SPECIAL, 'left'), LeftCharCommand())
        self.register((KeyType.SPECIAL, 'right'), RightCharCommand())
        self.register((KeyType.SPECIAL, 'up'), UpLineCommand())
        self.register((KeyType.SPECIAL, 'down'), DownLineCommand())
        
        # Selection movement commands (Shift+arrow)
        self.register((KeyType.SHIFT_SPECIAL, 'left'), ShiftLeftCommand())
        self.register((KeyType.SHIFT_SPECIAL, 'right'), ShiftRightCommand())
        self.register((KeyType.SHIFT_SPECIAL, 'up'), ShiftUpCommand())
        self.register((KeyType.SHIFT_SPECIAL, 'down'), ShiftDownCommand())
        
        # Alt+arrow for word movement
        self.register((KeyType.ALT, 'left'), LeftWordCommand())
        self.register((KeyType.ALT, 'right'), RightWordCommand())
        self.register((KeyType.ALT, 'b'), LeftWordCommand())
        self.register((KeyType.ALT, 'f'), RightWordCommand())
        
        # Line movement
        self.register((KeyType.CTRL, 'a'), BeginningOfLineCommand())
        self.register((KeyType.CTRL, 'e'), EndOfLineCommand())
        
        # Editing commands
        self.register((KeyType.SPECIAL, 'backspace'), BackspaceCommand())
        self.register((KeyType.CTRL, 'd'), DeleteCharCommand())
        self.register((KeyType.CTRL, 'k'), KillLineCommand())
        self.register((KeyType.ALT, 'backspace'), KillWordCommand())
        self.register((KeyType.ALT, 'd'), ForwardKillWordCommand())
        self.register((KeyType.SPECIAL, 'enter'), InsertNewlineCommand())
        self.register((KeyType.CTRL, '^'), CenterLineCommand())
        self.register((KeyType.CTRL, 't'), TransposeCharsCommand())
        self.register((KeyType.ALT, 't'), TransposeWordsCommand())
        self.register((KeyType.ALT, 'c'), CapitalizeWordCommand())
        self.register((KeyType.ALT, 'u'), UpcaseWordCommand())
        self.register((KeyType.ALT, 'l'), DowncaseWordCommand())
        self.register((KeyType.CTRL, 'x'), CutCommand())
        self.register((KeyType.CTRL, 'c'), CopyCommand())
        self.register((KeyType.CTRL, 'v'), PasteCommand())
        
        # System commands
        self.register((KeyType.CTRL, 'q'), QuitCommand())
        self.register((KeyType.CTRL, 's'), SaveCommand())
        self.register((KeyType.CTRL, 'p'), PrintCommand())
        self.register((KeyType.CTRL, 'w'), WordCountCommand())
        
        # Help command - F1 only
        self.register((KeyType.SPECIAL, 'f1'), HelpCommand())
    
    def register(self, key: Tuple[KeyType, str], command: EditorCommand):
        """Register a command for a key combination."""
        self._commands[key] = command
    
    def get_command(self, key_type: KeyType, value: str) -> Optional[EditorCommand]:
        """Get the command for a key combination."""
        # For Alt-modified keys, check both with and without Alt flag
        if key_type == KeyType.ALT:
            return self._commands.get((KeyType.ALT, value))
        return self._commands.get((key_type, value))
    
    def execute(self, editor: 'Editor', key_event: 'KeyEvent') -> bool:
        """Execute the command for the given key event.
        
        Returns:
            True if the document was modified
        """
        # Check for Alt-modified keys
        if key_event.is_alt:
            command = self.get_command(KeyType.ALT, key_event.value)
        else:
            command = self.get_command(key_event.key_type, key_event.value)
        
        if command:
            return command.execute(editor, key_event)
        
        # Handle regular text input
        if key_event.key_type == KeyType.REGULAR:
            return InsertTextCommand().execute(editor, key_event)
        
        return False
