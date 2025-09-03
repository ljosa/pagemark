"""Handle actual printing and PDF generation."""

import subprocess
import tempfile
import os
import shutil
from typing import List, Optional


class PrintOutput:
    """Handles printing to printers and generating PDF files."""
    
    def __init__(self):
        """Initialize print output handler."""
        self.lpr_available = shutil.which("lpr") is not None
        self.ps2pdf_available = shutil.which("ps2pdf") is not None
        self.enscript_available = shutil.which("enscript") is not None
    
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
            # Create temporary file with print content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', 
                                           delete=False) as temp_file:
                temp_filename = temp_file.name
                
                # Write pages with form feeds between them
                for i, page in enumerate(pages):
                    for line in page:
                        temp_file.write(line + '\n')
                    # Add form feed between pages (but not after last page)
                    if i < len(pages) - 1:
                        temp_file.write('\f')
            
            # Build lpr command
            cmd = ['lpr', '-P', printer]
            
            # Add double-sided option if requested
            if double_sided:
                # Different systems use different options for double-sided
                # Try common CUPS option
                cmd.extend(['-o', 'sides=two-sided-long-edge'])
            
            # Add the file to print
            cmd.append(temp_filename)
            
            # Execute print command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up temp file
            os.unlink(temp_filename)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Print command failed"
                return False, f"Print failed: {error_msg}"
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            if 'temp_filename' in locals():
                os.unlink(temp_filename)
            return False, "Print command timed out"
        except Exception as e:
            if 'temp_filename' in locals():
                os.unlink(temp_filename)
            return False, f"Print error: {str(e)}"
    
    def save_to_pdf(self, pages: List[List[str]], filename: str) -> tuple[bool, str]:
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
            # First try to generate PDF using enscript + ps2pdf
            if self.enscript_available and self.ps2pdf_available:
                return self._save_pdf_with_enscript(pages, filename)
            
            # Fallback: save as formatted text file with .pdf name
            # (User can convert it later with other tools)
            return self._save_as_text(pages, filename)
            
        except Exception as e:
            return False, f"PDF generation error: {str(e)}"
    
    def _save_pdf_with_enscript(self, pages: List[List[str]], 
                                filename: str) -> tuple[bool, str]:
        """Generate PDF using enscript and ps2pdf.
        
        Args:
            pages: List of pages from PrintFormatter.
            filename: Output PDF filename.
            
        Returns:
            Tuple of (success, error_message).
        """
        try:
            # Create temporary text file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', 
                                           delete=False) as text_file:
                text_filename = text_file.name
                
                # Write pages with form feeds
                for i, page in enumerate(pages):
                    for line in page:
                        text_file.write(line + '\n')
                    if i < len(pages) - 1:
                        text_file.write('\f')
            
            # Create temporary PostScript file
            ps_filename = text_filename.replace('.txt', '.ps')
            
            # Convert text to PostScript using enscript
            # -B: no page headers
            # -f: font (Courier10)
            # -M: media size (Letter)
            enscript_cmd = [
                'enscript',
                '-B',  # No headers
                '-fCourier10',  # Courier 10pt font
                '-MLetter',  # Letter size paper
                '-o', ps_filename,  # Output file
                text_filename
            ]
            
            result = subprocess.run(
                enscript_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                os.unlink(text_filename)
                return False, f"PostScript generation failed: {result.stderr}"
            
            # Convert PostScript to PDF
            ps2pdf_cmd = ['ps2pdf', ps_filename, filename]
            
            result = subprocess.run(
                ps2pdf_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up temp files
            os.unlink(text_filename)
            os.unlink(ps_filename)
            
            if result.returncode != 0:
                return False, f"PDF conversion failed: {result.stderr}"
            
            return True, ""
            
        except Exception as e:
            # Clean up any temp files that might exist
            for temp_file in [text_filename, ps_filename]:
                if 'temp_file' in locals() and os.path.exists(temp_file):
                    os.unlink(temp_file)
            return False, str(e)
    
    def _save_as_text(self, pages: List[List[str]], filename: str) -> tuple[bool, str]:
        """Save pages as a formatted text file.
        
        This is the fallback when PDF tools aren't available.
        
        Args:
            pages: List of pages from PrintFormatter.
            filename: Output filename.
            
        Returns:
            Tuple of (success, error_message).
        """
        try:
            # Change extension to .txt if it's .pdf
            if filename.endswith('.pdf'):
                text_filename = filename[:-4] + '.txt'
                message = f"PDF tools not available. Saved as text file: {text_filename}"
            else:
                text_filename = filename
                message = ""
            
            with open(text_filename, 'w') as f:
                for i, page in enumerate(pages):
                    for line in page:
                        f.write(line + '\n')
                    # Add form feed between pages
                    if i < len(pages) - 1:
                        f.write('\f')
            
            if message:
                return True, message
            return True, ""
            
        except IOError as e:
            return False, f"Failed to save file: {str(e)}"
    
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
            
        except Exception as e:
            return False, f"Path validation error: {str(e)}"