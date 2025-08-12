"""
Engine wrapper to adapt original tools for smart tool usage
"""
from typing import Any, Dict, Callable
import asyncio


class EngineWrapper:
    """
    Wraps original tool implementations for use by smart tools
    """
    
    def __init__(self, engine_name: str, original_function: Callable, **config):
        self.engine_name = engine_name
        self.original_function = original_function
        self.config = config
    
    async def execute(self, **kwargs) -> Any:
        """
        Execute the wrapped engine with parameter adaptation
        """
        import os
        
        # Adapt parameters if needed
        adapted_kwargs = self._adapt_parameters(kwargs)
        
        # Store current working directory
        original_cwd = os.getcwd()
        
        try:
            # Change to local gemini engines directory for execution context
            # This ensures the original tools run with proper config context
            current_file = os.path.abspath(__file__)
            smart_tools_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            gemini_engines_path = os.path.join(smart_tools_root, "gemini-engines")
            os.chdir(gemini_engines_path)
            
            # Call the original function
            if asyncio.iscoroutinefunction(self.original_function):
                result = await self.original_function(**adapted_kwargs)
            else:
                result = self.original_function(**adapted_kwargs)
            
            return result
            
        except Exception as e:
            # Return error information in a consistent format
            return f"Engine {self.engine_name} failed: {str(e)}"
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
    
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
        
        # Apply mappings
        for smart_param, engine_param in parameter_mappings.items():
            if smart_param in adapted and smart_param != engine_param:
                adapted[engine_param] = adapted.pop(smart_param)
        
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
    def create_engines_from_original(tool_implementations: Any) -> Dict[str, EngineWrapper]:
        """
        Create engine wrappers from original tool implementation object
        """
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