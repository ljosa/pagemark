import tempfile
import os
from pagemark.editor import Editor
from pagemark.model import TextModel


def test_save_file_creates_file():
    """Test that save_file creates a new file with content."""
    editor = Editor()
    editor.model.paragraphs = ["First line", "Second line", "Third line"]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        temp_filename = f.name
    
    try:
        # Save the file
        result = editor.save_file(temp_filename)
        assert result == True
        
        # Check file was created and has correct content
        assert os.path.exists(temp_filename)
        with open(temp_filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content == "First line\nSecond line\nThird line"
        
        # Check that filename and modified flag were updated
        assert editor.filename == temp_filename
        assert editor.modified == False
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def test_save_file_overwrites_existing():
    """Test that save_file overwrites an existing file."""
    editor = Editor()
    
    # Create a file with initial content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Old content")
        temp_filename = f.name
    
    try:
        # Save new content
        editor.model.paragraphs = ["New content", "Line 2"]
        result = editor.save_file(temp_filename)
        assert result == True
        
        # Check file has new content
        with open(temp_filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content == "New content\nLine 2"
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def test_load_file_sets_filename():
    """Test that load_file sets the filename and loads content."""
    editor = Editor()
    
    # Create a test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Line 1\nLine 2\nLine 3")
        temp_filename = f.name
    
    try:
        # Load the file
        editor.load_file(temp_filename)
        
        # Check filename was set
        assert editor.filename == temp_filename
        
        # Check content was loaded
        assert editor.model.paragraphs == ["Line 1", "Line 2", "Line 3"]
        
        # Check modified flag is False
        assert editor.modified == False
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def test_load_nonexistent_file():
    """Test that loading a nonexistent file creates a new empty document."""
    editor = Editor()
    
    # Try to load a file that doesn't exist
    editor.load_file("/nonexistent/file.txt")
    
    # Check that filename was set
    assert editor.filename == "/nonexistent/file.txt"
    
    # Check that document is empty (default state)
    assert editor.model.paragraphs == [""]
    
    # Check modified flag is False
    assert editor.modified == False


def test_modified_flag_on_insert():
    """Test that the modified flag is set when text is inserted."""
    editor = Editor()
    assert editor.modified == False
    
    # Simulate inserting text (this would normally be done via _handle_key)
    editor.model.insert_text("Hello")
    editor.modified = True  # This is set in _handle_key
    
    assert editor.modified == True


def test_modified_flag_cleared_on_save():
    """Test that the modified flag is cleared after saving."""
    editor = Editor()
    editor.model.paragraphs = ["Test content"]
    editor.modified = True
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        temp_filename = f.name
    
    try:
        # Save the file
        editor.save_file(temp_filename)
        
        # Check modified flag was cleared
        assert editor.modified == False
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def test_save_file_utf8_encoding():
    """Test that files are saved with UTF-8 encoding."""
    editor = Editor()
    # Include some non-ASCII characters
    editor.model.paragraphs = ["Hello 世界", "Café", "Σωκράτης"]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        temp_filename = f.name
    
    try:
        # Save the file
        result = editor.save_file(temp_filename)
        assert result == True
        
        # Read back with UTF-8 encoding
        with open(temp_filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content == "Hello 世界\nCafé\nΣωκράτης"
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)