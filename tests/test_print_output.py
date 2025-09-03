"""Tests for print output functionality."""

import os
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pagemark.print_output import PrintOutput


def create_test_pages():
    """Create test pages for printing."""
    # Create simple 85x66 pages
    page1 = [" " * 85 for _ in range(66)]
    page1[10] = " " * 10 + "Test Page 1" + " " * 64
    
    page2 = [" " * 85 for _ in range(66)]
    page2[10] = " " * 10 + "Test Page 2" + " " * 64
    
    return [page1, page2]


def test_check_command_availability():
    """Test checking for available commands."""
    with patch("shutil.which") as mock_which:
        # All commands available
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        output = PrintOutput()
        assert output.lpr_available == True
        assert output.ps2pdf_available == True
        assert output.enscript_available == True
        
        # No commands available
        mock_which.side_effect = lambda cmd: None
        output = PrintOutput()
        assert output.lpr_available == False
        assert output.ps2pdf_available == False
        assert output.enscript_available == False


def test_print_to_printer_success():
    """Test successful printing to a printer."""
    with patch("shutil.which", return_value="/usr/bin/lpr"):
        output = PrintOutput()
        pages = create_test_pages()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("tempfile.NamedTemporaryFile"):
                with patch("os.unlink"):
                    success, error = output.print_to_printer(pages, "TestPrinter", double_sided=True)
                    
                    assert success == True
                    assert error == ""
                    
                    # Check that lpr was called with correct arguments
                    call_args = mock_run.call_args[0][0]
                    assert "lpr" in call_args
                    assert "-P" in call_args
                    assert "TestPrinter" in call_args
                    assert "-o" in call_args
                    assert "sides=two-sided-long-edge" in call_args


def test_print_to_printer_no_lpr():
    """Test printing when lpr is not available."""
    with patch("shutil.which", return_value=None):
        output = PrintOutput()
        pages = create_test_pages()
        
        success, error = output.print_to_printer(pages, "TestPrinter")
        
        assert success == False
        assert "lpr command not found" in error


def test_print_to_printer_no_printer():
    """Test printing with no printer specified."""
    with patch("shutil.which", return_value="/usr/bin/lpr"):
        output = PrintOutput()
        pages = create_test_pages()
        
        success, error = output.print_to_printer(pages, "")
        
        assert success == False
        assert "No printer specified" in error


def test_print_to_printer_failure():
    """Test handling of print command failure."""
    with patch("shutil.which", return_value="/usr/bin/lpr"):
        output = PrintOutput()
        pages = create_test_pages()
        
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Printer not found"
        
        with patch("subprocess.run", return_value=mock_result):
            with patch("tempfile.NamedTemporaryFile"):
                with patch("os.unlink"):
                    success, error = output.print_to_printer(pages, "BadPrinter")
                    
                    assert success == False
                    assert "Printer not found" in error


def test_print_to_printer_timeout():
    """Test handling of print command timeout."""
    with patch("shutil.which", return_value="/usr/bin/lpr"):
        output = PrintOutput()
        pages = create_test_pages()
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("lpr", 10)):
            with patch("tempfile.NamedTemporaryFile"):
                with patch("os.unlink"):
                    success, error = output.print_to_printer(pages, "SlowPrinter")
                    
                    assert success == False
                    assert "timed out" in error


def test_save_to_pdf_with_tools():
    """Test PDF generation when enscript and ps2pdf are available."""
    with patch("shutil.which") as mock_which:
        def which_side_effect(cmd):
            if cmd in ["enscript", "ps2pdf"]:
                return f"/usr/bin/{cmd}"
            return None
        
        mock_which.side_effect = which_side_effect
        output = PrintOutput()
        pages = create_test_pages()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("subprocess.run", return_value=mock_result):
            with patch("tempfile.NamedTemporaryFile"):
                with patch("os.unlink"):
                    success, error = output.save_to_pdf(pages, "output.pdf")
                    
                    assert success == True
                    assert error == ""


def test_save_to_pdf_fallback_to_text():
    """Test PDF generation fallback when tools aren't available."""
    with patch("shutil.which", return_value=None):
        output = PrintOutput()
        pages = create_test_pages()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "output.pdf")
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                success, error = output.save_to_pdf(pages, output_file)
                
                assert success == True
                assert "PDF tools not available" in error
                assert ".txt" in error


def test_save_as_text():
    """Test saving pages as text file."""
    with patch("shutil.which", return_value=None):
        output = PrintOutput()
        pages = create_test_pages()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "output.txt")
            
            success, error = output._save_as_text(pages, output_file)
            
            assert success == True
            assert error == ""
            assert os.path.exists(output_file)
            
            # Check content
            with open(output_file, 'r') as f:
                content = f.read()
                assert "Test Page 1" in content
                assert "Test Page 2" in content
                assert "\f" in content  # Form feed between pages


def test_validate_output_path_valid():
    """Test validating a valid output path."""
    output = PrintOutput()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        valid_path = os.path.join(temp_dir, "output.pdf")
        
        is_valid, error = output.validate_output_path(valid_path)
        
        assert is_valid == True
        assert error == ""


def test_validate_output_path_nonexistent_directory():
    """Test validating path with non-existent directory."""
    output = PrintOutput()
    
    invalid_path = "/nonexistent/directory/output.pdf"
    
    is_valid, error = output.validate_output_path(invalid_path)
    
    assert is_valid == False
    assert "Directory does not exist" in error


def test_validate_output_path_readonly_directory():
    """Test validating path in read-only directory."""
    output = PrintOutput()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Make directory read-only
        os.chmod(temp_dir, 0o444)
        
        readonly_path = os.path.join(temp_dir, "output.pdf")
        
        is_valid, error = output.validate_output_path(readonly_path)
        
        # Restore permissions for cleanup
        os.chmod(temp_dir, 0o755)
        
        assert is_valid == False
        assert "not writable" in error


def test_validate_output_path_readonly_file():
    """Test validating path with read-only existing file."""
    output = PrintOutput()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "readonly.pdf")
        
        # Create read-only file
        with open(file_path, 'w') as f:
            f.write("test")
        os.chmod(file_path, 0o444)
        
        is_valid, error = output.validate_output_path(file_path)
        
        # Restore permissions for cleanup
        os.chmod(file_path, 0o644)
        
        assert is_valid == False
        assert "not writable" in error


def test_pdf_extension_handling():
    """Test that .pdf extension is added if missing."""
    output = PrintOutput()
    
    # Mock the actual save methods
    with patch.object(output, '_save_as_text', return_value=(True, "")):
        # Test without extension
        success, error = output.save_to_pdf([], "output")
        # The method should add .pdf extension internally
        
        # Test with extension
        success, error = output.save_to_pdf([], "output.pdf")
        assert success == True