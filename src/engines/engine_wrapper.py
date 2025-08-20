"""
Engine wrapper to adapt original tools for smart tool usage with CPU throttling
"""
from typing import Any, Dict, Callable
import asyncio
import logging
import sys
import os
from pathlib import Path
import aiofiles

# Handle import for both module and script execution
try:
    from ..services.cpu_throttler import get_cpu_throttler
    from ..utils.path_utils import normalize_paths
except ImportError:
    # Handle direct script execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from services.cpu_throttler import get_cpu_throttler
    from utils.path_utils import normalize_paths

logger = logging.getLogger(__name__)


class EngineWrapper:
    """
    Wraps original tool implementations for use by smart tools with CPU throttling
    """
    
    def __init__(self, engine_name: str, original_function: Callable, gemini_client=None, **config):
        self.engine_name = engine_name
        self.original_function = original_function
        self.gemini_client = gemini_client
        self.config = config
        
        # Get CPU throttler singleton instance
        self.cpu_throttler = get_cpu_throttler()
    
    async def execute(self, **kwargs) -> Any:
        """
        Execute the wrapped engine with parameter adaptation and CPU throttling
        """
        import os
        
        # CPU yield before heavy engine operation
        if self.cpu_throttler:
            await self.cpu_throttler.yield_if_needed()
            logger.debug(f"Starting engine execution: {self.engine_name}")
        
        # CRITICAL FIX: Pre-process all path inputs to ensure they are lists
        logger.info(f"ENGINE EXECUTE: Raw input kwargs: {list(kwargs.keys())}")
        preprocessed_kwargs = self._preprocess_path_inputs(kwargs)
        logger.info(f"ENGINE EXECUTE: After preprocessing: {list(preprocessed_kwargs.keys())}")
        
        # Adapt parameters if needed
        adapted_kwargs = self._adapt_parameters(preprocessed_kwargs)
        
        # Store current working directory
        original_cwd = os.getcwd()
        
        try:
            # Get gemini engines path
            current_file = os.path.abspath(__file__)
            smart_tools_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            gemini_engines_path = os.path.join(smart_tools_root, "gemini-engines")
            
            # Use heavy operation monitor for CPU tracking
            if self.cpu_throttler:
                async with self.cpu_throttler.monitor_heavy_operation(f"engine_{self.engine_name}"):
                    result = await self._execute_engine_impl(adapted_kwargs, gemini_engines_path)
            else:
                result = await self._execute_engine_impl(adapted_kwargs, gemini_engines_path)
            
            return result
            
        except Exception as e:
            # Return error information in a consistent format
            logger.error(f"Engine {self.engine_name} failed: {str(e)}")
            return f"Engine {self.engine_name} failed: {str(e)}"
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
            
            # Final CPU yield after heavy operation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
    
    async def _execute_engine_impl(self, adapted_kwargs: Dict[str, Any], gemini_engines_path: str) -> Any:
        """Helper method to execute the engine with proper directory context"""
        import os
        
        # Log current state for debugging file access issues
        original_cwd = os.getcwd()
        logger.debug(f"Engine {self.engine_name} execution context:")
        logger.debug(f"  Current working directory: {original_cwd}")
        logger.debug(f"  Changing to: {gemini_engines_path}")
        
        # Log path parameters to help debug file access issues
        for param in ['paths', 'files', 'file_paths', 'source_paths']:
            if param in adapted_kwargs:
                paths = adapted_kwargs[param]
                if paths:
                    logger.debug(f"  {param}: {len(paths)} paths provided")
                    logger.debug(f"    First path: {paths[0] if paths else 'None'}")
                    # Check if first path exists
                    if paths and os.path.exists(paths[0]):
                        logger.debug(f"    First path exists: ✓")
                    else:
                        logger.warning(f"    First path does NOT exist: {paths[0] if paths else 'None'}")
        
        # Change to local gemini engines directory for execution context
        # This ensures the original tools run with proper config context
        os.chdir(gemini_engines_path)
        
        # Call the original function
        if asyncio.iscoroutinefunction(self.original_function):
            result = await self.original_function(**adapted_kwargs)
        else:
            result = self.original_function(**adapted_kwargs)
        
        return result
    
    def _preprocess_path_inputs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-process all potential path inputs to ensure they are lists
        This is the critical fix for WindowsPath iteration errors
        IMPORTANT: Converts to absolute paths since we change working directory
        """
        processed = kwargs.copy()
        
        # All possible path parameter names across all engines
        path_params = [
            'files', 'paths', 'file_paths', 'source_paths', 'config_paths', 
            'spec_paths', 'log_paths', 'schema_paths', 'project_paths'
        ]
        
        for param in path_params:
            if param in processed:
                original_value = processed[param]
                logger.info(f"PREPROCESSING: {param} = {type(original_value)} : {original_value}")
                
                # Use centralized path normalization - this returns ABSOLUTE paths
                normalized_paths = normalize_paths(original_value)
                processed[param] = normalized_paths
                logger.info(f"PREPROCESSING: Normalized {param} to absolute paths: {len(normalized_paths)} paths")
        
        return processed
    
    def _adapt_parameters(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt parameters from smart tool format to engine-specific format
        """
        adapted = kwargs.copy()
        
        # Common parameter mappings
        parameter_mappings = {
            # Smart tool param -> Engine param
            'files': 'paths',           # understand tool uses 'files', engines use 'paths'  
            'file_paths': 'paths',      # alternative mapping
            'query': 'query',           # search parameters
            'question': 'question',     # analysis questions
        }
        
        # Apply mappings and normalize paths
        for smart_param, engine_param in parameter_mappings.items():
            if smart_param in adapted and smart_param != engine_param:
                value = adapted.pop(smart_param)
                # Apply path normalization for path-related parameters
                if smart_param in ['files', 'file_paths'] and engine_param == 'paths':
                    logger.info(f"ENGINE WRAPPER: Normalizing {smart_param} -> {engine_param}, input type={type(value)}, value={value}")
                    normalized_value = normalize_paths(value)
                    logger.info(f"ENGINE WRAPPER: Normalized to {len(normalized_value)} paths: {normalized_value[:3]}...")
                    adapted[engine_param] = normalized_value
                else:
                    adapted[engine_param] = value
        
        # Handle path parameters that might not have been mapped
        path_related_params = ['paths', 'source_paths', 'config_paths', 'spec_paths', 'log_paths', 'schema_paths', 'project_paths']
        for param in path_related_params:
            if param in adapted:
                adapted[param] = normalize_paths(adapted[param])
        
        # Engine-specific adaptations
        if self.engine_name == 'analyze_code':
            # Ensure analysis_type is set
            if 'analysis_type' not in adapted:
                adapted['analysis_type'] = 'overview'
        
        elif self.engine_name == 'search_code':
            # Ensure search_type is set
            if 'search_type' not in adapted:
                adapted['search_type'] = 'text'
        
        elif self.engine_name == 'check_quality':
            # Ensure check_type is set
            if 'check_type' not in adapted:
                adapted['check_type'] = 'all'
        
        return adapted


