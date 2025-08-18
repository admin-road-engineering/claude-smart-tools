"""
Caching mechanism for correlation analysis results
Improves performance by avoiding redundant correlation computations
"""
import hashlib
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached correlation result"""
    result: Dict[str, Any]
    timestamp: float
    hit_count: int = 0
    
    def is_expired(self, ttl: int) -> bool:
        """Check if cache entry has expired"""
        return (time.time() - self.timestamp) > ttl


class CorrelationCache:
    """
    Simple in-memory cache for correlation results
    Uses content-based hashing for cache keys
    """
    
    def __init__(self, ttl: int = 300, max_entries: int = 100):
        """
        Initialize the correlation cache
        
        Args:
            ttl: Time-to-live in seconds (default: 5 minutes)
            max_entries: Maximum number of cache entries (default: 100)
        """
        self.ttl = ttl
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order = []  # Track access order for LRU eviction
        
        logger.info(f"Correlation cache initialized with TTL={ttl}s, max_entries={max_entries}")
    
    def generate_cache_key(self, engine_results: Dict[str, Any]) -> str:
        """
        Generate a stable cache key from engine results
        Uses content-based hashing to ensure consistency
        """
        try:
            # Sort and serialize the engine results for stable hashing
            # Convert complex objects to strings for serialization
            serializable_results = {}
            
            for engine, result in sorted(engine_results.items()):
                if isinstance(result, (dict, list)):
                    # For complex types, use JSON serialization
                    serializable_results[engine] = json.dumps(result, sort_keys=True)
                else:
                    # For simple types, convert to string
                    serializable_results[engine] = str(result)
            
            # Create a stable string representation
            content = json.dumps(serializable_results, sort_keys=True)
            
            # Generate SHA256 hash
            cache_key = hashlib.sha256(content.encode()).hexdigest()
            
            logger.debug(f"Generated cache key: {cache_key[:8]}...")
            return cache_key
            
        except Exception as e:
            logger.warning(f"Failed to generate cache key: {e}")
            # Return a unique key that won't match anything
            return f"error_{time.time()}"
    
    def get(self, engine_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached correlation results if available
        
        Args:
            engine_results: The engine results to look up
            
        Returns:
            Cached correlation results or None if not found/expired
        """
        cache_key = self.generate_cache_key(engine_results)
        
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # Check if entry has expired
            if entry.is_expired(self.ttl):
                logger.debug(f"Cache entry expired for key: {cache_key[:8]}...")
                del self._cache[cache_key]
                self._remove_from_access_order(cache_key)
                return None
            
            # Update hit count and access order
            entry.hit_count += 1
            self._update_access_order(cache_key)
            
            logger.info(f"Cache hit for key: {cache_key[:8]}... (hits: {entry.hit_count})")
            return entry.result
        
        logger.debug(f"Cache miss for key: {cache_key[:8]}...")
        return None
    
    def put(self, engine_results: Dict[str, Any], correlation_results: Dict[str, Any]):
        """
        Store correlation results in cache
        
        Args:
            engine_results: The engine results that were analyzed
            correlation_results: The correlation analysis results to cache
        """
        cache_key = self.generate_cache_key(engine_results)
        
        # Check if we need to evict entries
        if len(self._cache) >= self.max_entries:
            self._evict_lru()
        
        # Store the new entry
        entry = CacheEntry(
            result=correlation_results,
            timestamp=time.time()
        )
        
        self._cache[cache_key] = entry
        self._update_access_order(cache_key)
        
        logger.info(f"Cached correlation results for key: {cache_key[:8]}...")
    
    def clear(self):
        """Clear all cached entries"""
        self._cache.clear()
        self._access_order.clear()
        logger.info("Correlation cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = len(self._cache)
        total_hits = sum(entry.hit_count for entry in self._cache.values())
        
        # Calculate average age of entries
        if total_entries > 0:
            current_time = time.time()
            avg_age = sum(current_time - entry.timestamp 
                         for entry in self._cache.values()) / total_entries
        else:
            avg_age = 0
        
        return {
            'total_entries': total_entries,
            'total_hits': total_hits,
            'average_age_seconds': avg_age,
            'max_entries': self.max_entries,
            'ttl_seconds': self.ttl
        }
    
    def _update_access_order(self, cache_key: str):
        """Update the access order for LRU tracking"""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)
    
    def _remove_from_access_order(self, cache_key: str):
        """Remove a key from access order tracking"""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
    
    def _evict_lru(self):
        """Evict the least recently used entry"""
        if self._access_order:
            # Remove the least recently used entry
            lru_key = self._access_order[0]
            
            if lru_key in self._cache:
                logger.debug(f"Evicting LRU entry: {lru_key[:8]}...")
                del self._cache[lru_key]
                self._access_order.remove(lru_key)
    
    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired(self.ttl):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._remove_from_access_order(key)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


# Global cache instance
_global_cache: Optional[CorrelationCache] = None


def get_correlation_cache() -> CorrelationCache:
    """Get the global correlation cache instance"""
    global _global_cache
    
    if _global_cache is None:
        # Get TTL from environment or use default
        import os
        ttl = int(os.environ.get('CORRELATION_CACHE_TTL', '300'))
        max_entries = int(os.environ.get('CORRELATION_CACHE_MAX_ENTRIES', '100'))
        
        _global_cache = CorrelationCache(ttl=ttl, max_entries=max_entries)
    
    return _global_cache


def reset_correlation_cache():
    """Reset the global cache"""
    global _global_cache
    
    if _global_cache:
        _global_cache.clear()
    
    _global_cache = None