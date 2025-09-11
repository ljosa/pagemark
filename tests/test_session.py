"""Unit tests for session management."""

import unittest
from pagemark.session import SessionManager, SessionKeys, get_session


class TestSessionManager(unittest.TestCase):
    """Test session management functionality."""
    
    def setUp(self):
        """Clear session before each test."""
        get_session().clear()
        
    def test_singleton_pattern(self):
        """Test that SessionManager is a singleton."""
        session1 = SessionManager()
        session2 = SessionManager()
        session3 = get_session()
        
        self.assertIs(session1, session2)
        self.assertIs(session2, session3)
        
    def test_set_and_get(self):
        """Test setting and getting session values."""
        session = get_session()
        
        session.set("test_key", "test_value")
        self.assertEqual(session.get("test_key"), "test_value")
        
        session.set("test_int", 42)
        self.assertEqual(session.get("test_int"), 42)
        
    def test_get_with_default(self):
        """Test getting with default value."""
        session = get_session()
        
        # Non-existent key should return default
        self.assertEqual(session.get("nonexistent", "default"), "default")
        
        # Existing key should return value, not default
        session.set("existing", "value")
        self.assertEqual(session.get("existing", "default"), "value")
        
    def test_clear(self):
        """Test clearing all session data."""
        session = get_session()
        
        session.set("key1", "value1")
        session.set("key2", "value2")
        
        session.clear()
        
        self.assertIsNone(session.get("key1"))
        self.assertIsNone(session.get("key2"))
        
    def test_clear_key(self):
        """Test clearing specific key."""
        session = get_session()
        
        session.set("key1", "value1")
        session.set("key2", "value2")
        
        session.clear_key("key1")
        
        self.assertIsNone(session.get("key1"))
        self.assertEqual(session.get("key2"), "value2")
        
    def test_state_property(self):
        """Test getting copy of state."""
        session = get_session()
        
        session.set("key1", "value1")
        session.set("key2", "value2")
        
        state = session.state
        
        # Should be a copy
        state["key3"] = "value3"
        self.assertIsNone(session.get("key3"))
        
        # Should contain the right values
        self.assertEqual(state["key1"], "value1")
        self.assertEqual(state["key2"], "value2")
        
    def test_session_keys_constants(self):
        """Test that SessionKeys constants are defined."""
        self.assertIsInstance(SessionKeys.FONT_NAME, str)
        self.assertIsInstance(SessionKeys.DOUBLE_SPACING, str)
        self.assertIsInstance(SessionKeys.LINE_LENGTH, str)
        self.assertIsInstance(SessionKeys.LAST_SAVE_PATH, str)
        
    def test_persistence_across_instances(self):
        """Test that data persists across different access points."""
        session1 = get_session()
        session1.set("persistent", "data")
        
        session2 = SessionManager()
        self.assertEqual(session2.get("persistent"), "data")
        
    def test_font_settings_workflow(self):
        """Test typical font settings workflow."""
        session = get_session()
        
        # Simulate print dialog saving font settings
        session.set(SessionKeys.FONT_NAME, "Prestige Elite Std")
        session.set(SessionKeys.LINE_LENGTH, 72)
        session.set(SessionKeys.DOUBLE_SPACING, True)
        
        # Simulate editor reading settings
        font = session.get(SessionKeys.FONT_NAME, "Courier")
        length = session.get(SessionKeys.LINE_LENGTH, 65)
        spacing = session.get(SessionKeys.DOUBLE_SPACING, False)
        
        self.assertEqual(font, "Prestige Elite Std")
        self.assertEqual(length, 72)
        self.assertTrue(spacing)


if __name__ == '__main__':
    unittest.main()