"""Handle actual printing and PDF generation."""

import subprocess
import tempfile
import os
import shutil
from typing import List, Optional

from .postscript import PostScriptGenerator


class PrintOutput:
    """Handles printing to printers and generating PDF files."""
    
    def __init__(self):
        """Initialize print output handler."""
        self.lpr_available = shutil.which("lpr") is not None
        self.ps_generator = PostScriptGenerator()
    
    def print_to_printer(self, pages: List[List[str]], printer: str, 
                        double_sided: bool = False) -> tuple[bool, str]:
        """Submit print job to CUPS printer.
        
        Args:
            pages: List of pages from PrintFormatter (85x66 chars each).
            printer: Name of the printer to use.
            double_sided: Whether to print double-sided.
            
        Returns:
            Tuple of (success, error_message).
        """
        if not self.lpr_available:
            return False, "Printing is not available (lpr command not found)"
        
        if not printer:
            return False, "No printer specified"
        
        try:
            # Generate PostScript using our Python generator
            runs = getattr(self, 'page_runs', None)
            postscript_content = self.ps_generator.generate_postscript(pages, runs)
            
            # Create temporary PostScript file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps', 
                                           delete=False) as ps_file:
                ps_filename = ps_file.name
                ps_file.write(postscript_content)
            
            # Build lpr command to print PostScript
            cmd = ['lpr', '-P', printer]
            
            # Add double-sided option if requested
            if double_sided:
                # CUPS option for double-sided printing
                cmd.extend(['-o', 'sides=two-sided-long-edge'])
            
            # Add the PostScript file to print
            cmd.append(ps_filename)
            
            # Execute print command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up PostScript file
            os.unlink(ps_filename)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Print command failed"
                return False, f"Print failed: {error_msg}"
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            if 'ps_filename' in locals() and os.path.exists(ps_filename):
                os.unlink(ps_filename)
            return False, "Print command timed out"
        except (OSError, subprocess.SubprocessError) as e:
            # Justification: ensure temp file cleanup and return a user-facing error
            if 'ps_filename' in locals() and os.path.exists(ps_filename):
                os.unlink(ps_filename)
            return False, f"Print error: {str(e)}"
    
    def save_to_file(self, pages: List[List[str]], filename: str) -> tuple[bool, str]:
        """Generate PostScript file from pages.
        
        Args:
            pages: List of pages from PrintFormatter (85x66 chars each).
            filename: Output PostScript filename.
            
        Returns:
            Tuple of (success, error_message).
        """
        # Ensure filename has .ps extension
        if not filename.endswith('.ps'):
            filename += '.ps'
        
        try:
            # Generate PostScript using our Python generator
            runs = getattr(self, 'page_runs', None)
            postscript_content = self.ps_generator.generate_postscript(pages, runs)
            
            # Save as PostScript file
            with open(filename, 'w') as f:
                f.write(postscript_content)
            
            return True, ""
            
        except OSError as e:
            # File system errors are expected here; report succinctly
            return False, f"Save error: {str(e)}"
    
    
    def validate_output_path(self, filename: str) -> tuple[bool, str]:
        """Check if the output path is valid and writable.
        
        Args:
            filename: The proposed output filename.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            # Get directory path
            directory = os.path.dirname(filename) or '.'
            
            # Check if directory exists
            if not os.path.exists(directory):
                return False, f"Directory does not exist: {directory}"
            
            # Check if directory is writable
            if not os.access(directory, os.W_OK):
                return False, f"Directory is not writable: {directory}"
            
            # Check if file exists and is writable
            if os.path.exists(filename):
                if not os.access(filename, os.W_OK):
                    return False, f"File exists and is not writable: {filename}"
            
            return True, ""
            
        except OSError as e:
            return False, f"Path validation error: {str(e)}"
