"""Unit tests for the autosave module."""

import os
import tempfile
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from pagemark.autosave import (
    get_swap_path,
    write_swap_file,
    delete_swap_file,
    swap_file_exists,
    read_swap_file,
)
from pagemark.constants import EditorConstants
from pagemark.editor import Editor
from pagemark.session import get_session


@pytest.fixture
def clean_session():
    """Clear session before test to avoid pollution."""
    get_session().clear()
    yield
    get_session().clear()


class TestGetSwapPath:
    """Tests for get_swap_path function."""

    def test_simple_filename(self):
        """Test swap path for a simple filename."""
        result = get_swap_path("/path/to/document.txt")
        assert result == "/path/to/.document.txt.swp"

    def test_filename_in_current_directory(self):
        """Test swap path for a file in current directory."""
        result = get_swap_path("document.txt")
        assert result == "./.document.txt.swp"

    def test_filename_with_no_extension(self):
        """Test swap path for a file without extension."""
        result = get_swap_path("/path/to/README")
        assert result == "/path/to/.README.swp"

    def test_filename_with_multiple_dots(self):
        """Test swap path for a file with multiple dots."""
        result = get_swap_path("/path/to/file.name.txt")
        assert result == "/path/to/.file.name.txt.swp"


class TestWriteSwapFile:
    """Tests for write_swap_file function."""

    def test_write_swap_file_success(self):
        """Test successful swap file write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")
            content = "Hello, World!\nThis is a test."

            result = write_swap_file(filename, content)

            assert result is True
            swap_path = get_swap_path(filename)
            assert os.path.exists(swap_path)
            with open(swap_path, 'r') as f:
                assert f.read() == content

    def test_write_swap_file_overwrites_existing(self):
        """Test that write_swap_file overwrites existing swap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")

            write_swap_file(filename, "First content")
            write_swap_file(filename, "Second content")

            swap_path = get_swap_path(filename)
            with open(swap_path, 'r') as f:
                assert f.read() == "Second content"

    def test_write_swap_file_permission_error(self):
        """Test write_swap_file returns False on permission error."""
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.side_effect = PermissionError("Permission denied")
            result = write_swap_file("/some/path/file.txt", "content")
            assert result is False


class TestDeleteSwapFile:
    """Tests for delete_swap_file function."""

    def test_delete_existing_swap_file(self):
        """Test deleting an existing swap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")
            write_swap_file(filename, "content")
            swap_path = get_swap_path(filename)
            assert os.path.exists(swap_path)

            delete_swap_file(filename)

            assert not os.path.exists(swap_path)

    def test_delete_nonexistent_swap_file(self):
        """Test deleting a non-existent swap file doesn't raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "nonexistent.txt")
            # Should not raise
            delete_swap_file(filename)


class TestSwapFileExists:
    """Tests for swap_file_exists function."""

    def test_swap_file_exists_true(self):
        """Test returns True when swap file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")
            write_swap_file(filename, "content")

            assert swap_file_exists(filename) is True

    def test_swap_file_exists_false(self):
        """Test returns False when swap file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")

            assert swap_file_exists(filename) is False


class TestReadSwapFile:
    """Tests for read_swap_file function."""

    def test_read_existing_swap_file(self):
        """Test reading an existing swap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")
            content = "Test content\nwith multiple lines"
            write_swap_file(filename, content)

            result = read_swap_file(filename)

            assert result == content

    def test_read_nonexistent_swap_file(self):
        """Test reading a non-existent swap file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "nonexistent.txt")

            result = read_swap_file(filename)

            assert result is None


