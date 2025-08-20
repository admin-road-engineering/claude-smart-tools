"""
Exception hierarchy for Gemini MCP server
"""

class GeminiMcpError(Exception):
    """Base exception for all MCP server errors"""
    pass


class SecurityError(GeminiMcpError):
    """Security-related errors including path traversal and access violations"""
    def __init__(self, message: str, error_code: str = None, suggestions: list = None, context: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.suggestions = suggestions or []
        self.context = context or {}

class PersistenceError(GeminiMcpError):
    """Database and session storage errors"""
    pass

class GeminiApiError(GeminiMcpError):
    """Gemini API client errors"""
    pass

class RateLimitError(GeminiApiError):
    """Rate limiting specific errors"""
    def __init__(self, message: str, model: str = None, retry_after: int = None):
        super().__init__(message)
        self.model = model
        self.retry_after = retry_after

class ComplexityError(GeminiMcpError):
    """Complexity assessment and model selection errors"""
    pass

class ConfigurationError(GeminiMcpError):
    """Configuration and setup errors"""
    pass

class ToolingError(GeminiMcpError):
    """Base class for tool execution errors"""
    def __init__(self, message: str, error_code: str = None, suggestions: list = None, context: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.suggestions = suggestions or []
        self.context = context or {}

class SearchError(ToolingError):
    """Search operation specific errors"""
    pass

class NoResultsFoundError(SearchError):
    """No search results found"""
    def __init__(self, query: str, files_checked: int = 0, suggestions: list = None, context: dict = None):
        message = f"No results found for query: '{query}'"
        super().__init__(
            message=message,
            error_code="NO_RESULTS_FOUND",
            suggestions=suggestions,
            context=context or {"query": query, "files_checked": files_checked}
        )
        self.query = query
        self.files_checked = files_checked

class InvalidQuerySyntaxError(SearchError):
    """Invalid query syntax"""
    def __init__(self, query: str, syntax_error: str, suggestions: list = None):
        message = f"Invalid query syntax: '{query}' - {syntax_error}"
        super().__init__(
            message=message,
            error_code="INVALID_QUERY_SYNTAX",
            suggestions=suggestions,
            context={"query": query, "syntax_error": syntax_error}
        )
        self.query = query
        self.syntax_error = syntax_error

class PathError(ToolingError):
    """Path resolution and access errors"""
    pass

class PathNotFoundError(PathError):
    """Specified path not found"""
    def __init__(self, path: str, suggestions: list = None):
        message = f"Path not found: '{path}'"
        super().__init__(
            message=message,
            error_code="PATH_NOT_FOUND",
            suggestions=suggestions,
            context={"path": path}
        )
        self.path = path

class PermissionError(PathError):
    """Permission denied accessing path"""
    def __init__(self, path: str, operation: str = "access"):
        message = f"Permission denied: Cannot {operation} '{path}'"
        suggestions = [
            "Run with elevated permissions if needed",
            "Check if the directory is protected",
            "Try a different directory"
        ]
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            suggestions=suggestions,
            context={"path": path, "operation": operation}
        )
        self.path = path
        self.operation = operation

class AnalysisError(ToolingError):
    """Code analysis specific errors"""
    pass

class TimeoutError(AnalysisError):
    """Analysis operation timed out"""
    def __init__(self, operation: str, timeout_seconds: int, suggestions: list = None):
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        super().__init__(
            message=message,
            error_code="OPERATION_TIMEOUT",
            suggestions=suggestions or [
                "Try with a smaller scope",
                "Use verbose=False for faster analysis", 
                "Check if the operation is still running"
            ],
            context={"operation": operation, "timeout_seconds": timeout_seconds}
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class FileStateError(ToolingError):
    """Base class for file state and freshness validation errors"""
    pass


class AnalysisBlockedError(FileStateError):
    """Analysis is blocked due to critical file validation issues"""
    def __init__(self, message: str, report, suggestions: list = None):
        """
        Initialize with full validation report for rich error handling
        
        Args:
            message: Human-readable error message
            report: ValidationReport with complete validation context
            suggestions: Optional list of actionable suggestions
        """
        super().__init__(
            message=message,
            error_code="ANALYSIS_BLOCKED",
            suggestions=suggestions or [
                "Check that file paths exist and are accessible",
                "Verify you're in the correct directory",
                "Ensure files haven't been moved or deleted"
            ],
            context={
                "validation_timestamp": report.timestamp.isoformat(),
                "verified_files_count": len(report.verified_files),
                "missing_paths_count": len(report.missing_paths),
                "filtered_files_count": len(report.filtered_files),
                "has_critical_issues": report.has_critical_issues,
                "validation_summary": report.validation_summary
            }
        )
        # Attach full report object for rich error formatting
        self.report = report


class StaleAnalysisDetectedError(FileStateError):
    """Analysis contains references to files that don't exist in current codebase"""
    def __init__(self, message: str, original_result: str, report, suggestions: list = None):
        """
        Initialize with full stale reference report for rich error handling
        
        Args:
            message: Human-readable error message
            original_result: The original analysis output containing stale references
            report: StaleReferenceReport with complete detection context
            suggestions: Optional list of actionable suggestions
        """
        super().__init__(
            message=message,
            error_code="STALE_ANALYSIS_DETECTED", 
            suggestions=suggestions or [
                "Re-run the analysis to get current results",
                "Clear any cached analysis data",
                "Verify you're analyzing the intended codebase version"
            ],
            context={
                "detection_timestamp": report.analysis_timestamp.isoformat(),
                "stale_files_count": len(report.stale_files_detected),
                "confidence_score": report.confidence_score,
                "actionable_recommendation": report.actionable_recommendation.name,
                "known_valid_files_count": len(report.known_valid_files)
            }
        )
        # Attach full objects for rich error formatting
        self.original_result = original_result
        self.report = report


class FileCacheError(FileStateError):
    """File cache related errors"""
    def __init__(self, message: str, file_path: str = None):
        super().__init__(
            message=message,
            error_code="FILE_CACHE_ERROR",
            suggestions=[
                "Clear the file cache and retry",
                "Check file permissions and accessibility",
                "Ensure sufficient disk space for caching"
            ],
            context={"file_path": file_path} if file_path else {}
        )
        self.file_path = file_path


# Resilience and Streaming Errors

class ResilienceError(GeminiMcpError):
    """Base class for resilience layer errors"""
    pass

class StreamingError(ResilienceError):
    """Streaming orchestrator errors"""
    pass

class MemoryLimitExceededError(StreamingError):
    """Memory usage exceeds configured limits"""
    def __init__(self, message: str, current_memory: float = None, 
                 estimated_additional: float = None, limit: float = None):
        super().__init__(message)
        self.current_memory = current_memory
        self.estimated_additional = estimated_additional
        self.limit = limit

class AtomicPayloadTooLargeError(StreamingError):
    """Atomic payload (structured data) exceeds size limits"""
    def __init__(self, message: str, size_kb: int = None):
        super().__init__(message)
        self.size_kb = size_kb

class CircuitBreakerOpenError(ResilienceError):
    """Circuit breaker is open, blocking requests"""
    def __init__(self, message: str, retry_after_seconds: float = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class SynthesisError(GeminiMcpError):
    """Errors during synthesis report generation"""
    def __init__(self, message: str, model_name: str = None, synthesis_data: dict = None):
        super().__init__(message)
        self.model_name = model_name
        self.synthesis_data = synthesis_data