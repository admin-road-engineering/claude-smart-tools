"""
Request correlation system for distributed debugging
Provides trace_id context throughout the request lifecycle
"""
import logging
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime

# Context variable for trace ID - automatically propagated across async calls
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

logger = logging.getLogger(__name__)

class TraceContext:
    """Manages request correlation and tracing throughout the system"""
    
    @staticmethod
    def generate_trace_id() -> str:
        """Generate a unique trace ID for request correlation"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"trace_{timestamp}_{unique_id}"
    
    @staticmethod
    def set_trace_id(trace_id: str) -> str:
        """Set trace ID for current context"""
        _trace_id.set(trace_id)
        logger.debug(f"Trace context set: {trace_id}")
        return trace_id
    
    @staticmethod
    def get_trace_id() -> Optional[str]:
        """Get current trace ID"""
        return _trace_id.get()
    
    @staticmethod
    def ensure_trace_id() -> str:
        """Get existing trace ID or generate new one"""
        trace_id = TraceContext.get_trace_id()
        if not trace_id:
            trace_id = TraceContext.generate_trace_id()
            TraceContext.set_trace_id(trace_id)
        return trace_id
    
    @staticmethod
    def create_context_dict(additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a context dictionary with trace ID and optional additional data"""
        context = {
            'trace_id': TraceContext.get_trace_id(),
            'timestamp': datetime.now().isoformat()
        }
        
        if additional_data:
            context.update(additional_data)
            
        return context

class TracedLogger:
    """Logger wrapper that automatically includes trace ID in log messages"""
    
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
    
    def _log_with_trace(self, level: int, msg: str, *args, **kwargs):
        """Internal method to log with trace context"""
        trace_id = TraceContext.get_trace_id()
        if trace_id:
            # Add trace_id to extra fields for structured logging
            extra = kwargs.get('extra', {})
            extra['trace_id'] = trace_id
            kwargs['extra'] = extra
            
            # Prefix message with trace ID for easy visual scanning
            msg = f"[{trace_id}] {msg}"
        
        self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log_with_trace(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log_with_trace(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log_with_trace(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log_with_trace(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log_with_trace(logging.CRITICAL, msg, *args, **kwargs)

def trace_request(func):
    """Decorator to automatically set up trace context for a request"""
    async def wrapper(*args, **kwargs):
        # Generate trace ID if not already present
        trace_id = TraceContext.ensure_trace_id()
        
        traced_logger = TracedLogger(func.__module__)
        traced_logger.info(f"Starting request: {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            traced_logger.info(f"Request completed successfully: {func.__name__}")
            return result
        except Exception as e:
            traced_logger.error(f"Request failed: {func.__name__} - {str(e)}")
            raise
    
    return wrapper

# Convenience function for getting traced logger
def get_traced_logger(name: str) -> TracedLogger:
    """Get a traced logger for the given name"""
    return TracedLogger(name)