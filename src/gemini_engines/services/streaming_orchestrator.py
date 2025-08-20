"""
Streaming orchestrator for large response handling
Prevents memory exhaustion and terminal freezes with generous limits
"""
import asyncio
import psutil
import gc
from typing import AsyncGenerator, Dict, Any, Optional, Union
from datetime import datetime

from ..services.trace_context import get_traced_logger
from ..services.cpu_throttler import CPUThrottler
from ..exceptions import (
    StreamingError, 
    MemoryLimitExceededError, 
    AtomicPayloadTooLargeError,
    CircuitBreakerOpenError
)

logger = get_traced_logger(__name__)

class StreamingOrchestrator:
    """Orchestrates streaming of large responses with memory management"""
    
    def __init__(self, config):
        self.config = config
        
        # Generous limits - user-friendly defaults
        self.max_response_size_kb = getattr(config, 'max_response_size_kb', 1500)  # 1.5MB (from config)
        self.memory_limit_mb = getattr(config, 'memory_limit_mb', 2000)  # 2GB (from config)
        self.max_chunk_size_kb = getattr(config, 'max_chunk_size_kb', 200)  # 200KB chunks (from config)
        self.enable_streaming = getattr(config, 'enable_streaming_responses', True)
        self.enable_large_response_mode = getattr(config, 'enable_large_response_mode', True)
        
        # CPU throttling
        self.cpu_throttler = CPUThrottler(config)
        
        # Circuit breaker state
        self._circuit_breaker_open = False
        self._circuit_breaker_reset_time = None
        self._failure_count = 0
        self._failure_threshold = 3
        self._circuit_breaker_timeout = 60  # seconds
        
        logger.info(f"Streaming orchestrator initialized - Response limit: {self.max_response_size_kb}KB, "
                   f"Memory limit: {self.memory_limit_mb}MB, Chunk size: {self.max_chunk_size_kb}KB")
    
    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert bytes to MB
        except Exception as e:
            logger.warning(f"Could not get memory usage: {e}")
            return 0.0
    
    def _check_circuit_breaker(self):
        """Check circuit breaker state"""
        if self._circuit_breaker_open:
            if datetime.now().timestamp() > self._circuit_breaker_reset_time:
                # Reset circuit breaker
                self._circuit_breaker_open = False
                self._failure_count = 0
                logger.info("Circuit breaker reset - ready to process requests")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker open - retry after {self._circuit_breaker_reset_time - datetime.now().timestamp():.0f}s"
                )
    
    def _open_circuit_breaker(self):
        """Open circuit breaker after failures"""
        self._circuit_breaker_open = True
        self._circuit_breaker_reset_time = datetime.now().timestamp() + self._circuit_breaker_timeout
        logger.error(f"Circuit breaker opened - blocking requests for {self._circuit_breaker_timeout}s")
    
    def _is_atomic_payload(self, content: str, content_type: str = "text") -> bool:
        """Determine if payload should be treated as atomic (not chunked)"""
        # File Freshness Guardian reports and other structured data
        atomic_indicators = [
            '"validation_report"',
            '"stale_reference_report"', 
            '"file_validation_errors"',
            '"validation_results"',
            '{"files":',
            '{"error_code":',
            '{"suggestions":'
        ]
        
        # JSON-like structured responses should remain atomic
        if content_type == "json" or any(indicator in content.lower() for indicator in atomic_indicators):
            logger.debug("Payload detected as atomic - will not chunk")
            return True
        
        return False
    
    def _estimate_response_size(self, content: str) -> int:
        """Estimate response size in KB"""
        return len(content.encode('utf-8')) // 1024
    
    async def _check_memory_limits(self, estimated_size_kb: int):
        """Check if processing would exceed memory limits"""
        current_memory_mb = self._get_memory_usage_mb()
        estimated_additional_mb = estimated_size_kb / 1024
        
        projected_memory_mb = current_memory_mb + estimated_additional_mb
        
        if projected_memory_mb > self.memory_limit_mb:
            logger.warning(f"Memory limit check: Current {current_memory_mb:.1f}MB + "
                         f"Estimated {estimated_additional_mb:.1f}MB = {projected_memory_mb:.1f}MB "
                         f"exceeds limit of {self.memory_limit_mb}MB")
            
            # Force garbage collection before failing
            gc.collect()
            
            # Re-check after garbage collection
            current_memory_mb = self._get_memory_usage_mb()
            projected_memory_mb = current_memory_mb + estimated_additional_mb
            
            if projected_memory_mb > self.memory_limit_mb:
                raise MemoryLimitExceededError(
                    f"Processing would exceed memory limit: {projected_memory_mb:.1f}MB > {self.memory_limit_mb}MB",
                    current_memory=current_memory_mb,
                    estimated_additional=estimated_additional_mb,
                    limit=self.memory_limit_mb
                )
    
    async def stream_response(self, content: str, content_type: str = "text", 
                            metadata: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """
        Stream response content in chunks, with intelligent atomic payload detection
        
        Args:
            content: Response content to stream
            content_type: Type of content (text, json, etc.)
            metadata: Optional metadata about the response
        
        Yields:
            Response chunks
        """
        try:
            # Check circuit breaker
            self._check_circuit_breaker()
            
            estimated_size_kb = self._estimate_response_size(content)
            
            logger.info(f"Streaming response: {estimated_size_kb}KB content")
            
            # Check memory limits
            await self._check_memory_limits(estimated_size_kb)
            
            # Handle atomic payloads
            if self._is_atomic_payload(content, content_type):
                if estimated_size_kb > self.max_response_size_kb:
                    # Atomic payload too large - provide graceful error
                    error_msg = (
                        f"Structured data response ({estimated_size_kb}KB) exceeds safe limit "
                        f"({self.max_response_size_kb}KB) and cannot be chunked. "
                        f"Consider using summary mode or increasing MAX_RESPONSE_SIZE_KB."
                    )
                    raise AtomicPayloadTooLargeError(error_msg, size_kb=estimated_size_kb)
                else:
                    # Small enough atomic payload - yield as single chunk
                    logger.debug(f"Yielding atomic payload: {estimated_size_kb}KB")
                    yield content
                    return
            
            # Handle streamable content
            if not self.enable_streaming or estimated_size_kb <= self.max_response_size_kb:
                # Small enough or streaming disabled - yield as single chunk
                logger.debug(f"Yielding single chunk: {estimated_size_kb}KB")
                yield content
                return
            
            # Large content - stream in chunks
            if not self.enable_large_response_mode:
                # Large response mode disabled - provide truncated content
                truncate_chars = self.max_response_size_kb * 1024
                truncated_content = content[:truncate_chars]
                yield truncated_content
                yield f"\n\n--- Content Truncated ---\nResponse was {estimated_size_kb}KB, truncated to {self.max_response_size_kb}KB. Enable ENABLE_LARGE_RESPONSE_MODE=true for full content streaming."
                return
            
            # Stream large content in chunks with CPU throttling
            chunk_size_chars = self.max_chunk_size_kb * 1024
            total_chunks = (len(content) + chunk_size_chars - 1) // chunk_size_chars
            
            logger.info(f"Streaming large response in {total_chunks} chunks of {self.max_chunk_size_kb}KB")
            
            async with self.cpu_throttler.monitor_heavy_operation("response_streaming"):
                for i in range(0, len(content), chunk_size_chars):
                    chunk = content[i:i + chunk_size_chars]
                    chunk_number = (i // chunk_size_chars) + 1
                    
                    # Add chunk headers for user clarity
                    if chunk_number == 1:
                        chunk_header = f"📄 Streaming Response ({total_chunks} chunks, {estimated_size_kb}KB total)\n\n"
                        chunk = chunk_header + chunk
                    elif chunk_number == total_chunks:
                        chunk = chunk + f"\n\n--- End of Stream (chunk {chunk_number}/{total_chunks}) ---"
                    
                    yield chunk
                    
                    # CPU-aware yielding - replaces fixed 0.01s sleep
                    await self.cpu_throttler.yield_if_needed()
                    
                    # Check memory during streaming
                    current_memory_mb = self._get_memory_usage_mb()
                    if current_memory_mb > self.memory_limit_mb * 0.9:  # 90% threshold
                        logger.warning(f"Memory usage high during streaming: {current_memory_mb:.1f}MB")
                        gc.collect()
                        # Extra yield after garbage collection
                        await self.cpu_throttler.yield_control()
            
            logger.info(f"Streaming completed: {total_chunks} chunks, {estimated_size_kb}KB")
            
            # Reset failure count on success
            if self._failure_count > 0:
                self._failure_count = 0
                logger.debug("Reset failure count after successful streaming")
                
        except Exception as e:
            self._failure_count += 1
            logger.error(f"Streaming failed (failure {self._failure_count}): {str(e)}")
            
            if self._failure_count >= self._failure_threshold:
                self._open_circuit_breaker()
            
            # Provide graceful error response
            error_response = f"""⚠️ Streaming Error

An error occurred while streaming the response:
{str(e)}

This may be due to:
- Memory limitations (current limit: {self.memory_limit_mb}MB)
- Response size constraints (current limit: {self.max_response_size_kb}KB)
- System resource exhaustion

**Suggestions:**
- Try with a smaller request or summary mode
- Increase memory limits via MEMORY_LIMIT_MB environment variable
- Check system memory availability

**Technical Details:**
- Error Type: {type(e).__name__}
- Estimated Response Size: {estimated_size_kb}KB
- Current Memory Usage: {self._get_memory_usage_mb():.1f}MB
"""
            yield error_response
            raise StreamingError(f"Failed to stream response: {str(e)}") from e
    
    async def process_response(self, content: str, content_type: str = "text", 
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Process response - either stream or return directly based on size and type
        
        For non-streaming contexts, this returns the full content or raises appropriate errors
        """
        try:
            estimated_size_kb = self._estimate_response_size(content)
            
            # Check memory limits
            await self._check_memory_limits(estimated_size_kb)
            
            # Handle atomic payloads
            if self._is_atomic_payload(content, content_type):
                if estimated_size_kb > self.max_response_size_kb:
                    raise AtomicPayloadTooLargeError(
                        f"Structured data response ({estimated_size_kb}KB) exceeds limit ({self.max_response_size_kb}KB)",
                        size_kb=estimated_size_kb
                    )
                return content
            
            # Handle large non-atomic content
            if estimated_size_kb > self.max_response_size_kb:
                if not self.enable_large_response_mode:
                    # Truncate
                    truncate_chars = self.max_response_size_kb * 1024
                    truncated_content = content[:truncate_chars]
                    return truncated_content + f"\n\n--- Content Truncated ---\nEnable ENABLE_LARGE_RESPONSE_MODE=true for full content."
                else:
                    # For non-streaming context, we still return full content but log warning
                    logger.warning(f"Large response processed non-streaming: {estimated_size_kb}KB")
                    return content
            
            return content
            
        except Exception as e:
            logger.error(f"Response processing failed: {str(e)}")
            raise