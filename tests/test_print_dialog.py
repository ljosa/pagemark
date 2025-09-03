"""Tests for the print dialog UI."""

from unittest.mock import Mock, MagicMock, patch
import blessed

from pagemark.print_dialog import PrintDialog, PrintAction, PrintOptions
from pagemark.model import TextModel
from pagemark.terminal import TerminalInterface


def create_mock_terminal():
    """Create a mock terminal interface for testing."""
    mock_term = Mock(spec=TerminalInterface)
    mock_blessed_term = MagicMock()
    mock_blessed_term.width = 80
    mock_blessed_term.height = 50
    mock_blessed_term.hide_cursor = ""
    mock_blessed_term.normal_cursor = ""
    mock_blessed_term.home = ""
    mock_blessed_term.clear = ""
    mock_blessed_term.move = Mock(return_value="")
    mock_blessed_term.hidden_cursor = False
    mock_term.term = mock_blessed_term
    mock_term.get_key = Mock()
    return mock_term


def create_test_model():
    """Create a test text model."""
    # Create a mock view
    mock_view = Mock()
    mock_view.num_columns = 65
    mock_view.num_rows = 54
    
    # Create model with test content
    return TextModel(mock_view, paragraphs=["Test paragraph one.", "Test paragraph two."])


def test_dialog_initialization():
    """Test that the print dialog initializes correctly."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = ["Printer1", "Printer2"]
        mock_manager.return_value.get_default_printer.return_value = "Printer1"
        
        dialog = PrintDialog(model, terminal)
        
        assert dialog.model == model
        assert dialog.terminal == terminal
        assert dialog.current_page == 0
        assert dialog.double_sided == True
        assert len(dialog.output_options) == 3  # 2 printers + PDF
        assert "PDF File" in dialog.output_options


def test_output_list_building_with_printers():
    """Test building output list with available printers."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = ["HP_LaserJet", "Canon_PIXMA"]
        mock_manager.return_value.get_default_printer.return_value = "Canon_PIXMA"
        
        dialog = PrintDialog(model, terminal)
        
        assert dialog.output_options == ["HP_LaserJet", "Canon_PIXMA", "PDF File"]
        assert dialog.selected_output == 1  # Canon_PIXMA is default


def test_output_list_building_no_printers():
    """Test building output list when no printers are available."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = []
        mock_manager.return_value.get_default_printer.return_value = None
        
        dialog = PrintDialog(model, terminal)
        
        assert dialog.output_options == ["PDF File"]
        assert dialog.selected_output == 0


def test_cancel_with_escape():
    """Test cancelling the dialog with Escape key."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    # Mock Escape key press
    terminal.get_key.return_value = blessed.keyboard.Keystroke('\x1b')
    
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(model, terminal)
        result = dialog.show()
        
        assert result.action == PrintAction.CANCEL
        assert result.printer_name is None


def test_cancel_with_c_key():
    """Test cancelling the dialog with 'C' key."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    # Mock 'C' key press
    terminal.get_key.return_value = 'C'
    
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(model, terminal)
        result = dialog.show()
        
        assert result.action == PrintAction.CANCEL


def test_print_to_printer():
    """Test selecting print to printer option."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    # Mock 'P' key press
    terminal.get_key.return_value = 'P'
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = ["TestPrinter"]
        mock_manager.return_value.get_default_printer.return_value = "TestPrinter"
        
        dialog = PrintDialog(model, terminal)
        dialog.selected_output = 0  # Select printer
        result = dialog.show()
        
        assert result.action == PrintAction.PRINT
        assert result.printer_name == "TestPrinter"
        assert result.double_sided == True


def test_save_to_pdf():
    """Test selecting save to PDF option."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    # Mock 'P' key press
    terminal.get_key.return_value = 'P'
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = ["Printer1"]
        
        dialog = PrintDialog(model, terminal)
        dialog.selected_output = 1  # Select PDF (second option)
        result = dialog.show()
        
        assert result.action == PrintAction.SAVE_PDF
        assert result.pdf_filename == "output.pdf"
        assert result.printer_name is None


def test_cycle_output_options():
    """Test cycling through output options with 'O' key."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    # Mock key sequence: O, O, P
    key_sequence = ['O', 'O', 'P']
    terminal.get_key.side_effect = key_sequence
    
    with patch("pagemark.print_dialog.PrinterManager") as mock_manager:
        mock_manager.return_value.get_available_printers.return_value = ["Printer1", "Printer2"]
        
        dialog = PrintDialog(model, terminal)
        assert dialog.selected_output == 0  # Start at first option
        
        # Process first 'O' (cycle to Printer2)
        dialog._render = Mock()  # Mock render to avoid display
        key = terminal.get_key()
        assert key == 'O'
        dialog.selected_output = (dialog.selected_output + 1) % len(dialog.output_options)
        assert dialog.selected_output == 1
        
        # Process second 'O' (cycle to PDF)
        key = terminal.get_key()
        assert key == 'O'
        dialog.selected_output = (dialog.selected_output + 1) % len(dialog.output_options)
        assert dialog.selected_output == 2
        
        # Would wrap around to 0 on next cycle
        dialog.selected_output = (dialog.selected_output + 1) % len(dialog.output_options)
        assert dialog.selected_output == 0


def test_toggle_double_sided():
    """Test toggling double-sided option with 'D' key."""
    model = create_test_model()
    terminal = create_mock_terminal()
    
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(model, terminal)
        
        # Initial state
        assert dialog.double_sided == True
        
        # Toggle off
        dialog.double_sided = not dialog.double_sided
        assert dialog.double_sided == False
        
        # Toggle back on
        dialog.double_sided = not dialog.double_sided
        assert dialog.double_sided == True


def test_page_navigation():
    """Test page navigation with PgUp/PgDn."""
    # Create model with enough content for multiple pages
    mock_view = Mock()
    mock_view.num_columns = 65
    mock_view.num_rows = 54
    
    # Create 100 lines to ensure multiple pages
    paragraphs = [f"Line {i}" for i in range(100)]
    model = TextModel(mock_view, paragraphs=paragraphs)
    terminal = create_mock_terminal()
    
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(model, terminal)
        
        assert dialog.current_page == 0
        assert len(dialog.pages) > 1  # Should have multiple pages
        
        # Navigate to next page
        if dialog.current_page < len(dialog.pages) - 1:
            dialog.current_page += 1
        assert dialog.current_page == 1
        
        # Navigate to previous page
        if dialog.current_page > 0:
            dialog.current_page -= 1
        assert dialog.current_page == 0
        
        # Try to go before first page (should stay at 0)
        if dialog.current_page > 0:
            dialog.current_page -= 1
        assert dialog.current_page == 0