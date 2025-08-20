"""
Resilient review service using composition pattern
Wraps existing ReviewService with streaming and circuit breaker protection
"""
import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator, Union
from datetime import datetime, timedelta

from ..services.review_service import ReviewService
from ..services.streaming_orchestrator import StreamingOrchestrator
from ..services.trace_context import get_traced_logger, TraceContext, trace_request
from ..models.review_request import ReviewRequest
from ..exceptions import (
    ResilienceError, 
    TimeoutError as CustomTimeoutError,
    CircuitBreakerOpenError,
    StreamingError
)

logger = get_traced_logger(__name__)

class ResilientReviewService:
    """
    Resilient wrapper around ReviewService using composition pattern
    
    Adds:
    - Request tracing
    - Multi-layer timeout protection  
    - Memory management via streaming
    - Circuit breaker protection
    - Graceful degradation
    """
    
    def __init__(self, core_review_service: ReviewService, 
                 streaming_orchestrator: StreamingOrchestrator, config):
        self.core_service = core_review_service
        self.orchestrator = streaming_orchestrator
        self.config = config
        
        # Timeout configuration - generous limits
        self.review_timeout_seconds = getattr(config, 'review_timeout_seconds', 180)  # 3 minutes
        self.max_concurrent_reviews = getattr(config, 'max_concurrent_reviews', 5)
        
        # Circuit breaker for the whole service
        self._circuit_breaker_open = False
        self._circuit_breaker_reset_time = None
        self._failure_count = 0
        self._failure_threshold = 5  # Higher threshold for service-level breaker
        self._circuit_breaker_timeout = 300  # 5 minutes
        
        # Concurrency tracking
        self._active_reviews = 0
        self._active_reviews_lock = asyncio.Lock()
        
        logger.info(f"Resilient review service initialized - Timeout: {self.review_timeout_seconds}s, "
                   f"Max concurrent: {self.max_concurrent_reviews}")
    
    def _check_service_circuit_breaker(self):
        """Check service-level circuit breaker"""
        if self._circuit_breaker_open:
            if datetime.now().timestamp() > self._circuit_breaker_reset_time:
                self._circuit_breaker_open = False
                self._failure_count = 0
                logger.info("Service circuit breaker reset")
            else:
                remaining_time = self._circuit_breaker_reset_time - datetime.now().timestamp()
                raise CircuitBreakerOpenError(
                    f"Review service circuit breaker open - retry in {remaining_time:.0f}s"
                )
    
    def _open_service_circuit_breaker(self):
        """Open service-level circuit breaker"""
        self._circuit_breaker_open = True
        self._circuit_breaker_reset_time = datetime.now().timestamp() + self._circuit_breaker_timeout
        logger.error(f"Service circuit breaker opened - blocking all reviews for {self._circuit_breaker_timeout}s")
    
    async def _acquire_review_slot(self):
        """Acquire a review slot (concurrency control)"""
        async with self._active_reviews_lock:
            if self._active_reviews >= self.max_concurrent_reviews:
                raise ResilienceError(
                    f"Maximum concurrent reviews reached ({self.max_concurrent_reviews}). "
                    f"Please wait for current reviews to complete."
                )
            self._active_reviews += 1
            logger.debug(f"Review slot acquired ({self._active_reviews}/{self.max_concurrent_reviews})")
    
    async def _release_review_slot(self):
        """Release a review slot"""
        async with self._active_reviews_lock:
            self._active_reviews = max(0, self._active_reviews - 1)
            logger.debug(f"Review slot released ({self._active_reviews}/{self.max_concurrent_reviews})")
    
    async def _execute_with_timeout(self, coro, timeout_seconds: float, operation_name: str):
        """Execute coroutine with timeout and proper error handling"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"{operation_name} timed out after {timeout_seconds}s")
            raise CustomTimeoutError(
                f"{operation_name} timed out after {timeout_seconds}s. "
                f"Try using summary mode or increase REVIEW_TIMEOUT_SECONDS.",
                timeout_seconds=timeout_seconds,
                operation=operation_name
            )
    
    async def review_with_streaming(self, request: ReviewRequest) -> AsyncGenerator[str, None]:
        """
        Review with streaming response - prevents terminal freezes for large responses
        
        ARCHITECTURAL FIX: Consolidated massive parameter list into ReviewRequest model
        to reduce coupling and improve maintainability.
        """
        trace_id = TraceContext.ensure_trace_id()
        start_time = time.time()
        
        try:
            # Pre-flight checks
            self._check_service_circuit_breaker()
            await self._acquire_review_slot()
            
            logger.info(f"Starting streaming review - Detail: {request.detail_level}, Focus: {request.focus}")
            
            # Execute core review with timeout protection - now using consolidated request object
            review_coro = self.core_service.process_review_request(request)
            
            # Calculate dynamic timeout based on detail level
            if request.detail_level == "comprehensive":
                timeout = self.review_timeout_seconds
            elif request.detail_level == "detailed":
                timeout = self.review_timeout_seconds * 0.8
            else:
                timeout = self.review_timeout_seconds * 0.6
            
            result = await self._execute_with_timeout(
                review_coro, 
                timeout, 
                f"Review ({request.detail_level})"
            )
            
            # Stream the response
            content_type = "json" if any(indicator in result.lower() for indicator in 
                                       ['"validation_report"', '"error_code"', '{"']) else "text"
            
            async for chunk in self.orchestrator.stream_response(
                result, 
                content_type=content_type,
                metadata={
                    'trace_id': trace_id,
                    'detail_level': request.detail_level,
                    'focus': request.focus,
                    'task_id': request.task_id
                }
            ):
                yield chunk
            
            # Success - reset failure count
            if self._failure_count > 0:
                self._failure_count = 0
                logger.debug("Reset service failure count after successful review")
            
            elapsed_time = time.time() - start_time
            logger.info(f"Streaming review completed successfully in {elapsed_time:.2f}s")
            
        except Exception as e:
            self._failure_count += 1
            elapsed_time = time.time() - start_time
            
            logger.error(f"Review failed after {elapsed_time:.2f}s (failure {self._failure_count}): {str(e)}")
            
            # Open circuit breaker if too many failures
            if self._failure_count >= self._failure_threshold:
                self._open_service_circuit_breaker()
            
            # Provide graceful error response
            error_context = TraceContext.create_context_dict({
                'error_type': type(e).__name__,
                'elapsed_time': elapsed_time,
                'detail_level': request.detail_level,
                'focus': request.focus
            })
            
            error_response = f"""🚨 Review Service Error

