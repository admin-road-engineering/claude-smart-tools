"""
Base class for smart tools that route to multiple engines with CPU throttling
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import asyncio
import logging
import sys
import os

# Handle imports for both module and script execution
try:
    from ..services.cpu_throttler import get_cpu_throttler
    from ..utils.project_context import get_project_context_reader
    from ..utils.path_utils import normalize_paths
    from ..utils.error_handler import handle_smart_tool_error
except ImportError:
    # Add parent directory to path for script execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from services.cpu_throttler import get_cpu_throttler
    from utils.project_context import get_project_context_reader
    from utils.path_utils import normalize_paths
    from utils.error_handler import handle_smart_tool_error

logger = logging.getLogger(__name__)


class SmartToolResult(BaseModel):
    """Result from a smart tool execution"""
    tool_name: str
    success: bool
    result: str
    engines_used: List[str]
    routing_decision: str
    metadata: Dict[str, Any] = {}
    correlations: Optional[Dict[str, Any]] = None
    conflicts: Optional[List[Dict[str, Any]]] = None
    resolutions: Optional[List[Dict[str, Any]]] = None


class BaseSmartTool(ABC):
    """Base class for all smart tools with CPU throttling and correlation support"""
    
    def __init__(self, engines: Dict[str, Any]):
        self.engines = engines
        self.tool_name = self.__class__.__name__.replace('Tool', '').lower()
        
        # Get CPU throttler singleton instance
        self.cpu_throttler = get_cpu_throttler()
        
        # Initialize correlation framework (lazy loading)
        self._correlation_framework = None
        self.enable_correlation = os.environ.get('ENABLE_CORRELATION_ANALYSIS', 'true').lower() == 'true'
        
        # Initialize file content cache for this execution
        self._file_content_cache = {}  # {file_path: (content, mtime)}
        self._cache_enabled = os.environ.get('ENABLE_FILE_CACHE', 'true').lower() == 'true'
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_stale_hits = 0
        
        # Configurable cache parameters
        self._cache_extensions = os.environ.get('CACHE_FILE_EXTENSIONS', 
            '.py,.js,.ts,.java,.cpp,.c,.go,.rs,.cs,.rb,.php,.yaml,.json,.toml').split(',')
        self._cache_dir_limit = int(os.environ.get('CACHE_DIR_LIMIT', '100'))
        
        # Initialize project context reader
        self.context_reader = get_project_context_reader()
        self._project_context_cache = {}  # Cache project context per execution
        
        # Configure retry behavior
        self._max_retries = int(os.environ.get('ENGINE_MAX_RETRIES', '3'))
        self._base_retry_delay = float(os.environ.get('ENGINE_BASE_RETRY_DELAY', '1.0'))
        self._max_retry_delay = float(os.environ.get('ENGINE_MAX_RETRY_DELAY', '30.0'))
        
        if self.cpu_throttler:
            logger.debug(f"Smart tool {self.tool_name} initialized with CPU throttling, file caching, and project context awareness")
        else:
            logger.warning(f"Smart tool {self.tool_name} initialized without CPU throttling")
    
    @abstractmethod
    async def execute(self, **kwargs) -> SmartToolResult:
        """Execute the smart tool with intelligent routing"""
        pass
    
    @abstractmethod
    def get_routing_strategy(self, **kwargs) -> Dict[str, Any]:
        """Determine which engines to use and how"""
        pass
    
    def get_available_engines(self) -> List[str]:
        """Get list of available engine names"""
        return list(self.engines.keys())
    
    async def execute_engine(self, engine_name: str, **kwargs) -> Any:
        """Execute a specific engine with improved error handling, CPU throttling, file caching, and project context"""
        if engine_name not in self.engines:
            return f"Engine {engine_name} not available"
        
        # CPU yield before heavy engine operation
        if self.cpu_throttler:
            await self.cpu_throttler.yield_if_needed()
            logger.debug(f"Starting {engine_name} engine execution with CPU throttling")
        
        # CRITICAL FIX: Normalize path parameters before passing to engine
        # This handles cases where paths might be WindowsPath objects
        from pathlib import Path
        path_params = ['files', 'paths', 'file_paths', 'sources', 'source_paths', 
                      'config_paths', 'spec_paths', 'log_paths', 'schema_paths', 
                      'project_paths']
        
        normalized_kwargs = kwargs.copy()
        
        # Add project context to kwargs if we have files/paths
        # Only add for engines that support it (currently only review_output)
        engines_supporting_context = ['review_output']
        files_for_context = self._extract_files_from_kwargs(normalized_kwargs, path_params)
        if files_for_context and engine_name in engines_supporting_context:
            project_context = await self._get_project_context(files_for_context)
            if project_context and project_context.get('context_files_found'):
                # Add formatted context to kwargs for engines that can use it
                normalized_kwargs['project_context'] = self.context_reader.format_context_for_analysis(project_context)
                logger.info(f"Added project context from {len(project_context['context_files_found'])} files to {engine_name}")
        for param in path_params:
            if param in normalized_kwargs:
                value = normalized_kwargs[param]
                # Use centralized path normalization
                normalized_paths = normalize_paths(value)
                normalized_kwargs[param] = normalized_paths
                logger.debug(f"Normalized {param} using centralized path utils: {len(normalized_paths)} paths")
        
        # Pre-populate file content cache if enabled
        if self._cache_enabled and any(param in normalized_kwargs for param in path_params):
            await self._populate_file_cache(normalized_kwargs, path_params)
            # Don't pass cache to engine directly - engines don't expect this parameter
            # The cache is used internally to speed up file operations
        
        try:
            engine = self.engines[engine_name]
            result = await self._execute_engine_with_retry(engine, engine_name, normalized_kwargs)
            return result
        except Exception as e:
            # Use standardized error handling
            context = {
                'operation': 'engine_execution',
                'engine_name': engine_name,
                'kwargs_keys': list(normalized_kwargs.keys()) if normalized_kwargs else []
            }
            return handle_smart_tool_error(e, context, engine_name)
        finally:
            # CPU yield after engine operation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
    
    async def execute_multiple_engines(self, engine_names: List[str], **kwargs) -> Dict[str, Any]:
        """Execute multiple engines with CPU-aware batching"""
        results = {}
        
        # Process engines with CPU throttling between each
        if self.cpu_throttler:
            # Use throttled batch processing for large engine sets
            async for batch in self.cpu_throttler.throttled_batch_processing(engine_names, batch_size=3):
                for engine_name in batch:
                    results[engine_name] = await self.execute_engine(engine_name, **kwargs)
        else:
            # Fallback: execute all engines sequentially
            for engine_name in engine_names:
                results[engine_name] = await self.execute_engine(engine_name, **kwargs)
        
        return results
    
    async def _execute_engine_with_retry(self, engine: Any, engine_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Execute engine with exponential backoff retry logic for rate limiting and transient errors
        Uses configurable retry parameters from environment variables
        """
        import time
        import random
        
        max_retries = self._max_retries
        
        for attempt in range(max_retries + 1):
            try:
                # Execute the engine
                if hasattr(engine, 'execute'):
                    result = await engine.execute(**kwargs)
                else:
                    # Direct function call
                    result = await engine(**kwargs)
                    
                # Success - return result
                if attempt > 0:
                    logger.info(f"Engine {engine_name} succeeded on retry attempt {attempt + 1}")
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if this is a retryable error
                is_rate_limit = "rate limited" in error_msg or "exhausted" in error_msg or "quota" in error_msg
                is_transient = "timeout" in error_msg or "connection" in error_msg or "network" in error_msg
                is_server_error = "500" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg
                
                if (is_rate_limit or is_transient or is_server_error) and attempt < max_retries:
                    # Calculate exponential backoff with jitter
                    base_delay = self._base_retry_delay * (2 ** attempt)  # 1, 2, 4, 8 seconds by default
                    jitter = random.uniform(0.1, 0.5)  # Add randomness to avoid thundering herd
                    delay = min(base_delay + jitter, self._max_retry_delay)  # Cap at max delay
                    
                    error_type = "rate limit" if is_rate_limit else ("server error" if is_server_error else "transient")
                    logger.warning(f"Engine {engine_name} failed on attempt {attempt + 1}/{max_retries + 1} "
                                 f"with {error_type} error. Retrying in {delay:.1f} seconds...")
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Not retryable or max retries exceeded
                    if attempt == max_retries and (is_rate_limit or is_transient or is_server_error):
                        logger.error(f"Engine {engine_name} failed after {max_retries + 1} attempts. "
                                   f"Final error: {str(e)}")
                    raise e
    
    async def analyze_correlations(self, engine_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze correlations between multiple engine results (non-blocking)"""
        if not self.enable_correlation or len(engine_results) < 2:
            return None
        
        try:
            # Lazy load correlation framework
            if self._correlation_framework is None:
                from ..services.correlation_framework import CorrelationFramework
                self._correlation_framework = CorrelationFramework()
            
            # Run correlation analysis in executor to avoid blocking
            from concurrent.futures import ThreadPoolExecutor
            
            # Use a thread pool for CPU-bound correlation analysis
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                # Run the synchronous analyze method in a thread
                correlation_results = await loop.run_in_executor(
                    executor,
                    self._correlation_framework.analyze,
                    engine_results
                )
            
            # Log summary
            if correlation_results and 'summary' in correlation_results:
                logger.info(f"Correlation summary: {correlation_results['summary']}")
            
            return correlation_results
            
        except ImportError as e:
            logger.warning(f"Correlation framework not available: {e}")
            self.enable_correlation = False
            return None
        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}")
            return None
    
    def format_correlation_report(self, correlation_data: Dict[str, Any]) -> str:
        """Format correlation analysis results for display"""
        if not correlation_data:
            return ""
        
        report_parts = []
        
        # Add correlations section
        if 'correlations' in correlation_data and correlation_data['correlations']:
            report_parts.append("\n## 🔗 Engine Correlations")
            for corr in correlation_data['correlations'][:5]:  # Limit to top 5
                report_parts.append(f"- {corr}")
        
        # Add conflicts section
        if 'conflicts' in correlation_data and correlation_data['conflicts']:
            report_parts.append("\n## ⚠️ Detected Conflicts")
            for conflict in correlation_data['conflicts'][:3]:  # Limit to top 3
                report_parts.append(f"- {conflict}")
        
        # Add resolutions section
        if 'resolutions' in correlation_data and correlation_data['resolutions']:
            report_parts.append("\n## ✅ Conflict Resolutions")
            for resolution in correlation_data['resolutions'][:3]:  # Limit to top 3
                report_parts.append(f"- {resolution}")
        
        # Add summary
        if 'summary' in correlation_data:
            report_parts.append(f"\n**Analysis Summary**: {correlation_data['summary']}")
        
        return "\n".join(report_parts) if report_parts else ""
    
    async def _populate_file_cache(self, kwargs: Dict[str, Any], path_params: List[str]) -> None:
        """Pre-populate file content cache with timestamp validation for freshness"""
        import aiofiles
        import os
        from pathlib import Path
        
        # Collect all unique file paths from kwargs
        all_files = set()
        for param in path_params:
            if param in kwargs:
                paths = kwargs[param]
                if isinstance(paths, (list, tuple)):
                    for path in paths:
                        path = Path(str(path))
                        is_file = await asyncio.to_thread(path.is_file)
                        if is_file:
                            all_files.add(str(path))
                        else:
                            is_dir = await asyncio.to_thread(path.is_dir)
                            if is_dir:
                                # For directories, cache configurable source files
                                for ext in self._cache_extensions:
                                    for file in path.rglob(f'*{ext}'):
                                        all_files.add(str(file))
                                        if len(all_files) > self._cache_dir_limit:
                                            break
        
        # Read files into cache with timestamp validation
        for file_path in all_files:
            try:
                current_mtime = await asyncio.to_thread(os.path.getmtime, file_path)
                
                # Check if file is in cache and if it's still fresh
                if file_path in self._file_content_cache:
                    cached_content, cached_mtime = self._file_content_cache[file_path]
                    if cached_mtime == current_mtime:
                        self._cache_hits += 1
                        logger.debug(f"Cache hit (fresh) for file: {file_path}")
                        continue
                    else:
                        self._cache_stale_hits += 1
                        logger.debug(f"Cache stale for file: {file_path}, re-reading")
                
                # Read the file (either not cached or stale)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    self._file_content_cache[file_path] = (content, current_mtime)
                    self._cache_misses += 1
                    logger.debug(f"Cached file content with mtime: {file_path}")
                    
            except Exception as e:
                logger.debug(f"Could not cache file {file_path}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging and optimization"""
        total_accesses = self._cache_hits + self._cache_misses + self._cache_stale_hits
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_stale_hits': self._cache_stale_hits,
            'cache_size': len(self._file_content_cache),
            'cache_hit_rate': self._cache_hits / total_accesses if total_accesses > 0 else 0,
            'cache_freshness_rate': self._cache_hits / (self._cache_hits + self._cache_stale_hits) if (self._cache_hits + self._cache_stale_hits) > 0 else 1.0,
            'cache_extensions': self._cache_extensions,
            'cache_dir_limit': self._cache_dir_limit
        }
    
    def clear_cache(self) -> None:
        """Clear the file content cache to free memory"""
        self._file_content_cache.clear()
        self._project_context_cache.clear()
        logger.info(f"Cleared file and project context cache. Stats: {self.get_cache_stats()}")
    
    def _extract_files_from_kwargs(self, kwargs: Dict[str, Any], path_params: List[str]) -> List[str]:
        """Extract file paths from kwargs for context reading"""
        files = []
        for param in path_params:
            if param in kwargs:
                value = kwargs[param]
                if isinstance(value, (list, tuple)):
                    files.extend([str(item) for item in value])
                elif value is not None:
                    files.append(str(value))
        return files
    
    async def _get_project_context(self, files: List[str]) -> Dict[str, Any]:
        """Get project context for the given files (cached per execution)"""
        # Create a cache key from sorted file paths
        cache_key = '|'.join(sorted(files[:5]))  # Use first 5 files for cache key
        
        if cache_key in self._project_context_cache:
            logger.debug(f"Using cached project context for {len(files)} files")
            return self._project_context_cache[cache_key]
        
        # Read project context
        logger.info(f"Reading project context for {len(files)} files")
        context = self.context_reader.read_project_context(files)
        
        # Cache the context
        self._project_context_cache[cache_key] = context
        
        # Log what we found
        if context.get('claude_md_content'):
            logger.info(f"Found project CLAUDE.md with {len(context['claude_md_content'])} chars")
        if context.get('project_type'):
            logger.info(f"Detected project type: {context['project_type']}")
        
        return context