class EngineFactory:
    """
    Factory for creating engine wrappers from original tool implementations
    """
    
    @staticmethod
    def _apply_path_normalization_monkey_patch(tool_implementations: Any):
        """
        Apply monkey patch to fix WindowsPath object is not iterable error
        This ensures immediate fix at runtime before any engine calls occur
        """
        if not hasattr(tool_implementations, '_collect_code_from_paths'):
            logger.warning("Tool implementations missing _collect_code_from_paths method - adding it now")
            
            # Add the missing method
            async def _collect_code_from_paths(self, paths, extensions=None):
                """
                Collect code content from specified paths (files or directories)
                Handles WindowsPath objects properly
                """
                from pathlib import Path
                
                # CRITICAL FIX: Normalize paths using our utility
                normalized_paths = normalize_paths(paths)
                logger.info(f"_collect_code_from_paths: Normalized {len(normalized_paths)} paths")
                
                collected_content = []
                processed_files = set()
                
                # Default code extensions if not specified
                if extensions is None:
                    extensions = [
                        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.cs',
                        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj',
                        '.sh', '.bash', '.ps1', '.bat', '.cmd',
                        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
                        '.xml', '.html', '.css', '.scss', '.less',
                        '.sql', '.md', '.rst', '.txt'
                    ]
                
                for path_str in normalized_paths:
                    if path_str in processed_files:
                        continue
                    
                    path = Path(path_str)
                    
                    # Only process actual files (normalize_paths already expanded directories)
                    if path.exists() and path.is_file():
                        # Check extension
                        if not extensions or any(path.suffix == ext for ext in extensions):
                            try:
                                async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = await f.read()
                                    collected_content.append(f"### File: {path}\n```\n{content}\n```\n")
                                    processed_files.add(path_str)
                            except Exception as e:
                                logger.warning(f"Could not read file {path}: {e}")
                
                return '\n\n'.join(collected_content)
            
            # Bind the method to the instance
            import types
            tool_implementations._collect_code_from_paths = types.MethodType(_collect_code_from_paths, tool_implementations)
            logger.info("Added _collect_code_from_paths method to tool implementations")
            return
        
        # Store original method
        original_method = tool_implementations._collect_code_from_paths
        
        async def patched_collect_code_from_paths(paths, extensions=None):
            """
            Patched version that normalizes paths before calling original method
            """
            from pathlib import Path
            
            # CRITICAL DEBUG: Log the exact input and type
            logger.info(f"MONKEY PATCH CALLED: Input type={type(paths)}, value={paths}")
            
            # CRITICAL FIX: Normalize paths to handle WindowsPath objects
            try:
                normalized_paths = normalize_paths(paths)
                logger.info(f"Monkey patch successfully normalized {len(normalized_paths)} paths from input type {type(paths)}")
                logger.info(f"Normalized paths: {normalized_paths[:3]}...")  # Show first 3 paths
            except Exception as e:
                # Log the full exception and stack trace for debugging
                logger.exception(
                    f"CRITICAL: Path normalization failed inside monkey patch. "
                    f"Original input type was {type(paths)}. Using robust fallback to prevent crash."
                )
                # Robust fallback path normalization to prevent crashes
                try:
                    if not paths:
                        normalized_paths = []
                    elif isinstance(paths, (list, tuple)):
                        normalized_paths = [str(p) for p in paths]
                    elif isinstance(paths, (str, Path)) or hasattr(paths, '__fspath__'):
                        normalized_paths = [str(paths)]
                    else:
                        # Last resort: convert to string and wrap in list
                        normalized_paths = [str(paths)]
                except Exception as fallback_error:
                    # Ultimate safety: return empty list to prevent crash
                    logger.error(f"Even fallback normalization failed: {fallback_error}. Returning empty list.")
                    normalized_paths = []
            
            # Call original method with normalized paths
            return await original_method(normalized_paths, extensions)
        
        # Apply the monkey patch
        tool_implementations._collect_code_from_paths = patched_collect_code_from_paths
        logger.info("Applied WindowsPath normalization monkey patch to GeminiToolImplementations")
    
    @staticmethod
    def create_engines_from_original(tool_implementations: Any) -> Dict[str, EngineWrapper]:
        """
        Create engine wrappers from original tool implementation object
        """
        # CRITICAL: Apply monkey patch immediately to fix WindowsPath error
        # This will add the missing _collect_code_from_paths method if needed
        EngineFactory._apply_path_normalization_monkey_patch(tool_implementations)
        
        engines = {}
        
        # Map of engine names to their corresponding methods
        engine_methods = {
            'analyze_code': 'analyze_code',
            'search_code': 'search_code', 
            'check_quality': 'check_quality',
            'analyze_docs': 'analyze_docs',
            'analyze_logs': 'analyze_logs',
            'analyze_database': 'analyze_database',
            'performance_profiler': 'performance_profiler',
            'config_validator': 'config_validator',
            'api_contract_checker': 'api_contract_checker',
            'analyze_test_coverage': 'analyze_test_coverage',
            'map_dependencies': 'map_dependencies',
            'interface_inconsistency_detector': 'interface_inconsistency_detector'
        }
        
        # Create wrapper for each engine
        for engine_name, method_name in engine_methods.items():
            if hasattr(tool_implementations, method_name):
                original_method = getattr(tool_implementations, method_name)
                engines[engine_name] = EngineWrapper(engine_name, original_method)
        
        return engines