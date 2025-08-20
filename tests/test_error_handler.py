"""
Comprehensive test suite for error_handler.py module
Tests error categorization, severity assignment, message generation, and suggestion accuracy
"""
import unittest
from unittest.mock import patch, Mock, MagicMock
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.error_handler import (
    ErrorCategory, ErrorSeverity, SmartToolError, 
    ErrorHandler, get_error_handler, handle_smart_tool_error
)


class TestErrorCategory(unittest.TestCase):
    """Test ErrorCategory enum"""
    
    def test_error_categories_exist(self):
        """Test that all expected error categories are defined"""
        expected_categories = [
            'USER_ERROR', 'API_ERROR', 'SYSTEM_ERROR', 
            'NETWORK_ERROR', 'CONFIGURATION_ERROR', 
            'ENGINE_ERROR', 'UNKNOWN_ERROR'
        ]
        for category in expected_categories:
            self.assertTrue(hasattr(ErrorCategory, category))
    
    def test_error_category_values(self):
        """Test error category string values"""
        self.assertEqual(ErrorCategory.USER_ERROR.value, "user_error")
        self.assertEqual(ErrorCategory.API_ERROR.value, "api_error")
        self.assertEqual(ErrorCategory.SYSTEM_ERROR.value, "system_error")


class TestErrorSeverity(unittest.TestCase):
    """Test ErrorSeverity enum"""
    
    def test_severity_levels_exist(self):
        """Test that all severity levels are defined"""
        expected_severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        for severity in expected_severities:
            self.assertTrue(hasattr(ErrorSeverity, severity))
    
    def test_severity_values(self):
        """Test severity string values"""
        self.assertEqual(ErrorSeverity.LOW.value, "low")
        self.assertEqual(ErrorSeverity.MEDIUM.value, "medium")
        self.assertEqual(ErrorSeverity.HIGH.value, "high")
        self.assertEqual(ErrorSeverity.CRITICAL.value, "critical")


