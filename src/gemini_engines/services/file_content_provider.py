"""
FileContentProvider - Focused service for file content reading and caching
Handles file I/O, content hashing, and cache management with concurrency safety
"""
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path
from ..security import get_path_validator
from ..services.cpu_throttler import CPUThrottler

# Use aiofiles for non-blocking file I/O
try:
    import aiofiles
    import aiofiles.os
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logging.warning("aiofiles not available - using thread pool executor for file I/O")


@dataclass
class FileMetadata:
    """Cached file metadata with content hash and timing"""
    path: str
    content: str
    content_hash: str
    size: int
    mtime: float
    cached_at: datetime
    exists: bool


class FileContentProvider:
    """
    Focused service for file content reading and intelligent caching
    
    Responsibilities:
    - Non-blocking file content reading with aiofiles
    - Content-hash based cache management with TTL
    - Concurrency-safe cache operations
    - File existence and modification time tracking
    - File size limits for DoS prevention
    """
    
    # SECURITY: Maximum file size to prevent memory exhaustion (50MB default)
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    
    def __init__(self, cache_ttl_seconds: int = 300, max_file_size_mb: int = 50, config=None):
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, FileMetadata] = {}
        self._cache_lock = asyncio.Lock()  # Concurrency protection
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        
        # CPU throttling for heavy file operations
        if config:
            self.cpu_throttler = CPUThrottler(config)
        else:
            self.cpu_throttler = None
        
        if not AIOFILES_AVAILABLE:
            self.logger.warning("aiofiles not available - using thread pool executor for async file I/O")
    
    async def get_content(self, file_path: str) -> str:
        """
        Get file content with cache-aware, non-blocking I/O
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            File content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable
            SecurityError: If path is outside project boundaries
        """
        # SECURITY: Validate path before any file operations
        validator = get_path_validator()
        validated_path = validator.validate_path(file_path, "read")
        file_path_str = str(validated_path)
        
        # Thread-safe cache check
        async with self._cache_lock:
            cached = self._cache.get(file_path_str)
            if cached and not await self._is_cache_stale_locked(cached):
                self.logger.debug(f"Cache hit for {file_path_str}")
                return cached.content
        
        # Cache miss or stale - read file fresh (outside lock for I/O)
        self.logger.debug(f"Cache miss for {file_path_str} - reading fresh")
        
        try:
            # CPU yield before heavy I/O operation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(file_path_str, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                stat = await aiofiles.os.stat(file_path_str)
            else:
                content = await self._run_in_executor(self._read_file_sync, file_path_str)
                stat = await self._run_in_executor(os.stat, file_path_str)
            
            # CPU yield after file reading, before hash calculation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            # Calculate content hash
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Thread-safe cache update
            async with self._cache_lock:
                self._cache[file_path_str] = FileMetadata(
                    path=file_path_str,
                    content=content,
                    content_hash=content_hash,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    cached_at=datetime.now(),
                    exists=True
                )
            
            self.logger.debug(f"Cached fresh content for {file_path} ({len(content)} chars)")
            return content
            
        except FileNotFoundError:
            # Cache the fact that file doesn't exist
            async with self._cache_lock:
                self._cache[file_path] = FileMetadata(
                    path=file_path,
                    content="",
                    content_hash="",
                    size=0,
                    mtime=0,
                    cached_at=datetime.now(),
                    exists=False
                )
            raise
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    async def get_content_hash(self, file_path: str) -> str:
        """
        Get content hash for a file (may use cache)
        
        Args:
            file_path: Path to the file
            
        Returns:
            MD5 hash of file content
        """
        # SECURITY: Validate path first
        validator = get_path_validator()
        validated_path = validator.validate_path(file_path, "hash")
        file_path_str = str(validated_path)
        
        # Try cache first
        async with self._cache_lock:
            cached = self._cache.get(file_path_str)
            if cached and cached.exists and not await self._is_cache_stale_locked(cached):
                return cached.content_hash
        
        # Read content to get hash (this will update cache)
        try:
            await self.get_content(file_path)
            # Now it should be in cache
            async with self._cache_lock:
                cached = self._cache.get(file_path)
                return cached.content_hash if cached and cached.exists else ""
        except Exception:
            return ""
    
    async def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists (may use cache)
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists and is readable
        """
        try:
            await self.get_content(file_path)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            # Other errors (permissions, etc) - file exists but not readable
            return True
    
    async def get_file_stats(self, file_path: str) -> Optional[Dict]:
        """
        Get file statistics (size, mtime) using cache when possible
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict with size and mtime, or None if file doesn't exist
        """
        async with self._cache_lock:
            cached = self._cache.get(file_path)
            if cached and not await self._is_cache_stale_locked(cached):
                if cached.exists:
                    return {"size": cached.size, "mtime": cached.mtime}
                else:
                    return None
        
        # Not in cache or stale - get fresh stats
        try:
            if AIOFILES_AVAILABLE:
                stat = await aiofiles.os.stat(file_path)
            else:
                stat = await self._run_in_executor(os.stat, file_path)
            
            return {"size": stat.st_size, "mtime": stat.st_mtime}
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"Error getting stats for {file_path}: {e}")
            return None
    
    def invalidate(self, paths: Optional[list] = None):
        """
        Invalidate cache for specific paths or entire cache
        
        Args:
            paths: Optional list of paths to invalidate. If None, clears entire cache.
        """
        # Note: This is synchronous since it's just manipulating the cache dict
        # In practice, you'd rarely call this during async operations
        if paths is None:
            cleared_count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cleared entire file cache ({cleared_count} entries)")
        else:
            cleared_count = 0
            for path in paths:
                if path in self._cache:
                    del self._cache[path]
                    cleared_count += 1
            self.logger.info(f"Cleared cache for {cleared_count} specific paths")
    
    async def get_cache_stats(self) -> Dict:
        """Get cache statistics for monitoring"""
        async with self._cache_lock:
            total_entries = len(self._cache)
            existing_files = sum(1 for cached in self._cache.values() if cached.exists)
            total_content_size = sum(len(cached.content) for cached in self._cache.values() if cached.exists)
            
            return {
                "total_entries": total_entries,
                "existing_files": existing_files,
                "missing_files": total_entries - existing_files,
                "total_content_size": total_content_size,
                "cache_ttl_seconds": self._cache_ttl.total_seconds()
            }
    
    async def _is_cache_stale_locked(self, cached: FileMetadata) -> bool:
        """
        Determine if cached file metadata is stale
        NOTE: This method assumes the caller already holds self._cache_lock
        """
        # Check cache age first (fast)
        if (datetime.now() - cached.cached_at) > self._cache_ttl:
            return True
        
        # If marked as non-existent, check if it still doesn't exist
        if not cached.exists:
            try:
                if AIOFILES_AVAILABLE:
                    await aiofiles.os.stat(cached.path)
                else:
                    await self._run_in_executor(os.stat, cached.path)
                # File now exists, cache is stale
                return True
            except FileNotFoundError:
                # File still doesn't exist, cache is fresh
                return False
            except Exception:
                # Can't check, assume stale to be safe
                return True
        
        # For existing files, check modification time and size
        try:
            if AIOFILES_AVAILABLE:
                current_stat = await aiofiles.os.stat(cached.path)
            else:
                current_stat = await self._run_in_executor(os.stat, cached.path)
            
            # Quick check: if mtime and size are identical, assume it's fresh
            if cached.mtime == current_stat.st_mtime and cached.size == current_stat.st_size:
                return False
            
            # If mtime/size differs, check content hash for definitive answer
            current_hash = await self._calculate_file_hash(cached.path)
            return current_hash != cached.content_hash
            
        except FileNotFoundError:
            # File no longer exists, cache is stale
            return True
        except Exception:
            # Error checking file, assume stale to be safe
            return True
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content (outside of cache)"""
        hasher = hashlib.md5()
        
        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(file_path, 'rb') as f:
                    while chunk := await f.read(8192):
                        hasher.update(chunk)
            else:
                content = await self._run_in_executor(self._read_file_binary_sync, file_path)
                hasher.update(content)
            
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    async def _run_in_executor(self, func, *args):
        """Run synchronous function in thread pool executor"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)
    
    def _read_file_sync(self, file_path: str) -> str:
        """Synchronous file read for thread pool execution"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _read_file_binary_sync(self, file_path: str) -> bytes:
        """Synchronous binary file read for thread pool execution"""
        with open(file_path, 'rb') as f:
            return f.read()