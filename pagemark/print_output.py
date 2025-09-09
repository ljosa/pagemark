"""Handle actual printing and PDF generation."""

import subprocess
import tempfile
import os
import shutil
from typing import List, Optional

from .pdf_generator import PDFGenerator


class PrintOutput:
    """Handles printing to printers and generating PDF files."""
    
    def __init__(self):
        """Initialize print output handler."""
        self.lpr_available = shutil.which("lpr") is not None
        self.pdf_generator = PDFGenerator()
    
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
            # Generate PDF using our Python generator
            runs = getattr(self, 'page_runs', None)
            pdf_content = self.pdf_generator.generate_pdf(pages, runs)
            
            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', 
                                           delete=False) as pdf_file:
                pdf_filename = pdf_file.name
                pdf_file.write(pdf_content)
            
            # Build lpr command to print PDF
            cmd = ['lpr', '-P', printer]
            
            # Add double-sided option if requested
            if double_sided:
                # CUPS option for double-sided printing
                cmd.extend(['-o', 'sides=two-sided-long-edge'])
            
            # Add the PDF file to print
            cmd.append(pdf_filename)
            
            # Execute print command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up PDF file
            os.unlink(pdf_filename)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Print command failed"
                return False, f"Print failed: {error_msg}"
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            if 'pdf_filename' in locals() and os.path.exists(pdf_filename):
                os.unlink(pdf_filename)
            return False, "Print command timed out"
        except (OSError, subprocess.SubprocessError) as e:
            # Justification: ensure temp file cleanup and return a user-facing error
            if 'pdf_filename' in locals() and os.path.exists(pdf_filename):
                os.unlink(pdf_filename)
            return False, f"Print error: {str(e)}"
    
    def save_to_file(self, pages: List[List[str]], filename: str) -> tuple[bool, str]:
        """Generate PDF file from pages.
        
        Args:
            pages: List of pages from PrintFormatter (85x66 chars each).
            filename: Output PDF filename.
            
        Returns:
            Tuple of (success, error_message).
        """
        # Ensure filename has .pdf extension
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        try:
            # Generate PDF using our Python generator
            runs = getattr(self, 'page_runs', None)
            pdf_content = self.pdf_generator.generate_pdf(pages, runs)
            
            # Save as PDF file
            with open(filename, 'wb') as f:
                f.write(pdf_content)
            
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
