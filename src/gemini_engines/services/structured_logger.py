"""
Structured JSON Logging Service for Gemini MCP Server
Provides enterprise-grade observability with structured log output
"""
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict, field

from ..config import config


class LogLevel(Enum):
    """Structured log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(Enum):
    """Event types for categorizing log entries"""
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    TOOL_EXECUTION = "tool_execution"
    FILE_VALIDATION = "file_validation"
    STALE_ANALYSIS = "stale_analysis"
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    ERROR_OCCURRED = "error_occurred"
    PERFORMANCE_METRIC = "performance_metric"
    SECURITY_EVENT = "security_event"
    CACHE_OPERATION = "cache_operation"


@dataclass
class LogContext:
    """Context information for structured logs"""
    session_id: Optional[str] = None
    tool_name: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    file_paths: List[str] = field(default_factory=list)
    model_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations"""
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cache_hits: Optional[int] = None
    cache_misses: Optional[int] = None
    files_processed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredLogger:
    """Structured JSON logger with context awareness"""
    
    def __init__(self, name: str = __name__):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(config.log_level_value)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create structured JSON handler
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
    
    def _create_structured_log(self,
                             level: LogLevel,
                             message: str,
                             event_type: EventType,
                             context: Optional[LogContext] = None,
                             details: Optional[Dict[str, Any]] = None,
                             performance: Optional[PerformanceMetrics] = None,
                             exception: Optional[Exception] = None) -> Dict[str, Any]:
        """Create structured log entry"""
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.value,
            "message": message,
            "event_type": event_type.value,
            "service": "gemini-mcp-server",
            "version": "1.0.0"
        }
        
        # Add context if provided
        if context:
            log_entry["context"] = context.to_dict()
        
        # Add details if provided
        if details:
            log_entry["details"] = details
        
        # Add performance metrics if provided
        if performance:
            log_entry["performance"] = performance.to_dict()
        
        # Add exception information if provided
        if exception:
            log_entry["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc()
            }
        
        return log_entry
    
    def info(self,
             message: str,
             event_type: EventType = EventType.SYSTEM_START,
             context: Optional[LogContext] = None,
             details: Optional[Dict[str, Any]] = None,
             performance: Optional[PerformanceMetrics] = None):
        """Log info level message"""
        log_entry = self._create_structured_log(
            LogLevel.INFO, message, event_type, context, details, performance
        )
        self.logger.info(json.dumps(log_entry))
    
    def warning(self,
                message: str,
                event_type: EventType = EventType.ERROR_OCCURRED,
                context: Optional[LogContext] = None,
                details: Optional[Dict[str, Any]] = None,
                performance: Optional[PerformanceMetrics] = None):
        """Log warning level message"""
        log_entry = self._create_structured_log(
            LogLevel.WARNING, message, event_type, context, details, performance
        )
        self.logger.warning(json.dumps(log_entry))
    
    def error(self,
              message: str,
              event_type: EventType = EventType.ERROR_OCCURRED,
              context: Optional[LogContext] = None,
              details: Optional[Dict[str, Any]] = None,
              exception: Optional[Exception] = None):
        """Log error level message"""
        log_entry = self._create_structured_log(
            LogLevel.ERROR, message, event_type, context, details, exception=exception
        )
        self.logger.error(json.dumps(log_entry))
    
    def debug(self,
              message: str,
              event_type: EventType = EventType.SYSTEM_START,
              context: Optional[LogContext] = None,
              details: Optional[Dict[str, Any]] = None):
        """Log debug level message"""
        log_entry = self._create_structured_log(
            LogLevel.DEBUG, message, event_type, context, details
        )
        self.logger.debug(json.dumps(log_entry))
    
    def critical(self,
                 message: str,
                 event_type: EventType = EventType.ERROR_OCCURRED,
                 context: Optional[LogContext] = None,
                 details: Optional[Dict[str, Any]] = None,
                 exception: Optional[Exception] = None):
        """Log critical level message"""
        log_entry = self._create_structured_log(
            LogLevel.CRITICAL, message, event_type, context, details, exception=exception
        )
        self.logger.critical(json.dumps(log_entry))
    
    # Specialized logging methods for common events
    
    def log_tool_execution(self,
                          tool_name: str,
                          session_id: str,
                          duration_ms: float,
                          success: bool,
                          file_paths: List[str] = None,
                          error: Optional[Exception] = None):
        """Log tool execution with performance metrics"""
        context = LogContext(
            session_id=session_id,
            tool_name=tool_name,
            file_paths=file_paths or []
        )
        
        performance = PerformanceMetrics(
            duration_ms=duration_ms,
            files_processed=len(file_paths) if file_paths else 0
        )
        
        details = {"success": success}
        
        if success:
            self.info(
                f"Tool {tool_name} executed successfully",
                EventType.TOOL_EXECUTION,
                context,
                details,
                performance
            )
        else:
            self.error(
                f"Tool {tool_name} execution failed",
                EventType.TOOL_EXECUTION,
                context,
                details,
                error
            )
    
    def log_file_validation(self,
                           session_id: str,
                           validated_files: int,
                           missing_files: int,
                           filtered_files: int,
                           validation_time_ms: float,
                           has_critical_issues: bool):
        """Log file validation results"""
        context = LogContext(session_id=session_id)
        
        performance = PerformanceMetrics(
            duration_ms=validation_time_ms,
            files_processed=validated_files + missing_files + filtered_files
        )
        
        details = {
            "validated_files": validated_files,
            "missing_files": missing_files,
            "filtered_files": filtered_files,
            "has_critical_issues": has_critical_issues
        }
        
        level = EventType.ERROR_OCCURRED if has_critical_issues else EventType.FILE_VALIDATION
        
        self.info(
            f"File validation completed: {validated_files} valid, {missing_files} missing",
            level,
            context,
            details,
            performance
        )
    
    def log_stale_analysis(self,
                          session_id: str,
                          tool_name: str,
                          stale_files: List[str],
                          confidence_score: float,
                          action_taken: str):
        """Log stale analysis detection"""
        context = LogContext(
            session_id=session_id,
            tool_name=tool_name
        )
        
        details = {
            "stale_files": stale_files,
            "confidence_score": confidence_score,
            "action_taken": action_taken,
            "stale_file_count": len(stale_files)
        }
        
        self.warning(
            f"Stale analysis detected in {tool_name}",
            EventType.STALE_ANALYSIS,
            context,
            details
        )
    
    def log_api_request(self,
                       model: str,
                       session_id: str,
                       request_size_chars: int,
                       timeout_seconds: int):
        """Log API request"""
        context = LogContext(
            session_id=session_id,
            model_used=model
        )
        
        details = {
            "request_size_chars": request_size_chars,
            "timeout_seconds": timeout_seconds
        }
        
        self.debug(
            f"API request sent to {model}",
            EventType.API_REQUEST,
            context,
            details
        )
    
    def log_api_response(self,
                        model: str,
                        session_id: str,
                        response_size_chars: int,
                        duration_ms: float,
                        success: bool,
                        error: Optional[Exception] = None):
        """Log API response"""
        context = LogContext(
            session_id=session_id,
            model_used=model
        )
        
        performance = PerformanceMetrics(duration_ms=duration_ms)
        
        details = {
            "response_size_chars": response_size_chars,
            "success": success
        }
        
        if success:
            self.info(
                f"API response received from {model}",
                EventType.API_RESPONSE,
                context,
                details,
                performance
            )
        else:
            self.error(
                f"API request to {model} failed",
                EventType.API_RESPONSE,
                context,
                details,
                error
            )
    
    def log_cache_operation(self,
                           operation: str,
                           file_path: str,
                           cache_hit: bool,
                           duration_ms: float):
        """Log cache operations"""
        details = {
            "operation": operation,
            "file_path": file_path,
            "cache_hit": cache_hit
        }
        
        performance = PerformanceMetrics(
            duration_ms=duration_ms,
            cache_hits=1 if cache_hit else 0,
            cache_misses=0 if cache_hit else 1
        )
        
        self.debug(
            f"Cache {operation}: {'HIT' if cache_hit else 'MISS'} for {file_path}",
            EventType.CACHE_OPERATION,
            details=details,
            performance=performance
        )


class StructuredFormatter(logging.Formatter):
    """Custom formatter that ensures JSON output is properly formatted"""
    
    def format(self, record):
        # If the message is already JSON, return as-is
        if hasattr(record, 'message') and record.message.startswith('{'):
            return record.message
        
        # Otherwise, create a basic structured log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "gemini-mcp-server",
            "logger": record.name
        }
        
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_entry)


# Global structured logger instance
structured_logger = StructuredLogger("gemini-mcp-server")


def get_logger(name: str = None) -> StructuredLogger:
    """Get a structured logger instance"""
    if name:
        return StructuredLogger(name)
    return structured_logger