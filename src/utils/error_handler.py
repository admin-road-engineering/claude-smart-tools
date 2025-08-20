"""
Standardized error handling framework for Smart Tools
Provides consistent error categorization, formatting, and reporting
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import traceback
import re

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Standardized error categories for consistent handling"""
    USER_ERROR = "user_error"          # User input issues (paths, parameters)
    API_ERROR = "api_error"            # External API issues (rate limits, auth)
    SYSTEM_ERROR = "system_error"      # Internal system issues (file I/O, memory)
    NETWORK_ERROR = "network_error"    # Network connectivity issues
    CONFIGURATION_ERROR = "config_error"  # Configuration issues
    ENGINE_ERROR = "engine_error"      # Engine-specific errors
    UNKNOWN_ERROR = "unknown_error"    # Unclassified errors


class ErrorSeverity(Enum):
    """Error severity levels for appropriate handling"""
    LOW = "low"          # Non-critical, operation can continue
    MEDIUM = "medium"    # Important, affects functionality
    HIGH = "high"        # Critical, blocks operation
    CRITICAL = "critical"  # System-level failure


class SmartToolError:
    """Structured error representation for Smart Tools"""
    
    def __init__(self, 
                 category: ErrorCategory,
                 severity: ErrorSeverity,
                 message: str,
                 original_exception: Optional[Exception] = None,
                 context: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[List[str]] = None):
        self.category = category
        self.severity = severity
        self.message = message
        self.original_exception = original_exception
        self.context = context or {}
        self.suggestions = suggestions or []
        
        # Add traceback if available
        if original_exception:
            self.traceback = traceback.format_exception(
                type(original_exception), 
                original_exception, 
                original_exception.__traceback__
            )
        else:
            self.traceback = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            'category': self.category.value,
            'severity': self.severity.value,
            'message': self.message,
            'context': self.context,
            'suggestions': self.suggestions,
            'original_error': str(self.original_exception) if self.original_exception else None,
            'traceback': self.traceback
        }
    
    def get_user_message(self) -> str:
        """Get user-friendly error message with suggestions"""
        base_message = f"{self._get_severity_emoji()} {self.message}"
        
        if self.suggestions:
            suggestions_text = "\n".join([f"  • {suggestion}" for suggestion in self.suggestions])
            base_message += f"\n\nSuggestions:\n{suggestions_text}"
        
        return base_message
    
    def _get_severity_emoji(self) -> str:
        """Get emoji representation of severity"""
        emoji_map = {
            ErrorSeverity.LOW: "ℹ️",
            ErrorSeverity.MEDIUM: "⚠️",
            ErrorSeverity.HIGH: "❌",
            ErrorSeverity.CRITICAL: "🚨"
        }
        return emoji_map.get(self.severity, "❓")