**Error**: {str(e)}
**Type**: {type(e).__name__}
**Trace ID**: {trace_id}
**Elapsed Time**: {elapsed_time:.2f}s

**Suggestions**:
- Try with summary detail level for faster processing
- Reduce content size or use chunked processing
- Check system resources and memory availability
- Increase timeout via REVIEW_TIMEOUT_SECONDS if needed

**Technical Context**:
```json
{error_context}
```

The review service will automatically recover. If issues persist, check logs for trace ID: {trace_id}
"""
            yield error_response
            
            # Re-raise for upstream handling
            raise ResilienceError(f"Review service error: {str(e)}") from e
            
        finally:
            await self._release_review_slot()
    
    async def review(self, request: ReviewRequest) -> str:
        """
        Non-streaming review - collects all chunks into single response
        
        ARCHITECTURAL FIX: Consolidated massive parameter list into ReviewRequest model
        to reduce coupling and improve maintainability.
        """
        chunks = []
        async for chunk in self.review_with_streaming(request):
            chunks.append(chunk)
        
        return "".join(chunks)
    
    async def process_review_request(self, request: ReviewRequest) -> str:
        """
        Process review request with memory protection - compatible with mcp_server
        This is the main entry point that enforces the 4GB memory limit
        
        ARCHITECTURAL FIX: Consolidated massive parameter list into ReviewRequest model
        to reduce coupling and improve maintainability.
        """
        # Check memory before starting
        current_memory_mb = self.orchestrator._get_memory_usage_mb()
        logger.info(f"Starting review with current memory usage: {current_memory_mb:.1f}MB / {self.orchestrator.memory_limit_mb}MB limit")
        
        if current_memory_mb > self.orchestrator.memory_limit_mb * 0.9:  # 90% threshold warning
            logger.warning(f"Memory usage high before review: {current_memory_mb:.1f}MB")
        
        # Use the review method which includes all protections
        return await self.review(request)
    
    def get_service_status(self) -> Dict:
        """Get current service status for monitoring"""
        return {
            'active_reviews': self._active_reviews,
            'max_concurrent_reviews': self.max_concurrent_reviews,
            'circuit_breaker_open': self._circuit_breaker_open,
            'circuit_breaker_reset_time': self._circuit_breaker_reset_time,
            'failure_count': self._failure_count,
            'review_timeout_seconds': self.review_timeout_seconds,
            'trace_id': TraceContext.get_trace_id()
        }
    
    # Delegate other methods to core service
    def get_session_stats(self) -> Dict:
        """Get session statistics from core service"""
        return self.core_service.get_session_stats()
    
    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old sessions via core service"""
        return self.core_service.cleanup_old_sessions(days_old)