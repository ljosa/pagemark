"""Integration tests for the printing feature."""

from unittest.mock import Mock, MagicMock, patch
import blessed

from pagemark.editor import Editor
from pagemark.print_dialog import PrintAction, PrintOptions
from pagemark.terminal import TerminalInterface


def create_mock_editor():
    """Create a mock editor for testing."""
    editor = Editor()
    
    # Mock the terminal
    mock_term = Mock(spec=TerminalInterface)
    mock_blessed_term = MagicMock()
    mock_blessed_term.width = 80
    mock_blessed_term.height = 50
    mock_blessed_term.hide_cursor = ""
    mock_blessed_term.normal_cursor = ""
    mock_blessed_term.home = ""
    mock_blessed_term.clear = ""
    mock_blessed_term.move = Mock(return_value="")
    mock_blessed_term.KEY_ENTER = 343
    mock_blessed_term.KEY_BACKSPACE = 263
    mock_term.term = mock_blessed_term
    mock_term.clear_screen = Mock()
    mock_term.get_key = Mock()
    mock_term.height = 40
    mock_term.width = 80
    
    editor.terminal = mock_term
    editor.view.num_columns = 65
    editor.view.num_rows = 40
    
    # Load some test content
    editor.model.paragraphs = ["Test paragraph one.", "Test paragraph two."]
    
    return editor


def test_ctrl_p_handler():
    """Test that Ctrl-P triggers the print handler."""
    editor = create_mock_editor()
    
    # Mock the print dialog
    with patch('pagemark.editor.PrintDialog') as mock_dialog_class:
        mock_dialog = Mock()
        mock_dialog.show.return_value = PrintOptions(action=PrintAction.CANCEL)
        mock_dialog.pages = []
        mock_dialog_class.return_value = mock_dialog
        
        # Simulate Ctrl-P keypress
        key = Mock()
        key.is_sequence = False
        key.__str__ = lambda self: '\x10'  # Ctrl-P
        
        editor._handle_key(key)
        
        # Verify dialog was created and shown
        mock_dialog_class.assert_called_once_with(editor.model, editor.terminal)
        mock_dialog.show.assert_called_once()


def test_print_to_printer_flow():
    """Test the flow of printing to a printer."""
    editor = create_mock_editor()
    
    # Mock the print components
    with patch('pagemark.editor.PrintDialog') as mock_dialog_class:
        with patch('pagemark.editor.PrintOutput') as mock_output_class:
            mock_dialog = Mock()
            mock_dialog.show.return_value = PrintOptions(
                action=PrintAction.PRINT,
                printer_name="TestPrinter",
                double_sided=True
            )
            mock_dialog.pages = [["Page 1"], ["Page 2"]]
            mock_dialog_class.return_value = mock_dialog
            
            mock_output = Mock()
            mock_output.print_to_printer.return_value = (True, "")
            mock_output_class.return_value = mock_output
            
            # Simulate Ctrl-P
            key = Mock()
            key.is_sequence = False
            key.__str__ = lambda self: '\x10'  # Ctrl-P
            
            editor._handle_key(key)
            
            # Verify print was called
            mock_output.print_to_printer.assert_called_once_with(
                [["Page 1"], ["Page 2"]],
                "TestPrinter",
                True
            )
            
            # Verify status message
            assert "Successfully printed" in editor.status_message


def test_save_to_ps_flow():
    """Test the flow of saving to PS file."""
    editor = create_mock_editor()
    
    # Mock the print components
    with patch('pagemark.editor.PrintDialog') as mock_dialog_class:
        mock_dialog = Mock()
        mock_dialog.show.return_value = PrintOptions(
            action=PrintAction.SAVE_PS,
            ps_filename="output.ps"
        )
        mock_dialog.pages = [["Page 1"], ["Page 2"]]
        mock_dialog_class.return_value = mock_dialog
        
        # Simulate Ctrl-P
        key = Mock()
        key.is_sequence = False
        key.__str__ = lambda self: '\x10'  # Ctrl-P
        
        editor._handle_key(key)
        
        # Should enter PS filename prompt mode
        assert editor.prompt_mode == 'ps_filename'
        assert editor.prompt_input == "output.ps"
        assert hasattr(editor, '_pending_print_pages')