class TestSmartToolError(unittest.TestCase):
    """Test SmartToolError class"""
    
    def test_error_creation(self):
        """Test creating a SmartToolError instance"""
        error = SmartToolError(
            category=ErrorCategory.API_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message="Test error message",
            original_exception=ValueError("Original error"),
            context={"engine": "test_engine"},
            suggestions=["Try again", "Check configuration"]
        )
        
        self.assertEqual(error.category, ErrorCategory.API_ERROR)
        self.assertEqual(error.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(error.message, "Test error message")
        self.assertIsNotNone(error.original_exception)
        self.assertEqual(error.context["engine"], "test_engine")
        self.assertEqual(len(error.suggestions), 2)
        self.assertIsNotNone(error.traceback)
    
    def test_error_to_dict(self):
        """Test converting error to dictionary"""
        error = SmartToolError(
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.HIGH,
            message="File not found"
        )
        
        error_dict = error.to_dict()
        
        self.assertEqual(error_dict['category'], 'user_error')
        self.assertEqual(error_dict['severity'], 'high')
        self.assertEqual(error_dict['message'], 'File not found')
        self.assertIsNone(error_dict['original_error'])
    
    def test_get_user_message(self):
        """Test user-friendly message generation"""
        error = SmartToolError(
            category=ErrorCategory.API_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message="API rate limit exceeded",
            suggestions=["Wait 5 minutes", "Use different API key"]
        )
        
        user_message = error.get_user_message()
        
        self.assertIn("⚠️", user_message)  # Medium severity emoji
        self.assertIn("API rate limit exceeded", user_message)
        self.assertIn("Wait 5 minutes", user_message)
        self.assertIn("Use different API key", user_message)
    
    def test_severity_emoji_mapping(self):
        """Test correct emoji assignment for severity levels"""
        test_cases = [
            (ErrorSeverity.LOW, "ℹ️"),
            (ErrorSeverity.MEDIUM, "⚠️"),
            (ErrorSeverity.HIGH, "❌"),
            (ErrorSeverity.CRITICAL, "🚨")
        ]
        
        for severity, expected_emoji in test_cases:
            error = SmartToolError(
                category=ErrorCategory.UNKNOWN_ERROR,
                severity=severity,
                message="Test"
            )
            self.assertIn(expected_emoji, error.get_user_message())


class TestErrorHandler(unittest.TestCase):
    """Test ErrorHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.handler = ErrorHandler()
    
    def test_categorize_api_errors(self):
        """Test categorization of API-related errors"""
        test_cases = [
            ("Rate limited by API", ErrorCategory.API_ERROR),
            ("Request exhausted quota", ErrorCategory.API_ERROR),
            ("429 Too Many Requests", ErrorCategory.API_ERROR),
            ("Invalid API key provided", ErrorCategory.API_ERROR),
            ("Authentication failed", ErrorCategory.API_ERROR),
            ("401 Unauthorized", ErrorCategory.API_ERROR),
            ("Service unavailable 503", ErrorCategory.API_ERROR),
        ]
        
        for error_msg, expected_category in test_cases:
            exception = Exception(error_msg)
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(category, expected_category, 
                           f"Failed for: {error_msg}")
    
    def test_categorize_user_errors(self):
        """Test categorization of user input errors"""
        test_cases = [
            ("No files found in directory", ErrorCategory.USER_ERROR),
            ("File not found: test.py", ErrorCategory.USER_ERROR),
            ("Path does not exist", ErrorCategory.USER_ERROR),
            ("Invalid parameter provided", ErrorCategory.USER_ERROR),
            ("Missing required field", ErrorCategory.USER_ERROR),
            ("Permission denied", ErrorCategory.USER_ERROR),
        ]
        
        for error_msg, expected_category in test_cases:
            exception = Exception(error_msg)
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(category, expected_category,
                           f"Failed for: {error_msg}")
    
    def test_categorize_system_errors(self):
        """Test categorization of system errors"""
        test_cases = [
            ("Out of memory error", ErrorCategory.SYSTEM_ERROR),
            ("Disk space full", ErrorCategory.SYSTEM_ERROR),
            ("File write error occurred", ErrorCategory.SYSTEM_ERROR),
            ("I/O error reading file", ErrorCategory.SYSTEM_ERROR),
            ("Process execution error", ErrorCategory.SYSTEM_ERROR),
        ]
        
        for error_msg, expected_category in test_cases:
            exception = Exception(error_msg)
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(category, expected_category,
                           f"Failed for: {error_msg}")
    
    def test_categorize_network_errors(self):
        """Test categorization of network errors"""
        test_cases = [
            ("Connection timeout", ErrorCategory.NETWORK_ERROR),
            ("Network error occurred", ErrorCategory.NETWORK_ERROR),
            ("Host unreachable", ErrorCategory.NETWORK_ERROR),
            ("DNS resolution error", ErrorCategory.NETWORK_ERROR),
            ("Socket error", ErrorCategory.NETWORK_ERROR),
        ]
        
        for error_msg, expected_category in test_cases:
            exception = Exception(error_msg)
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(category, expected_category,
                           f"Failed for: {error_msg}")
    
    def test_categorize_by_exception_type(self):
        """Test categorization based on exception type"""
        test_cases = [
            (FileNotFoundError("test"), ErrorCategory.USER_ERROR),
            (PermissionError("test"), ErrorCategory.USER_ERROR),
            (ConnectionError("test"), ErrorCategory.NETWORK_ERROR),
            (TimeoutError("test"), ErrorCategory.NETWORK_ERROR),
            (MemoryError("test"), ErrorCategory.SYSTEM_ERROR),
            (ValueError("test"), ErrorCategory.UNKNOWN_ERROR),
        ]
        
        for exception, expected_category in test_cases:
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(category, expected_category,
                           f"Failed for: {type(exception).__name__}")
    
    def test_severity_determination(self):
        """Test severity level assignment"""
        # Test critical patterns
        critical_errors = [
            "Critical system failure",
            "Fatal error occurred",
            "Emergency shutdown",
            "System panic"
        ]
        
        for error_msg in critical_errors:
            exception = Exception(error_msg)
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(severity, ErrorSeverity.CRITICAL,
                           f"Failed for: {error_msg}")
        
        # Test category-based severity
        test_cases = [
            (Exception("API rate limited"), ErrorSeverity.MEDIUM),
            (Exception("File not found"), ErrorSeverity.MEDIUM),
            (Exception("Memory error"), ErrorSeverity.HIGH),
            (Exception("Network timeout"), ErrorSeverity.HIGH),
        ]
        
        for exception, expected_severity in test_cases:
            category, severity = self.handler.categorize_error(exception)
            self.assertEqual(severity, expected_severity,
                           f"Failed for: {str(exception)}")
    
    def test_handle_exception(self):
        """Test complete exception handling flow"""
        exception = Exception("Rate limited by API")
        context = {"operation": "test_op", "engine": "test_engine"}
        
        with patch.object(self.handler, '_log_error') as mock_log:
            smart_error = self.handler.handle_exception(
                exception, context, "test_engine"
            )
        
        # Verify error properties
        self.assertEqual(smart_error.category, ErrorCategory.API_ERROR)
        self.assertEqual(smart_error.severity, ErrorSeverity.MEDIUM)
        self.assertIn("Rate limit reached", smart_error.message)
        self.assertEqual(smart_error.context["engine"], "test_engine")
        self.assertEqual(smart_error.context["error_id"], 1)
        self.assertGreater(len(smart_error.suggestions), 0)
        
        # Verify logging was called
        mock_log.assert_called_once_with(smart_error)
        
        # Verify error added to history
        self.assertEqual(len(self.handler.error_history), 1)
        self.assertEqual(self.handler.error_count, 1)
    
    def test_error_history_limit(self):
        """Test that error history is limited to 50 entries"""
        # Create 60 errors
        for i in range(60):
            exception = Exception(f"Error {i}")
            self.handler.handle_exception(exception)
        
        # Verify only last 50 are kept
        self.assertEqual(len(self.handler.error_history), 50)
        self.assertEqual(self.handler.error_count, 60)
        
        # Verify oldest errors were removed
        error_messages = [e.message for e in self.handler.error_history]
        self.assertIn("Error 59", error_messages[-1])
        self.assertNotIn("Error 0", error_messages[0])
    
    def test_message_and_suggestions_generation(self):
        """Test message and suggestion generation for different error types"""
        test_cases = [
            (
                Exception("Rate limited"),
                ErrorCategory.API_ERROR,
                "Rate limit reached",
                ["Wait a few minutes", "Consider using a different API key"]
            ),
            (
                Exception("API key invalid"),
                ErrorCategory.API_ERROR,
                "API authentication failed",
                ["Verify your API key", "Check that the API key has necessary permissions"]
            ),
            (
                Exception("No files found"),
                ErrorCategory.USER_ERROR,
                "No valid files found",
                ["Check that the file paths are correct", "Ensure files exist"]
            ),
            (
                Exception("Permission denied"),
                ErrorCategory.USER_ERROR,
                "Permission denied",
                ["Check file and directory permissions", "Run with appropriate privileges"]
            ),
        ]
        
        for exception, category, expected_msg_part, expected_suggestions in test_cases:
            message, suggestions = self.handler._generate_message_and_suggestions(
                exception, category, None, "test_engine"
            )
            
            self.assertIn(expected_msg_part, message)
            for suggestion in expected_suggestions:
                self.assertTrue(
                    any(suggestion in s for s in suggestions),
                    f"Expected suggestion '{suggestion}' not found in {suggestions}"
                )
    
    def test_logging_with_severity(self):
        """Test that errors are logged with appropriate levels"""
        test_cases = [
            (ErrorSeverity.LOW, logging.INFO),
            (ErrorSeverity.MEDIUM, logging.WARNING),
            (ErrorSeverity.HIGH, logging.ERROR),
            (ErrorSeverity.CRITICAL, logging.CRITICAL),
        ]
        
        for severity, expected_level in test_cases:
            error = SmartToolError(
                category=ErrorCategory.API_ERROR,
                severity=severity,
                message="Test error",
                context={"engine": "test"}
            )
            
            with patch('src.utils.error_handler.logger.log') as mock_log:
                self.handler._log_error(error)
                mock_log.assert_called_once()
                actual_level = mock_log.call_args[0][0]
                self.assertEqual(actual_level, expected_level)
    
    def test_get_error_summary(self):
        """Test error summary generation"""
        # Create errors of different types
        self.handler.handle_exception(Exception("API rate limited"))
        self.handler.handle_exception(FileNotFoundError("test.py"))
        self.handler.handle_exception(ConnectionError("timeout"))
        
        summary = self.handler.get_error_summary()
        
        self.assertEqual(summary["total_errors"], 3)
        self.assertEqual(summary["recent_errors"], 3)
        self.assertIn("api_error", summary["category_counts"])
        self.assertIn("user_error", summary["category_counts"])
        self.assertIn("network_error", summary["category_counts"])
        self.assertIsNotNone(summary["last_error"])
    
    def test_global_error_handler(self):
        """Test global error handler singleton"""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        # Should be the same instance
        self.assertIs(handler1, handler2)
    
    def test_handle_smart_tool_error_convenience_function(self):
        """Test the convenience function for error handling"""
        exception = Exception("Test error")
        context = {"test": "context"}
        
        with patch.object(ErrorHandler, 'handle_exception') as mock_handle:
            mock_error = Mock()
            mock_error.get_user_message.return_value = "User friendly message"
            mock_handle.return_value = mock_error
            
            result = handle_smart_tool_error(exception, context, "engine_name")
            
            self.assertEqual(result, "User friendly message")
            mock_handle.assert_called_once_with(exception, context, "engine_name")
    
    def test_case_insensitive_pattern_matching(self):
        """Test that error categorization is case-insensitive"""
        test_cases = [
            "RATE LIMITED",
            "Rate Limited",
            "rate limited",
            "RaTe LiMiTeD"
        ]
        
        for error_msg in test_cases:
            exception = Exception(error_msg)
            category, _ = self.handler.categorize_error(exception)
            self.assertEqual(category, ErrorCategory.API_ERROR,
                           f"Failed for: {error_msg}")


if __name__ == '__main__':
    unittest.main()