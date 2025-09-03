"""Tests for printer utilities."""

import subprocess
from unittest.mock import Mock, patch, MagicMock
from pagemark.printer_utils import PrinterManager


def test_cups_availability_check():
    """Test checking if CUPS is available."""
    manager = PrinterManager()
    
    # Mock shutil.which
    with patch("shutil.which") as mock_which:
        # CUPS available
        mock_which.return_value = "/usr/bin/lpstat"
        manager = PrinterManager()
        assert manager.cups_available == True
        
        # CUPS not available
        mock_which.return_value = None
        manager = PrinterManager()
        assert manager.cups_available == False


def test_get_available_printers_no_cups():
    """Test getting printers when CUPS is not available."""
    with patch("shutil.which", return_value=None):
        manager = PrinterManager()
        printers = manager.get_available_printers()
        assert printers == []


def test_get_available_printers_with_cups():
    """Test getting printers when CUPS is available."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock successful lpstat output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """printer HP_LaserJet_4000 is idle.  enabled since Mon Dec 18 10:00:00 2023
printer Canon_PIXMA is idle.  enabled since Mon Dec 18 10:00:00 2023
printer Brother_HL_2270DW is idle.  enabled since Mon Dec 18 10:00:00 2023"""
        
        with patch("subprocess.run", return_value=mock_result):
            printers = manager.get_available_printers()
            
            assert len(printers) == 3
            assert "HP_LaserJet_4000" in printers
            assert "Canon_PIXMA" in printers
            assert "Brother_HL_2270DW" in printers


def test_get_available_printers_error():
    """Test handling of lpstat errors."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock failed lpstat
        mock_result = Mock()
        mock_result.returncode = 1
        
        with patch("subprocess.run", return_value=mock_result):
            printers = manager.get_available_printers()
            assert printers == []


def test_get_available_printers_timeout():
    """Test handling of lpstat timeout."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("lpstat", 5)):
            printers = manager.get_available_printers()
            assert printers == []


def test_get_default_printer():
    """Test getting the default printer."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock successful lpstat -d output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "system default destination: HP_LaserJet_4000"
        
        with patch("subprocess.run", return_value=mock_result):
            default = manager.get_default_printer()
            assert default == "HP_LaserJet_4000"


def test_get_default_printer_no_default():
    """Test when no default printer is set."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock lpstat -d with no default
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "no system default destination"
        
        with patch("subprocess.run", return_value=mock_result):
            default = manager.get_default_printer()
            assert default is None


def test_is_printer_available():
    """Test checking if a specific printer is available."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock printer list
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "printer HP_LaserJet_4000 is idle.  enabled since Mon Dec 18 10:00:00 2023"
        
        with patch("subprocess.run", return_value=mock_result):
            assert manager.is_printer_available("HP_LaserJet_4000") == True
            assert manager.is_printer_available("NonExistent_Printer") == False


def test_validate_printer():
    """Test validating a printer's status."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock successful validation
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "printer HP_LaserJet_4000 is idle.  enabled since Mon Dec 18 10:00:00 2023"
        
        with patch("subprocess.run", return_value=mock_result):
            assert manager.validate_printer("HP_LaserJet_4000") == True
        
        # Mock disabled printer
        mock_result.stdout = "printer HP_LaserJet_4000 disabled since Mon Dec 18 10:00:00 2023"
        
        with patch("subprocess.run", return_value=mock_result):
            assert manager.validate_printer("HP_LaserJet_4000") == False
        
        # Mock printer not found
        mock_result.returncode = 1
        
        with patch("subprocess.run", return_value=mock_result):
            assert manager.validate_printer("NonExistent") == False


def test_cache_behavior():
    """Test that printer information is cached."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        # Mock printer list
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "printer HP_LaserJet_4000 is idle.  enabled since Mon Dec 18 10:00:00 2023"
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # First call
            printers1 = manager.get_available_printers()
            assert mock_run.call_count == 1
            
            # Second call should use cache
            printers2 = manager.get_available_printers()
            assert mock_run.call_count == 1  # No additional call
            assert printers1 == printers2
            
            # Clear cache
            manager.clear_cache()
            
            # Third call should query again
            printers3 = manager.get_available_printers()
            assert mock_run.call_count == 2  # New call made


def test_cache_for_default_printer():
    """Test that default printer is cached."""
    with patch("shutil.which", return_value="/usr/bin/lpstat"):
        manager = PrinterManager()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "system default destination: HP_LaserJet_4000"
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # First call
            default1 = manager.get_default_printer()
            call_count_1 = mock_run.call_count
            
            # Second call should use cache
            default2 = manager.get_default_printer()
            assert mock_run.call_count == call_count_1  # No additional call
            assert default1 == default2
            
            # Clear cache
            manager.clear_cache()
            
            # Third call should query again
            default3 = manager.get_default_printer()
            assert mock_run.call_count > call_count_1  # New call made