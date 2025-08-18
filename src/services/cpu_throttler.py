"""
CPU throttling service to prevent overloading VS Code and the system
Provides CPU yield points and usage monitoring for heavy operations
Adapted from claude-gemini-mcp with singleton pattern for smart tools
"""
import asyncio
import time
import psutil
import logging
from typing import Optional, AsyncGenerator, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CPUThrottler:
    """CPU throttling and yield management for heavy operations with singleton pattern"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, config=None):
        """Implement singleton pattern for system-wide consistency"""
        if cls._instance is None:
            cls._instance = super(CPUThrottler, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        # Prevent re-initialization
        if CPUThrottler._initialized:
            return
        
        if config is None:
            raise ValueError("CPU throttler requires configuration on first initialization")
        
        self.config = config
        
        # CPU throttling configuration - unified from claude-gemini-mcp
        self.yield_interval_ms = getattr(config, 'processing_yield_interval_ms', 100)
        self.max_cpu_percent = getattr(config, 'max_cpu_usage_percent', 80.0)
        self.cpu_check_interval = getattr(config, 'cpu_check_interval', 10)
        self.file_scan_yield_frequency = getattr(config, 'file_scan_yield_frequency', 50)
        
        # State tracking
        self._last_yield_time = time.time()
        self._operation_count = 0
        self._cpu_warnings = 0
        self._throttle_active = False
        
        # CPU monitoring cache (to avoid excessive psutil calls)
        self._last_cpu_check = 0
        self._cached_cpu_percent = 0.0
        self._cpu_cache_duration = 1.0  # Cache CPU readings for 1 second
        
        CPUThrottler._initialized = True
        
        logger.info(f"CPU throttler singleton initialized - Yield: {self.yield_interval_ms}ms, "
                   f"CPU limit: {self.max_cpu_percent}%, Check interval: {self.cpu_check_interval}")
    
    @classmethod
    def get_instance(cls, config=None):
        """Get the singleton instance, creating if necessary"""
        if cls._instance is None:
            return cls(config)
        return cls._instance
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage with caching to reduce overhead"""
        current_time = time.time()
        
        # Use cached value if recent enough
        if current_time - self._last_cpu_check < self._cpu_cache_duration:
            return self._cached_cpu_percent
        
        try:
            # Get CPU usage - this is a brief snapshot
            cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking
            self._cached_cpu_percent = cpu_percent
            self._last_cpu_check = current_time
            return cpu_percent
        except Exception as e:
            logger.warning(f"Could not get CPU usage: {e}")
            return 0.0
    
    async def should_yield(self) -> bool:
        """Check if we should yield control back to the event loop"""
        current_time = time.time()
        
        # Time-based yielding
        time_since_yield = (current_time - self._last_yield_time) * 1000  # Convert to ms
        if time_since_yield >= self.yield_interval_ms:
            return True
        
        # Operation count-based yielding
        self._operation_count += 1
        if self._operation_count >= self.cpu_check_interval:
            self._operation_count = 0
            
            # Check CPU usage - this is the critical adaptive logic
            cpu_usage = self._get_cpu_usage()
            if cpu_usage > self.max_cpu_percent:
                if not self._throttle_active:
                    logger.warning(f"CPU usage high: {cpu_usage:.1f}% > {self.max_cpu_percent}% - activating throttling")
                    self._throttle_active = True
                return True
            else:
                if self._throttle_active:
                    logger.info(f"CPU usage normalized: {cpu_usage:.1f}% - deactivating throttling")
                    self._throttle_active = False
        
        return False
    
    async def yield_if_needed(self):
        """Yield control to the event loop if conditions are met"""
        if await self.should_yield():
            await self.yield_control()
    
    async def yield_control(self):
        """Unconditionally yield control back to the event loop"""
        self._last_yield_time = time.time()
        
        # Small sleep to allow other tasks to run
        if self._throttle_active:
            # Longer sleep when CPU is high
            await asyncio.sleep(0.01)  # 10ms
        else:
            # Minimal sleep just to yield
            await asyncio.sleep(0.001)  # 1ms
        
        logger.debug("CPU yielded to event loop")
    
    async def throttled_file_scan(self, items, yield_frequency: Optional[int] = None) -> AsyncGenerator[Any, None]:
        """
        Process items with automatic CPU yielding
        
        Args:
            items: Iterable of items to process
            yield_frequency: Override default file scan yield frequency
        
        Yields:
            Items from the iterable with CPU yielding between batches
        """
        if yield_frequency is None:
            yield_frequency = self.file_scan_yield_frequency
        
        count = 0
        for item in items:
            yield item
            
            count += 1
            if count >= yield_frequency:
                await self.yield_if_needed()
                count = 0
    
    async def throttled_batch_processing(self, items, batch_size: int = 50) -> AsyncGenerator[list, None]:
        """
        Process items in batches with CPU yielding between batches
        
        Args:
            items: Items to process
            batch_size: Number of items per batch
        
        Yields:
            Batches of items
        """
        batch = []
        for item in items:
            batch.append(item)
            
            if len(batch) >= batch_size:
                yield batch
                batch = []
                await self.yield_if_needed()
        
        # Yield remaining items
        if batch:
            yield batch
    
    def get_throttling_stats(self) -> dict:
        """Get current throttling statistics"""
        return {
            'throttle_active': self._throttle_active,
            'cpu_warnings': self._cpu_warnings,
            'last_cpu_usage': self._cached_cpu_percent,
            'operation_count': self._operation_count,
            'yield_interval_ms': self.yield_interval_ms,
            'max_cpu_percent': self.max_cpu_percent,
            'time_since_yield_ms': (time.time() - self._last_yield_time) * 1000,
            'singleton_initialized': CPUThrottler._initialized
        }
    
    def monitor_heavy_operation(self, operation_name: str):
        """
        Context manager for monitoring heavy operations
        
        Usage:
            async with throttler.monitor_heavy_operation("file_processing"):
                # Heavy processing here
                for item in large_list:
                    process_item(item)
                    await throttler.yield_if_needed()
        """
        return HeavyOperationMonitor(self, operation_name)


class HeavyOperationMonitor:
    """Context manager for monitoring heavy operations"""
    
    def __init__(self, throttler: CPUThrottler, operation_name: str):
        self.throttler = throttler
        self.operation_name = operation_name
        self.start_time = None
        self.start_cpu = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        self.start_cpu = self.throttler._get_cpu_usage()
        logger.debug(f"Starting heavy operation: {self.operation_name} (CPU: {self.start_cpu:.1f}%)")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        end_cpu = self.throttler._get_cpu_usage()
        duration = end_time - self.start_time
        
        logger.info(f"Completed heavy operation: {self.operation_name} "
                   f"(Duration: {duration:.2f}s, CPU: {self.start_cpu:.1f}% → {end_cpu:.1f}%)")
        
        # Ensure we yield after heavy operations
        await self.throttler.yield_control()


# Convenience function for getting the singleton instance
def get_cpu_throttler(config=None) -> Optional[CPUThrottler]:
    """Get the CPU throttler singleton instance"""
    try:
        return CPUThrottler.get_instance(config)
    except Exception as e:
        logger.warning(f"Could not initialize CPU throttler: {e}")
        return None