class TestCalculateAutosaveTimeout:
    """Tests for Editor._calculate_autosave_timeout method."""

    def test_no_timeout_when_not_modified(self, clean_session):
        """Test returns None when document is not modified."""
        editor = Editor()
        editor.modified = False
        editor.filename = "test.txt"

        result = editor._calculate_autosave_timeout()

        assert result is None

    def test_no_timeout_when_no_filename(self, clean_session):
        """Test returns None when document has no filename."""
        editor = Editor()
        editor.modified = True
        editor.filename = None

        result = editor._calculate_autosave_timeout()

        assert result is None

    def test_debounce_timeout_calculation(self, clean_session):
        """Test debounce timeout is calculated correctly."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        editor._last_edit_time = time.monotonic()
        editor._last_autosave_time = None

        result = editor._calculate_autosave_timeout()

        # Should be close to AUTOSAVE_DEBOUNCE_SECONDS
        assert result is not None
        assert 0 < result <= EditorConstants.AUTOSAVE_DEBOUNCE_SECONDS

    def test_backstop_timeout_calculation(self, clean_session):
        """Test backstop timeout when debounce has passed."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        # Set last edit time well in the past
        editor._last_edit_time = time.monotonic() - 100
        # Set last autosave recently
        editor._last_autosave_time = time.monotonic()

        result = editor._calculate_autosave_timeout()

        # Should be close to AUTOSAVE_BACKSTOP_SECONDS
        assert result is not None
        assert 0 < result <= EditorConstants.AUTOSAVE_BACKSTOP_SECONDS

    def test_immediate_save_when_conditions_met(self, clean_session):
        """Test returns small timeout when ready to save."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        # Set times well in the past
        editor._last_edit_time = time.monotonic() - 100
        editor._last_autosave_time = time.monotonic() - 1000

        result = editor._calculate_autosave_timeout()

        assert result == 0.1


class TestMaybeAutosave:
    """Tests for Editor._maybe_autosave method."""

    def test_no_autosave_when_not_modified(self, clean_session):
        """Test no autosave when document is not modified."""
        editor = Editor()
        editor.modified = False
        editor.filename = "test.txt"

        with patch('pagemark.editor.write_swap_file') as mock_write:
            editor._maybe_autosave()
            mock_write.assert_not_called()

    def test_no_autosave_when_no_filename(self, clean_session):
        """Test no autosave when document has no filename."""
        editor = Editor()
        editor.modified = True
        editor.filename = None

        with patch('pagemark.editor.write_swap_file') as mock_write:
            editor._maybe_autosave()
            mock_write.assert_not_called()

    def test_autosave_when_debounce_met(self, clean_session):
        """Test autosave triggers when debounce condition is met."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        editor._last_edit_time = time.monotonic() - EditorConstants.AUTOSAVE_DEBOUNCE_SECONDS - 1
        editor._last_autosave_time = None

        with patch('pagemark.editor.write_swap_file', return_value=True) as mock_write:
            editor._maybe_autosave()
            mock_write.assert_called_once()

    def test_autosave_when_backstop_met(self, clean_session):
        """Test autosave triggers when backstop condition is met."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        editor._last_edit_time = time.monotonic()  # Recent edit
        editor._last_autosave_time = time.monotonic() - EditorConstants.AUTOSAVE_BACKSTOP_SECONDS - 1

        with patch('pagemark.editor.write_swap_file', return_value=True) as mock_write:
            editor._maybe_autosave()
            mock_write.assert_called_once()

    def test_autosave_updates_last_autosave_time(self, clean_session):
        """Test successful autosave updates _last_autosave_time."""
        editor = Editor()
        editor.modified = True
        editor.filename = "test.txt"
        editor._last_edit_time = time.monotonic() - 100
        editor._last_autosave_time = None

        with patch('pagemark.editor.write_swap_file', return_value=True):
            editor._maybe_autosave()
            assert editor._last_autosave_time is not None


class TestSaveFileSwapCleanup:
    """Tests for swap file cleanup on save."""

    def test_save_deletes_swap_file(self, clean_session):
        """Test that save_file deletes the swap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")

            editor = Editor()
            editor.filename = filename
            editor.modified = True
            editor.model.paragraphs = ["Test content"]

            # Create a swap file first
            write_swap_file(filename, "swap content")
            assert swap_file_exists(filename)

            # Save the file
            editor.save_file(filename)

            # Swap file should be deleted
            assert not swap_file_exists(filename)

    def test_save_resets_autosave_time(self, clean_session):
        """Test that save_file resets _last_autosave_time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.txt")

            editor = Editor()
            editor.filename = filename
            editor.modified = True
            editor.model.paragraphs = ["Test content"]
            editor._last_autosave_time = time.monotonic()

            editor.save_file(filename)

            assert editor._last_autosave_time is None


class TestLoadFromContent:
    """Tests for Editor.load_from_content method."""

    def test_load_from_content_sets_filename(self, clean_session):
        """Test load_from_content sets the filename."""
        editor = Editor()

        editor.load_from_content("test.txt", "content")

        assert editor.filename == "test.txt"

    def test_load_from_content_sets_modified(self, clean_session):
        """Test load_from_content marks document as modified."""
        editor = Editor()

        editor.load_from_content("test.txt", "content")

        assert editor.modified is True

    def test_load_from_content_parses_overstrike(self, clean_session):
        """Test load_from_content parses overstrike content."""
        editor = Editor()

        # Overstrike bold: H\bH e\be l\bl l\bl o\bo
        bold_content = "H\bHe\bel\bll\blo\bo"
        editor.load_from_content("test.txt", bold_content)

        assert editor.model.paragraphs[0] == "Hello"
