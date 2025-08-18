"""
Unit tests for path normalization utilities
Tests the critical path handling that fixes WindowsPath iteration errors
"""
import pytest
import tempfile
import os
from pathlib import Path, WindowsPath
from unittest.mock import patch, MagicMock

# Import the functions to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from utils.path_utils import normalize_paths, normalize_single_path, safe_path_iteration


class TestNormalizePaths:
    """Test the main normalize_paths function"""
    
    def test_normalize_paths_with_none(self):
        """Test that None input returns empty list"""
        result = normalize_paths(None)
        assert result == []
    
    def test_normalize_paths_with_empty_list(self):
        """Test that empty list returns empty list"""
        result = normalize_paths([])
        assert result == []
    
    def test_normalize_paths_with_string_path(self):
        """Test single string path normalization"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            tmp_path = tmp.name
        
        try:
            result = normalize_paths(tmp_path)
            assert len(result) == 1
            assert os.path.isabs(result[0])  # Should be absolute path
            assert os.path.exists(result[0])
        finally:
            os.unlink(tmp_path)
    
    def test_normalize_paths_with_path_object(self):
        """Test single Path object normalization"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            tmp_path = Path(tmp.name)
        
        try:
            result = normalize_paths(tmp_path)
            assert len(result) == 1
            assert os.path.isabs(result[0])  # Should be absolute path
            assert os.path.exists(result[0])
        finally:
            os.unlink(str(tmp_path))
    
    @pytest.mark.skipif(os.name != 'nt', reason="WindowsPath only available on Windows")
    def test_normalize_paths_with_windows_path_object(self):
        """Test WindowsPath object normalization (critical fix)"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            # Create WindowsPath object
            windows_path = WindowsPath(tmp.name)
        
        try:
            result = normalize_paths(windows_path)
            assert len(result) == 1
            assert isinstance(result[0], str)  # Should be string, not WindowsPath
            assert os.path.isabs(result[0])  # Should be absolute path
            assert os.path.exists(result[0])
        finally:
            os.unlink(tmp.name)
    
    def test_normalize_paths_with_list_of_strings(self):
        """Test list of string paths normalization"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test files
            file1 = os.path.join(tmp_dir, 'file1.py')
            file2 = os.path.join(tmp_dir, 'file2.py')
            with open(file1, 'w') as f:
                f.write('# test file 1')
            with open(file2, 'w') as f:
                f.write('# test file 2')
            
            result = normalize_paths([file1, file2])
            assert len(result) == 2
            assert all(os.path.isabs(path) for path in result)
            assert all(os.path.exists(path) for path in result)
    
    def test_normalize_paths_with_mixed_list(self):
        """Test list with mixed Path objects and strings"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test files
            file1 = os.path.join(tmp_dir, 'file1.py')
            file2 = os.path.join(tmp_dir, 'file2.py')
            with open(file1, 'w') as f:
                f.write('# test file 1')
            with open(file2, 'w') as f:
                f.write('# test file 2')
            
            # Mix string and Path object
            mixed_paths = [file1, Path(file2)]
            result = normalize_paths(mixed_paths)
            assert len(result) == 2
            assert all(isinstance(path, str) for path in result)
            assert all(os.path.isabs(path) for path in result)
    
    def test_normalize_paths_with_directory(self):
        """Test directory path normalization finds files"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test files
            py_file = os.path.join(tmp_dir, 'test.py')
            js_file = os.path.join(tmp_dir, 'test.js')
            with open(py_file, 'w') as f:
                f.write('# test python file')
            with open(js_file, 'w') as f:
                f.write('// test javascript file')
            
            result = normalize_paths(tmp_dir)
            assert len(result) >= 2  # Should find both files
            assert all(os.path.isabs(path) for path in result)
            assert any('test.py' in path for path in result)
            assert any('test.js' in path for path in result)
    
    def test_normalize_paths_with_nonexistent_path(self):
        """Test handling of non-existent paths"""
        nonexistent = "/path/that/does/not/exist.py"
        result = normalize_paths(nonexistent)
        assert len(result) == 1
        assert result[0] == str(Path(nonexistent).resolve())  # Should still return absolute path


