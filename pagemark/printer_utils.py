"""Utilities for printer discovery and management using CUPS."""

import subprocess
import shutil
from typing import List, Optional


class PrinterManager:
    """Manages printer discovery and selection using CUPS."""
    
    def __init__(self):
        """Initialize the printer manager."""
        self.cups_available = self._check_cups_available()
        self._printer_cache = None
        self._default_cache = None
    
    def _check_cups_available(self) -> bool:
        """Check if CUPS commands are available on the system.
        
        Returns:
            True if lpstat is available, False otherwise.
        """
        return shutil.which("lpstat") is not None
    
    def get_available_printers(self) -> List[str]:
        """Query CUPS for available printers.
        
        Returns:
            List of printer names. Empty list if CUPS is not available
            or no printers are configured.
        """
        if self._printer_cache is not None:
            return self._printer_cache
        
        if not self.cups_available:
            self._printer_cache = []
            return []
        
        try:
            # Use lpstat -p to list printers
            # Format: "printer HP_LaserJet_4000 is idle.  enabled since ..."
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                self._printer_cache = []
                return []
            
            printers = []
            for line in result.stdout.splitlines():
                if line.startswith("printer "):
                    # Extract printer name
                    parts = line.split()
                    if len(parts) >= 2:
                        printer_name = parts[1]
                        printers.append(printer_name)
            
            self._printer_cache = printers
            return printers
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            self._printer_cache = []
            return []
    
    def get_default_printer(self) -> Optional[str]:
        """Get the system default printer.
        
        Returns:
            Name of the default printer, or None if no default is set.
        """
        if self._default_cache is not None:
            return self._default_cache
        
        if not self.cups_available:
            self._default_cache = None
            return None
        
        try:
            # Use lpstat -d to get default printer
            # Format: "system default destination: HP_LaserJet_4000"
            result = subprocess.run(
                ["lpstat", "-d"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                self._default_cache = None
                return None
            
            output = result.stdout.strip()
            if ":" in output:
                # Extract printer name after the colon
                default_printer = output.split(":", 1)[1].strip()
                if default_printer and default_printer != "none":
                    self._default_cache = default_printer
                    return default_printer
            
            self._default_cache = None
            return None
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            self._default_cache = None
            return None
    
    def is_printer_available(self, printer_name: str) -> bool:
        """Check if a specific printer is available.
        
        Args:
            printer_name: The name of the printer to check.
            
        Returns:
            True if the printer is available, False otherwise.
        """
        return printer_name in self.get_available_printers()
    
    def validate_printer(self, printer_name: str) -> bool:
        """Validate that a printer exists and is ready.
        
        Args:
            printer_name: The name of the printer to validate.
            
        Returns:
            True if the printer exists and is enabled, False otherwise.
        """
        if not self.cups_available or not printer_name:
            return False
        
        try:
            # Use lpstat -p to check specific printer status
            result = subprocess.run(
                ["lpstat", "-p", printer_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False
            
            # Check if printer is enabled (not disabled)
            output = result.stdout.strip().lower()
            if "enabled" in output or "idle" in output or "ready" in output:
                return True
            
            return False
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False
    
    def clear_cache(self):
        """Clear the cached printer information.
        
        This should be called if the printer configuration might have changed.
        """
        self._printer_cache = None
        self._default_cache = None