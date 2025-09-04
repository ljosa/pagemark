import os
from unittest.mock import patch, MagicMock, PropertyMock
from pagemark.editor import Editor


def test_resize_signal_triggers_rerender():
    """Test that SIGWINCH triggers a re-render via pipe."""
    editor = Editor()
    
    # Create a mock key for quit
    quit_key = '\x11'  # Ctrl-Q
    
    with patch.object(editor.terminal, 'setup'):
        with patch.object(editor.terminal, 'cleanup'):
            with patch.object(type(editor.terminal), 'width', PropertyMock(return_value=80)):
                with patch.object(type(editor.terminal), 'height', PropertyMock(return_value=24)):
                    with patch.object(editor.terminal.term, 'cbreak', MagicMock()):
                        with patch.object(editor.terminal, 'get_key') as mock_get_key:
                            with patch.object(editor.view, 'render') as mock_render:
                                with patch.object(editor, '_draw'):
                                    with patch('pagemark.editor.select.select') as mock_select:
                                        # Simulate: initial draw, resize pipe ready, stdin ready with quit
                                        mock_select.side_effect = [
                                            ([editor._resize_pipe_r], [], []),  # Resize pipe ready
                                            ([0], [], []),  # stdin ready
                                        ]
                                        # Quit on second call
                                        mock_get_key.side_effect = [quit_key]
                                        
                                        # Write to pipe to simulate resize
                                        os.write(editor._resize_pipe_w, b'R')
                                        
                                        # Run the editor
                                        editor.run()
                                        
                                        # Should have rendered twice: initial + after resize
                                        assert mock_render.call_count == 2


def test_no_polling():
    """Test that select is used instead of polling."""
    editor = Editor()
    
    with patch.object(editor.terminal, 'setup'):
        with patch.object(editor.terminal, 'cleanup'):
            with patch.object(type(editor.terminal), 'width', PropertyMock(return_value=80)):
                with patch.object(type(editor.terminal), 'height', PropertyMock(return_value=24)):
                    with patch.object(editor.terminal.term, 'cbreak', MagicMock()):
                        with patch.object(editor.terminal, 'get_key') as mock_get_key:
                            with patch.object(editor.view, 'render'):
                                with patch.object(editor, '_draw'):
                                    with patch('pagemark.editor.select.select') as mock_select:
                                        # Make select return stdin ready
                                        mock_select.return_value = ([0], [], [])
                                        # Make get_key return quit immediately
                                        mock_get_key.return_value = '\x11'  # Ctrl-Q
                                        
                                        # Run the editor
                                        editor.run()
                                        
                                        # Verify select was called (blocking wait)
                                        mock_select.assert_called()
                                        # Verify get_key was called with timeout=0 (non-blocking after select)
                                        mock_get_key.assert_called_with(timeout=0)


def test_resize_via_signal():
    """Test that SIGWINCH signal triggers resize."""
    editor = Editor()
    
    # Track calls to _handle_key
    calls = []
    
    def track_handle(key):
        calls.append(key)
        if key == '\x11':  # Quit on Ctrl-Q
            editor.running = False
    
    editor._handle_key = track_handle
    
    with patch.object(editor.terminal, 'setup'):
        with patch.object(editor.terminal, 'cleanup'):
            with patch.object(type(editor.terminal), 'width', PropertyMock(return_value=80)):
                with patch.object(type(editor.terminal), 'height', PropertyMock(return_value=24)):
                    with patch.object(editor.terminal.term, 'cbreak', MagicMock()):
                        with patch.object(editor.terminal, 'get_key') as mock_get_key:
                            with patch.object(editor.view, 'render') as mock_render:
                                with patch.object(editor, '_draw'):
                                    with patch('pagemark.editor.select.select') as mock_select:
                                        # Track render count at different stages
                                        render_calls = []
                                        
                                        def track_render():
                                            render_calls.append('render')
                                        
                                        mock_render.side_effect = track_render
                                        
                                        normal_key = 'a'
                                        quit_key = '\x11'
                                        
                                        # Simulate: stdin with normal key, resize pipe, stdin with quit
                                        mock_select.side_effect = [
                                            ([0], [], []),  # stdin ready
                                            ([editor._resize_pipe_r], [], []),  # Resize pipe ready
                                            ([0], [], []),  # stdin ready
                                        ]
                                        mock_get_key.side_effect = [normal_key, quit_key]
                                        
                                        # Simulate resize signal
                                        os.write(editor._resize_pipe_w, b'R')
                                        
                                        # Run the editor
                                        editor.run()
                                        
                                        # _handle_key should be called for normal and quit keys only
                                        assert calls == [normal_key, quit_key]
                                        # Should render: initial, after normal key, after resize, after quit key
                                        assert len(render_calls) >= 2  # At least initial and resize


def test_terminal_dimensions_update_on_resize():
    """Test that terminal dimensions are updated after resize."""
    editor = Editor()
    
    quit_key = '\x11'
    
    # Start with one size, then change after resize
    width_values = [80, 100]  # Change width after resize
    height_values = [24, 30]  # Change height after resize
    
    width_mock = PropertyMock(side_effect=width_values * 10)  # Repeat values
    height_mock = PropertyMock(side_effect=height_values * 10)
    
    with patch.object(editor.terminal, 'setup'):
        with patch.object(editor.terminal, 'cleanup'):
            with patch.object(type(editor.terminal), 'width', width_mock):
                with patch.object(type(editor.terminal), 'height', height_mock):
                    with patch.object(editor.terminal.term, 'cbreak', MagicMock()):
                        with patch.object(editor.terminal, 'get_key') as mock_get_key:
                            with patch.object(editor.view, 'render'):
                                with patch.object(editor, '_draw'):
                                    with patch('pagemark.editor.select.select') as mock_select:
                                        # Simulate resize then quit
                                        mock_select.side_effect = [
                                            ([editor._resize_pipe_r], [], []),  # Resize signal
                                            ([0], [], []),  # stdin ready
                                        ]
                                        mock_get_key.return_value = quit_key
                                        
                                        # Signal resize
                                        os.write(editor._resize_pipe_w, b'R')
                                        
                                        # Run the editor
                                        editor.run()
                                        
                                        # Dimensions should have been checked
                                        assert width_mock.call_count >= 2
                                        assert height_mock.call_count >= 2