class TestNormalizeSinglePath:
    """Test the normalize_single_path helper function"""
    
    def test_unknown_type_handling(self):
        """Test handling of unknown path types"""
        weird_input = {"not": "a path"}
        result = normalize_single_path(weird_input)
        assert len(result) == 1
        assert "not" in result[0] or "path" in result[0]  # Should convert to string
    
    def test_relative_path_becomes_absolute(self):
        """Test that relative paths become absolute"""
        # Use current directory as relative path
        result = normalize_single_path(".")
        assert len(result) >= 1  # Should find files in current directory
        assert all(os.path.isabs(path) for path in result)


class TestSafePathIteration:
    """Test the safe_path_iteration utility"""
    
    def test_safe_iteration_with_windows_path(self):
        """Test that WindowsPath objects can be safely iterated"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            if os.name == 'nt':
                windows_path = WindowsPath(tmp.name)
                paths_input = windows_path
            else:
                # On non-Windows, simulate the issue
                paths_input = Path(tmp.name)
        
        try:
            # This should not raise "WindowsPath object is not iterable"
            for file_path in safe_path_iteration(paths_input):
                assert isinstance(file_path, str)
                assert os.path.isabs(file_path)
        finally:
            os.unlink(tmp.name)


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @patch('utils.path_utils.logger')
    def test_logging_for_nonexistent_paths(self, mock_logger):
        """Test that warnings are logged for non-existent paths"""
        normalize_paths("/definitely/does/not/exist")
        mock_logger.warning.assert_called()
    
    @patch('utils.path_utils.logger')
    def test_logging_for_unknown_types(self, mock_logger):
        """Test that warnings are logged for unknown types"""
        normalize_single_path(123)  # Number instead of path
        mock_logger.warning.assert_called()
    
    def test_empty_directory_handling(self):
        """Test handling of empty directories"""
        with tempfile.TemporaryDirectory() as empty_dir:
            result = normalize_paths(empty_dir)
            # Should return the directory path itself if no files found
            assert len(result) == 1
            assert os.path.isabs(result[0])


class TestRegressionPrevention:
    """Tests specifically for preventing the original WindowsPath bug"""
    
    def test_windowspath_iteration_bug_prevention(self):
        """
        Regression test for the original "WindowsPath object is not iterable" bug
        This test ensures the fix prevents the exact error that was causing crashes
        """
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            
            if os.name == 'nt':
                # Create the exact scenario that caused the original bug
                windows_path_obj = WindowsPath(tmp.name)
            else:
                # Simulate on non-Windows systems
                windows_path_obj = Path(tmp.name)
        
        try:
            # This was the operation that failed before the fix
            normalized = normalize_paths(windows_path_obj)
            
            # Ensure we can iterate over the result (this would fail before)
            for path in normalized:
                assert isinstance(path, str)  # Should be string, not Path object
                
            # Ensure the result is not the original object type
            assert not any(isinstance(path, Path) for path in normalized)
            
        finally:
            os.unlink(tmp.name)
    
    def test_mixed_path_types_no_errors(self):
        """
        Test that mixing different path types doesn't cause iteration errors
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file1 = os.path.join(tmp_dir, 'file1.py')
            with open(file1, 'w') as f:
                f.write('test')
            
            # Mix of different path representations
            mixed_input = [
                file1,                    # string
                Path(file1),             # Path object
                tmp_dir,                 # directory string
                Path(tmp_dir)            # directory Path object
            ]
            
            # This should not raise any iteration errors
            result = normalize_paths(mixed_input)
            
            # All results should be strings
            assert all(isinstance(path, str) for path in result)
            # All results should be absolute paths
            assert all(os.path.isabs(path) for path in result)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])