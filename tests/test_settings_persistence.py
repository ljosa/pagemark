"""Unit tests for settings persistence."""

import unittest
import tempfile
import os
from pathlib import Path

from pagemark.settings_persistence import SettingsPersistence, get_persistence
from pagemark.session import SessionManager, SessionKeys, get_session


class TestSettingsPersistence(unittest.TestCase):
    """Test settings persistence functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test settings
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a new SettingsPersistence instance with custom path
        self.persistence = SettingsPersistence()
        self.persistence._config_dir = Path(self.temp_dir)
        self.persistence._settings_file = self.persistence._config_dir / "test_settings.json"
        self.persistence._settings_cache = None
        
        # Create a test document path
        self.test_doc_path = os.path.join(self.temp_dir, "test_document.txt")
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_settings(self):
        """Test saving and loading settings for a document."""
        settings = {
            "font_name": "Courier",
            "double_spacing": True,
            "line_length": 65,
        }
        
        # Save settings
        success = self.persistence.save_settings(self.test_doc_path, settings)
        self.assertTrue(success)
        
        # Load settings
        loaded = self.persistence.load_settings(self.test_doc_path)
        self.assertEqual(loaded, settings)
    
    def test_load_nonexistent_document(self):
        """Test loading settings for a document with no saved settings."""
        loaded = self.persistence.load_settings("/nonexistent/document.txt")
        self.assertEqual(loaded, {})
    
    def test_save_with_none_document_path(self):
        """Test that saving with None document path returns False."""
        settings = {"font_name": "Courier"}
        success = self.persistence.save_settings(None, settings)
        self.assertFalse(success)
    
    def test_load_with_none_document_path(self):
        """Test that loading with None document path returns empty dict."""
        loaded = self.persistence.load_settings(None)
        self.assertEqual(loaded, {})
    
    def test_update_settings(self):
        """Test updating settings for a document."""
        # Save initial settings
        initial_settings = {"font_name": "Courier"}
        self.persistence.save_settings(self.test_doc_path, initial_settings)
        
        # Update settings
        updated_settings = {
            "font_name": "Prestige Elite Std",
            "double_spacing": True,
        }
        self.persistence.save_settings(self.test_doc_path, updated_settings)
        
        # Load and verify
        loaded = self.persistence.load_settings(self.test_doc_path)
        self.assertEqual(loaded, updated_settings)
    
    def test_multiple_documents(self):
        """Test settings for multiple documents."""
        doc1_path = os.path.join(self.temp_dir, "doc1.txt")
        doc2_path = os.path.join(self.temp_dir, "doc2.txt")
        
        settings1 = {"font_name": "Courier", "line_length": 65}
        settings2 = {"font_name": "Prestige Elite Std", "line_length": 72}
        
        # Save settings for both documents
        self.persistence.save_settings(doc1_path, settings1)
        self.persistence.save_settings(doc2_path, settings2)
        
        # Load and verify
        loaded1 = self.persistence.load_settings(doc1_path)
        loaded2 = self.persistence.load_settings(doc2_path)
        
        self.assertEqual(loaded1, settings1)
        self.assertEqual(loaded2, settings2)
    
    def test_validate_string_settings(self):
        """Test validation of string settings."""
        # Valid string settings
        self.assertTrue(self.persistence.validate_setting("font_name", "Courier"))
        self.assertTrue(self.persistence.validate_setting("printer_name", "HP_LaserJet"))
        self.assertTrue(self.persistence.validate_setting("pdf_filename", "output.pdf"))
        
        # Invalid (non-string) settings
        self.assertFalse(self.persistence.validate_setting("font_name", 123))
        self.assertFalse(self.persistence.validate_setting("printer_name", True))
    
    def test_validate_boolean_settings(self):
        """Test validation of boolean settings."""
        # Valid boolean settings
        self.assertTrue(self.persistence.validate_setting("double_spacing", True))
        self.assertTrue(self.persistence.validate_setting("duplex_printing", False))
        
        # Invalid (non-boolean) settings
        self.assertFalse(self.persistence.validate_setting("double_spacing", "yes"))
        self.assertFalse(self.persistence.validate_setting("duplex_printing", 1))
    
    def test_validate_integer_settings(self):
        """Test validation of integer settings."""
        # Valid line lengths
        self.assertTrue(self.persistence.validate_setting("line_length", 65))
        self.assertTrue(self.persistence.validate_setting("line_length", 72))
        self.assertTrue(self.persistence.validate_setting("line_length", 40))
        self.assertTrue(self.persistence.validate_setting("line_length", 120))
        
        # Invalid line lengths (out of range)
        self.assertFalse(self.persistence.validate_setting("line_length", 30))
        self.assertFalse(self.persistence.validate_setting("line_length", 150))
        
        # Invalid (non-integer)
        self.assertFalse(self.persistence.validate_setting("line_length", "65"))
    
    def test_validate_none_value(self):
        """Test that None is valid for any setting."""
        self.assertTrue(self.persistence.validate_setting("font_name", None))
        self.assertTrue(self.persistence.validate_setting("double_spacing", None))
        self.assertTrue(self.persistence.validate_setting("line_length", None))
    
    def test_validate_with_available_options(self):
        """Test validation with available options list."""
        available_printers = ["HP_LaserJet", "Canon_Printer", "PDF File"]
        
        # Valid printer from list
        self.assertTrue(
            self.persistence.validate_setting("printer_name", "HP_LaserJet", available_printers)
        )
        
        # Invalid printer (not in list)
        self.assertFalse(
            self.persistence.validate_setting("printer_name", "NonExistent", available_printers)
        )
    
    def test_clear_cache(self):
        """Test clearing the settings cache."""
        # Save and load settings to populate cache
        settings = {"font_name": "Courier"}
        self.persistence.save_settings(self.test_doc_path, settings)
        self.persistence.load_settings(self.test_doc_path)
        
        # Cache should be populated
        self.assertIsNotNone(self.persistence._settings_cache)
        
        # Clear cache
        self.persistence.clear_cache()
        self.assertIsNone(self.persistence._settings_cache)
    
    def test_atomic_write(self):
        """Test that settings are written atomically."""
        # This test verifies the temp file pattern is used
        settings = {"font_name": "Courier"}
        self.persistence.save_settings(self.test_doc_path, settings)
        
        # Temp file should not exist after save
        temp_file = self.persistence._settings_file.with_suffix('.tmp')
        self.assertFalse(temp_file.exists())
        
        # Settings file should exist
        self.assertTrue(self.persistence._settings_file.exists())


class TestSessionPersistenceIntegration(unittest.TestCase):
    """Test integration between SessionManager and SettingsPersistence."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test settings
        self.temp_dir = tempfile.mkdtemp()
        
        # Get session and disable persistence for setup
        self.session = get_session()
        self.session.clear()
        self.session.set_persistence_enabled(False)
        
        # Override the persistence instance with test-specific one
        from pagemark import settings_persistence
        self.old_persistence = settings_persistence._persistence
        test_persistence = SettingsPersistence()
        test_persistence._config_dir = Path(self.temp_dir)
        test_persistence._settings_file = test_persistence._config_dir / "test_settings.json"
        test_persistence._settings_cache = None
        settings_persistence._persistence = test_persistence
        
        # Create a test document path
        self.test_doc_path = os.path.join(self.temp_dir, "test_document.txt")
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original persistence instance
        from pagemark import settings_persistence
        settings_persistence._persistence = self.old_persistence
        
        # Clear session
        self.session.clear()
        self.session.set_persistence_enabled(True)
        
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_load_document_settings(self):
        """Test loading settings when a document is opened."""
        # Enable persistence for this test
        self.session.set_persistence_enabled(True)
        
        # Manually save some settings
        persistence = get_persistence()
        settings = {
            "print_font_name": "Prestige Elite Std",
            "double_spacing": True,
            "line_length": 72,
        }
        persistence.save_settings(self.test_doc_path, settings)
        
        # Load document settings into session
        self.session.load_document_settings(self.test_doc_path)
        
        # Verify settings were loaded
        self.assertEqual(self.session.get(SessionKeys.FONT_NAME), "Prestige Elite Std")
        self.assertEqual(self.session.get(SessionKeys.DOUBLE_SPACING), True)
        self.assertEqual(self.session.get(SessionKeys.LINE_LENGTH), 72)
    
    def test_save_on_set(self):
        """Test that settings are saved when changed."""
        # Enable persistence and load document
        self.session.set_persistence_enabled(True)
        self.session.load_document_settings(self.test_doc_path)
        
        # Change a setting
        self.session.set(SessionKeys.FONT_NAME, "Courier")
        
        # Verify it was saved to disk
        persistence = get_persistence()
        persistence.clear_cache()  # Clear cache to force reload from disk
        loaded = persistence.load_settings(self.test_doc_path)
        self.assertEqual(loaded.get("print_font_name"), "Courier")
    
    def test_persistence_disabled(self):
        """Test that settings are not saved when persistence is disabled."""
        # Disable persistence
        self.session.set_persistence_enabled(False)
        self.session.load_document_settings(self.test_doc_path)
        
        # Change a setting
        self.session.set(SessionKeys.FONT_NAME, "Courier")
        
        # Verify it was NOT saved to disk
        persistence = get_persistence()
        loaded = persistence.load_settings(self.test_doc_path)
        self.assertEqual(loaded, {})
    
    def test_only_persistable_keys_saved(self):
        """Test that only persistable keys are saved to disk."""
        # Enable persistence and load document
        self.session.set_persistence_enabled(True)
        self.session.load_document_settings(self.test_doc_path)
        
        # Set both persistable and non-persistable keys
        self.session.set(SessionKeys.FONT_NAME, "Courier")  # Persistable
        self.session.set(SessionKeys.LAST_SAVE_PATH, "/tmp/test.txt")  # Not persistable
        
        # Verify only persistable key was saved
        persistence = get_persistence()
        persistence.clear_cache()
        loaded = persistence.load_settings(self.test_doc_path)
        self.assertIn("print_font_name", loaded)
        self.assertNotIn("last_save_path", loaded)


if __name__ == '__main__':
    unittest.main()
