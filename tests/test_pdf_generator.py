"""Tests for PDF generation."""

from pagemark.pdf_generator import PDFGenerator


def test_basic_pdf_generation():
    """Test basic PDF generation."""
    generator = PDFGenerator()
    
    # Create simple page
    page = ["Line 1".ljust(85), "Line 2".ljust(85)]
    page.extend([" " * 85 for _ in range(64)])  # Fill to 66 lines
    
    pages = [page]
    
    pdf_content = generator.generate_pdf(pages)
    
    # Check PDF header
    assert pdf_content.startswith(b'%PDF')
    
    # Check for basic PDF structure
    assert b'/Type /Page' in pdf_content
    assert b'/Font' in pdf_content
    assert b'stream' in pdf_content  # Content streams
    
    # Content is likely compressed, just verify structure


def test_pdf_with_special_characters():
    """Test PDF generation with special characters."""
    generator = PDFGenerator()
    
    # Create page with special characters
    page = [
        "Test with (parentheses)".ljust(85),
        "Test with [brackets]".ljust(85),
        "Test with 'quotes'".ljust(85),
        "Test with \"double quotes\"".ljust(85),
    ]
    page.extend([" " * 85 for _ in range(62)])
    
    pages = [page]
    
    pdf_content = generator.generate_pdf(pages)
    
    # Should generate valid PDF
    assert pdf_content.startswith(b'%PDF')
    assert b'/Type /Page' in pdf_content


def test_pdf_with_unicode():
    """Test handling of Unicode characters."""
    generator = PDFGenerator()
    
    # Create page with unicode/extended ASCII
    page = [
        "Café résumé naïve".ljust(85),
        "Test with ñ and ü".ljust(85),
    ]
    page.extend([" " * 85 for _ in range(64)])
    
    pages = [page]
    
    pdf_content = generator.generate_pdf(pages)
    
    # Should generate valid PDF
    assert pdf_content.startswith(b'%PDF')
    assert b'/Type /Page' in pdf_content


def test_pdf_with_styled_text():
    """Test PDF generation with bold and underlined text."""
    generator = PDFGenerator()
    
    # Create page
    page = [
        "Normal text with BOLD word".ljust(85),
        "Text with underlined part".ljust(85),
    ]
    page.extend([" " * 85 for _ in range(64)])
    
    pages = [page]
    
    # Create style runs: (start_col, text, flags)
    # flags: 1=bold, 2=underline
    page_styles = [[
        [(17, "BOLD", 1)],  # Line 0: BOLD is bold
        [(10, "underlined", 2)],  # Line 1: underlined
    ] + [[] for _ in range(64)]]
    
    pdf_content = generator.generate_pdf(pages, page_styles)
    
    # Should generate valid PDF with font changes
    assert pdf_content.startswith(b'%PDF')
    assert b'/Type /Page' in pdf_content
    assert b'Courier-Bold' in pdf_content  # Bold font should be used


def test_pdf_with_empty_pages():
    """Test PDF generation with empty pages."""
    generator = PDFGenerator()
    
    # Create empty pages (all spaces)
    page1 = [" " * 85 for _ in range(66)]
    page2 = [" " * 85 for _ in range(66)]
    
    pages = [page1, page2]
    
    pdf_content = generator.generate_pdf(pages)
    
    # Should generate valid PDF
    assert pdf_content.startswith(b'%PDF')
    assert b'/Type /Page' in pdf_content


def test_pdf_page_count():
    """Test that PDF has correct number of pages."""
    generator = PDFGenerator()
    
    # Create 3 pages
    page = [" " * 85 for _ in range(66)]
    pages = [page, page, page]
    
    pdf_content = generator.generate_pdf(pages)
    
    # Should generate valid PDF
    assert pdf_content.startswith(b'%PDF')
    
    # Check for multiple pages in the Pages object
    # ReportLab generates /Count 3 for 3 pages
    assert b'/Count 3' in pdf_content  # 3 pages in document


def test_pdf_with_mixed_styles():
    """Test PDF with both bold and underline on same line."""
    generator = PDFGenerator()
    
    page = [
        "Text with BOLD and underlined words".ljust(85),
    ]
    page.extend([" " * 85 for _ in range(65)])
    
    pages = [page]
    
    # Multiple style runs on same line
    page_styles = [[
        [(10, "BOLD", 1), (19, "underlined", 2)],  # Two styled segments
    ] + [[] for _ in range(65)]]
    
    pdf_content = generator.generate_pdf(pages, page_styles)
    
    # Should generate valid PDF
    assert pdf_content.startswith(b'%PDF')
    assert b'Courier-Bold' in pdf_content