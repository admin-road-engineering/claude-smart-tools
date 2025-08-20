"""
Base class for smart tools that route to multiple engines with CPU throttling
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import sys
import os

# Handle imports for both module and script execution
try:
    from ..services.cpu_throttler import get_cpu_throttler
except ImportError:
    # Add parent directory to path for script execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from services.cpu_throttler import get_cpu_throttler

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
        self._file_content_cache = {}
        self._cache_enabled = os.environ.get('ENABLE_FILE_CACHE', 'true').lower() == 'true'
        self._cache_hits = 0
        self._cache_misses = 0
        
        if self.cpu_throttler:
            logger.debug(f"Smart tool {self.tool_name} initialized with CPU throttling and file caching")
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
        """Execute a specific engine with improved error handling, CPU throttling, and file caching"""
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
        for param in path_params:
            if param in normalized_kwargs:
                value = normalized_kwargs[param]
                # Convert WindowsPath or single paths to list of strings
                if isinstance(value, (str, Path)) or hasattr(value, '__fspath__'):
                    normalized_kwargs[param] = [str(value)]
                    logger.debug(f"Normalized single {type(value).__name__} to list for {param}")
                elif isinstance(value, (list, tuple)):
                    normalized_kwargs[param] = [str(item) for item in value]
                    logger.debug(f"Normalized {len(value)} paths to strings for {param}")
        
        # Pre-populate file content cache if enabled
        if self._cache_enabled and any(param in normalized_kwargs for param in path_params):
            await self._populate_file_cache(normalized_kwargs, path_params)
            # Pass cache to engine if it supports it
            if 'file_content_cache' not in normalized_kwargs:
                normalized_kwargs['file_content_cache'] = self._file_content_cache
        
        try:
            engine = self.engines[engine_name]
            if hasattr(engine, 'execute'):
                result = await engine.execute(**normalized_kwargs)
            else:
                # Direct function call
                result = await engine(**normalized_kwargs)
            return result
        except Exception as e:
            error_msg = str(e)
            
            # Improve rate limiting error messages
            if "rate limited" in error_msg.lower() or "exhausted" in error_msg.lower():
                return f"⚠️ Rate limit reached. The Gemini API has usage limits. Please try again in a few minutes."
            
            # Improve file not found messages
            if "no files found" in error_msg.lower() or "no code files" in error_msg.lower():
                return f"📁 No valid files found. Please check the file paths."
            
            # API key issues
            if "api key" in error_msg.lower():
                return f"🔑 API key issue detected. Please check your Gemini API configuration."
            
            # General error with more context
            return f"Error in {engine_name}: {error_msg[:200]}..."
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
            import asyncio
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
        """Pre-populate file content cache for better performance"""
        import aiofiles
        from pathlib import Path
        
        # Collect all unique file paths from kwargs
        all_files = set()
        for param in path_params:
            if param in kwargs:
                paths = kwargs[param]
                if isinstance(paths, (list, tuple)):
                    for path in paths:
                        path = Path(str(path))
                        if path.is_file():
                            all_files.add(str(path))
                        elif path.is_dir():
                            # For directories, cache common source files
                            for ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']:
                                for file in path.rglob(f'*{ext}'):
                                    all_files.add(str(file))
                                    if len(all_files) > 100:  # Limit cache size
                                        break
        
        # Read files into cache
        for file_path in all_files:
            if file_path not in self._file_content_cache:
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        self._file_content_cache[file_path] = content
                        self._cache_misses += 1
                        logger.debug(f"Cached file content: {file_path}")
                except Exception as e:
                    logger.debug(f"Could not cache file {file_path}: {e}")
            else:
                self._cache_hits += 1
                logger.debug(f"Cache hit for file: {file_path}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for debugging and optimization"""
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_size': len(self._file_content_cache),
            'cache_hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
        }
    
    def clear_cache(self) -> None:
        """Clear the file content cache to free memory"""
        self._file_content_cache.clear()
        logger.info(f"Cleared file cache. Stats: {self.get_cache_stats()}")