class ErrorHandler:
    """Centralized error handling for Smart Tools"""
    
    # Error pattern mappings for automatic categorization
    ERROR_PATTERNS = {
        # API Errors
        ErrorCategory.API_ERROR: [
            r"rate limited|exhausted|quota|429|too many requests",
            r"api key|authentication|unauthorized|401|403",
            r"service unavailable|502|503|504|gateway timeout"
        ],
        
        # User Errors  
        ErrorCategory.USER_ERROR: [
            r"no files found|no code files|file not found|path does not exist",
            r"invalid parameter|invalid input|missing required",
            r"permission denied|access denied"
        ],
        
        # System Errors
        ErrorCategory.SYSTEM_ERROR: [
            r"memory error|out of memory|disk space|storage full",
            r"file.*error|i/o error|read.*error|write.*error",
            r"process.*error|subprocess.*error"
        ],
        
        # Network Errors
        ErrorCategory.NETWORK_ERROR: [
            r"connection.*error|network.*error|timeout|unreachable",
            r"dns.*error|host.*error|socket.*error"
        ],
        
        # Configuration Errors
        ErrorCategory.CONFIGURATION_ERROR: [
            r"configuration.*error|config.*error|missing.*config",
            r"environment.*error|setting.*error"
        ]
    }
    
    def __init__(self):
        self.error_count = 0
        self.error_history: List[SmartToolError] = []
    
    def categorize_error(self, exception: Exception) -> Tuple[ErrorCategory, ErrorSeverity]:
        """
        Automatically categorize an exception based on its message and type
        """
        error_msg = str(exception).lower()
        
        # Check patterns for each category
        for category, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_msg, re.IGNORECASE):
                    # Determine severity based on category and specific patterns
                    severity = self._determine_severity(category, error_msg, exception)
                    return category, severity
        
        # Default categorization based on exception type
        if isinstance(exception, (FileNotFoundError, PermissionError)):
            return ErrorCategory.USER_ERROR, ErrorSeverity.MEDIUM
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK_ERROR, ErrorSeverity.HIGH
        elif isinstance(exception, MemoryError):
            return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL
        else:
            return ErrorCategory.UNKNOWN_ERROR, ErrorSeverity.MEDIUM
    
    def _determine_severity(self, category: ErrorCategory, error_msg: str, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on category and context"""
        
        # Critical patterns regardless of category
        if any(pattern in error_msg for pattern in ["critical", "fatal", "emergency", "panic"]):
            return ErrorSeverity.CRITICAL
        
        # Category-specific severity mapping
        severity_map = {
            ErrorCategory.API_ERROR: ErrorSeverity.MEDIUM,  # Usually retryable
            ErrorCategory.USER_ERROR: ErrorSeverity.MEDIUM,  # User can fix
            ErrorCategory.SYSTEM_ERROR: ErrorSeverity.HIGH,  # System issue
            ErrorCategory.NETWORK_ERROR: ErrorSeverity.HIGH,  # Blocks operation
            ErrorCategory.CONFIGURATION_ERROR: ErrorSeverity.HIGH,  # Needs admin
            ErrorCategory.ENGINE_ERROR: ErrorSeverity.MEDIUM,  # Engine-specific
            ErrorCategory.UNKNOWN_ERROR: ErrorSeverity.MEDIUM  # Default
        }
        
        return severity_map.get(category, ErrorSeverity.MEDIUM)
    
    def handle_exception(self, 
                        exception: Exception, 
                        context: Optional[Dict[str, Any]] = None,
                        engine_name: Optional[str] = None) -> SmartToolError:
        """
        Handle an exception and return a structured error
        """
        self.error_count += 1
        
        # Categorize the error
        category, severity = self.categorize_error(exception)
        
        # Generate user-friendly message and suggestions
        message, suggestions = self._generate_message_and_suggestions(
            exception, category, context, engine_name
        )
        
        # Add context information
        error_context = context or {}
        if engine_name:
            error_context['engine'] = engine_name
        error_context['error_id'] = self.error_count
        
        # Create structured error
        smart_error = SmartToolError(
            category=category,
            severity=severity,
            message=message,
            original_exception=exception,
            context=error_context,
            suggestions=suggestions
        )
        
        # Log the error
        self._log_error(smart_error)
        
        # Store in history (keep last 50 errors)
        self.error_history.append(smart_error)
        if len(self.error_history) > 50:
            self.error_history.pop(0)
        
        return smart_error
    
    def _generate_message_and_suggestions(self, 
                                        exception: Exception, 
                                        category: ErrorCategory,
                                        context: Optional[Dict[str, Any]] = None,
                                        engine_name: Optional[str] = None) -> Tuple[str, List[str]]:
        """Generate user-friendly message and actionable suggestions"""
        
        error_msg = str(exception).lower()
        suggestions = []
        
        if category == ErrorCategory.API_ERROR:
            if "rate limited" in error_msg or "exhausted" in error_msg:
                message = "Rate limit reached. The API has usage limits."
                suggestions = [
                    "Wait a few minutes before retrying",
                    "Consider using a different API key if available",
                    "Reduce the number of concurrent requests"
                ]
            elif "api key" in error_msg or "authentication" in error_msg:
                message = "API authentication failed. Check your API configuration."
                suggestions = [
                    "Verify your API key is correct and active",
                    "Check that the API key has necessary permissions",
                    "Ensure the API key environment variable is set"
                ]
            else:
                message = f"API error occurred in {engine_name or 'engine'}"
                suggestions = ["Check API service status", "Retry the operation"]
                
        elif category == ErrorCategory.USER_ERROR:
            if "no files found" in error_msg or "file not found" in error_msg:
                message = "No valid files found at the specified paths."
                suggestions = [
                    "Check that the file paths are correct",
                    "Ensure files exist and are accessible",
                    "Verify you have permission to read the files"
                ]
            elif "permission denied" in error_msg:
                message = "Permission denied accessing the requested resources."
                suggestions = [
                    "Check file and directory permissions",
                    "Run with appropriate privileges if needed",
                    "Ensure paths are accessible from current location"
                ]
            else:
                message = "Invalid input or configuration provided."
                suggestions = ["Check your input parameters", "Review the documentation"]
                
        elif category == ErrorCategory.SYSTEM_ERROR:
            message = "System resource error occurred."
            suggestions = [
                "Check available disk space and memory",
                "Close other applications if needed",
                "Try with smaller input sets"
            ]
            
        elif category == ErrorCategory.NETWORK_ERROR:
            message = "Network connectivity issue detected."
            suggestions = [
                "Check your internet connection",
                "Verify firewall and proxy settings", 
                "Retry the operation in a moment"
            ]
            
        else:
            # Default/unknown error
            original_msg = str(exception)
            message = f"An error occurred in {engine_name or 'the system'}: {original_msg[:100]}"
            suggestions = ["Check the logs for more details", "Try the operation again"]
        
        return message, suggestions
    
    def _log_error(self, smart_error: SmartToolError):
        """Log the error with appropriate level"""
        
        log_level_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        
        log_level = log_level_map.get(smart_error.severity, logging.ERROR)
        
        # Create log message
        log_msg = f"[{smart_error.category.value.upper()}] {smart_error.message}"
        if smart_error.context.get('engine'):
            log_msg = f"Engine '{smart_error.context['engine']}': {log_msg}"
        
        # Log with appropriate level
        logger.log(log_level, log_msg)
        
        # Log traceback for high severity errors
        if smart_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] and smart_error.traceback:
            logger.error("Traceback: %s", ''.join(smart_error.traceback))
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors for debugging"""
        if not self.error_history:
            return {"total_errors": 0, "recent_errors": []}
        
        # Count by category
        category_counts = {}
        severity_counts = {}
        
        for error in self.error_history[-10:]:  # Last 10 errors
            category = error.category.value
            severity = error.severity.value
            
            category_counts[category] = category_counts.get(category, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_errors": self.error_count,
            "recent_errors": len(self.error_history),
            "category_counts": category_counts,
            "severity_counts": severity_counts,
            "last_error": self.error_history[-1].to_dict() if self.error_history else None
        }


# Global error handler instance
_global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance"""
    return _global_error_handler


def handle_smart_tool_error(exception: Exception, 
                           context: Optional[Dict[str, Any]] = None,
                           engine_name: Optional[str] = None) -> str:
    """
    Convenience function to handle an exception and return user-friendly message
    
    Args:
        exception: The exception to handle
        context: Additional context information
        engine_name: Name of the engine where error occurred
        
    Returns:
        User-friendly error message string
    """
    error_handler = get_error_handler()
    smart_error = error_handler.handle_exception(exception, context, engine_name)
    return smart_error.get_user_message()