def test_ps_filename_prompt_save():
    """Test entering a PS filename and saving."""
    editor = create_mock_editor()
    editor.prompt_mode = 'ps_filename'
    editor.prompt_input = "test.ps"
    editor._pending_print_pages = [["Page 1"]]
    
    with patch('pagemark.editor.PrintOutput') as mock_output_class:
        mock_output = Mock()
        mock_output.validate_output_path.return_value = (True, "")
        mock_output.save_to_file.return_value = (True, "")
        mock_output_class.return_value = mock_output
        
        # Simulate Enter key in prompt
        key = Mock()
        key.is_sequence = True
        key.code = 343  # Enter key code
        
        editor._handle_ps_filename_prompt(key)
        
        # Verify save was called
        mock_output.save_to_file.assert_called_once_with(
            [["Page 1"]],
            "test.ps"
        )
        
        # Verify prompt cleared
        assert editor.prompt_mode is None
        assert editor.prompt_input == ""
        assert editor._pending_print_pages is None


def test_ps_filename_prompt_cancel():
    """Test cancelling the PS filename prompt."""
    editor = create_mock_editor()
    editor.prompt_mode = 'ps_filename'
    editor.prompt_input = "test.ps"
    editor._pending_print_pages = [["Page 1"]]
    
    # Simulate ESC key
    key = Mock()
    key.__eq__ = lambda self, other: other == '\x1b'
    key.is_sequence = False
    key.code = None
    
    editor._handle_ps_filename_prompt(key)
    
    # Verify prompt cancelled
    assert editor.prompt_mode is None
    assert editor.prompt_input == ""
    assert editor._pending_print_pages is None
    assert "cancelled" in editor.status_message


def test_print_cancel():
    """Test cancelling the print dialog."""
    editor = create_mock_editor()
    
    with patch('pagemark.editor.PrintDialog') as mock_dialog_class:
        mock_dialog = Mock()
        mock_dialog.show.return_value = PrintOptions(action=PrintAction.CANCEL)
        mock_dialog.pages = []
        mock_dialog_class.return_value = mock_dialog
        
        # Simulate Ctrl-P
        key = Mock()
        key.is_sequence = False
        key.__str__ = lambda self: '\x10'  # Ctrl-P
        
        editor._handle_key(key)
        
        # Verify cancellation message
        assert "cancelled" in editor.status_message


def test_print_error_handling():
    """Test error handling during printing."""
    editor = create_mock_editor()
    
    with patch('pagemark.editor.PrintDialog') as mock_dialog_class:
        with patch('pagemark.editor.PrintOutput') as mock_output_class:
            mock_dialog = Mock()
            mock_dialog.show.return_value = PrintOptions(
                action=PrintAction.PRINT,
                printer_name="BadPrinter",
                double_sided=False
            )
            mock_dialog.pages = [["Page 1"]]
            mock_dialog_class.return_value = mock_dialog
            
            mock_output = Mock()
            mock_output.print_to_printer.return_value = (False, "Printer not found")
            mock_output_class.return_value = mock_output
            
            # Simulate Ctrl-P
            key = Mock()
            key.is_sequence = False
            key.__str__ = lambda self: '\x10'  # Ctrl-P
            
            editor._handle_key(key)
            
            # Verify error message
            assert "Print failed" in editor.status_message
            assert "Printer not found" in editor.status_message


def test_ps_save_error_handling():
    """Test error handling during PS save."""
    editor = create_mock_editor()
    editor.prompt_mode = 'ps_filename'
    editor.prompt_input = "/invalid/path/test.ps"
    editor._pending_print_pages = [["Page 1"]]
    
    with patch('pagemark.editor.PrintOutput') as mock_output_class:
        mock_output = Mock()
        mock_output.validate_output_path.return_value = (False, "Directory does not exist")
        mock_output_class.return_value = mock_output
        
        # Simulate Enter key
        key = Mock()
        key.is_sequence = True
        key.code = 343  # Enter key code
        
        editor._handle_ps_filename_prompt(key)
        
        # Verify error message
        assert "Directory does not exist" in editor.status_message
        
        # Verify prompt cleared
        assert editor.prompt_mode is None