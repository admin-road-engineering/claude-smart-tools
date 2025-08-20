"""
File Freshness Decorator - Implements 3-phase validation pipeline
Encapsulates pre-analysis validation, execution, and post-analysis stale detection
"""
import functools
import logging
from typing import List, Any, Dict, Callable

from ..exceptions import AnalysisBlockedError, StaleAnalysisDetectedError
from ..services.file_integrity_validator import FileIntegrityValidator


logger = logging.getLogger(__name__)


def extract_paths_from_args(args: tuple, kwargs: Dict[str, Any]) -> List[str]:
    """
    Extract file paths from function arguments
    
    Supports common parameter names: paths, path, file_paths, search_paths
    """
    # Check kwargs first
    for param_name in ['paths', 'path', 'file_paths', 'search_paths', 'scan_paths']:
        if param_name in kwargs and kwargs[param_name]:
            paths = kwargs[param_name]
            if isinstance(paths, str):
                return [paths]
            elif isinstance(paths, list):
                return paths
    
    # Check positional args (usually first or second parameter)
    for i, arg in enumerate(args[:3]):  # Check first 3 args
        if isinstance(arg, list) and len(arg) > 0 and isinstance(arg[0], str):
            # Looks like a list of paths
            return arg
        elif isinstance(arg, str) and ('/' in arg or '\\' in arg or arg.endswith('.py')):
            # Looks like a single path
            return [arg]
    
    return []


def with_file_freshness_check(file_validator: FileIntegrityValidator):
    """
    Decorator factory that creates a file freshness validation decorator
    
    Implements 3-phase validation pipeline:
    1. Pre-analysis: Validate file paths and block if critical issues
    2. Execute: Run tool function on verified files only
    3. Post-analysis: Detect stale references in output
    
    Args:
        file_validator: FileIntegrityValidator instance for validation logic
    """
    def decorator(tool_function: Callable) -> Callable:
        @functools.wraps(tool_function)
        async def wrapper(self, *args, **kwargs) -> str:
            tool_name = tool_function.__name__
            logger.debug(f"Starting {tool_name} with file freshness validation")
            
            # Extract file paths from arguments
            file_paths = extract_paths_from_args(args, kwargs)
            
            if not file_paths:
                # No paths provided - let tool handle its own path discovery
                # This allows tools to use their own smart path detection
                logger.debug(f"{tool_name}: No explicit paths provided, delegating to tool")
                return await tool_function(self, *args, **kwargs)
            
            try:
                # PHASE 1: PRE-ANALYSIS VALIDATION (CRITICAL)
                logger.info(f"{tool_name}: Starting file validation for {len(file_paths)} paths")
                validation_report = await file_validator.create_validation_report(file_paths)
                
                if validation_report.has_critical_issues:
                    logger.error(f"{tool_name}: Analysis blocked due to validation issues")
                    raise AnalysisBlockedError(
                        f"Analysis blocked: {validation_report.validation_summary}",
                        validation_report
                    )
                
                logger.info(f"{tool_name}: File validation passed - {len(validation_report.verified_files)} files verified")
                
                # PHASE 2: EXECUTE TOOL ON VERIFIED FILES
                # Inject verified files into kwargs, preserving original parameter name
                original_paths_param = None
                for param_name in ['paths', 'path', 'file_paths', 'search_paths', 'scan_paths']:
                    if param_name in kwargs:
                        original_paths_param = param_name
                        break
                
                if original_paths_param:
                    kwargs[original_paths_param] = validation_report.verified_files
                    logger.debug(f"{tool_name}: Injected {len(validation_report.verified_files)} verified files as '{original_paths_param}'")
                else:
                    # Fallback: inject as 'paths' parameter
                    kwargs['verified_files'] = validation_report.verified_files
                    logger.debug(f"{tool_name}: Injected {len(validation_report.verified_files)} verified files as 'verified_files'")
                
                # Execute the core tool function
                tool_output = await tool_function(self, *args, **kwargs)
                
                # PHASE 3: POST-ANALYSIS STALE DETECTION
                logger.debug(f"{tool_name}: Checking output for stale file references")
                known_valid_files = set(validation_report.verified_files)
                stale_report = await file_validator.detect_stale_references(
                    analysis_output=tool_output,
                    known_valid_files=known_valid_files
                )
                
                if stale_report.is_stale:
                    logger.warning(f"{tool_name}: Stale file references detected in output")
                    raise StaleAnalysisDetectedError(
                        f"Analysis result contains references to {len(stale_report.stale_files_detected)} non-existent files",
                        tool_output,
                        stale_report
                    )
                
                # SUCCESS: Return output with validation header for transparency
                validation_header = validation_report.format_current_state_report()
                tool_icon = {
                    'enhanced_search_code': '🔍',
                    'enhanced_analyze_code': '🔬', 
                    'enhanced_check_quality': '🔍'
                }.get(tool_name, '📋')
                
                return f"{validation_header}\n\n{tool_icon} {tool_name.upper().replace('_', ' ')} RESULTS:\n{tool_output}"
                
            except (AnalysisBlockedError, StaleAnalysisDetectedError):
                # Re-raise structured exceptions for MCP handler to format
                raise
            except Exception as e:
                # Unexpected error during validation
                logger.error(f"{tool_name}: Unexpected error during file validation: {e}")
                # Let the original tool handle the error its own way
                return await tool_function(self, *args, **kwargs)
        
        return wrapper
    return decorator


class FileValidationMixin:
    """
    Mixin class that provides file validation capabilities to tool integration classes
    
    This can be mixed into EnhancedToolIntegration to provide the validation infrastructure
    """
    
    def __init__(self, *args, file_validator: FileIntegrityValidator, **kwargs):
        """Initialize with file validator dependency"""
        super().__init__(*args, **kwargs)
        self.file_validator = file_validator
    
    def with_validation(self, tool_function: Callable) -> Callable:
        """Apply file freshness validation to a tool function"""
        return with_file_freshness_check(self.file_validator)(tool_function)
    
    async def validate_paths_for_tool(self, paths: List[str], tool_name: str) -> tuple:
        """
        Manual validation for tools that need custom handling
        
        Returns:
            tuple: (validation_report, should_proceed)
        """
        try:
            validation_report = await self.file_validator.create_validation_report(paths)
            
            if validation_report.has_critical_issues:
                logger.warning(f"{tool_name}: Validation failed - {validation_report.validation_summary}")
                return validation_report, False
            else:
                logger.info(f"{tool_name}: Validation passed - {len(validation_report.verified_files)} files verified")
                return validation_report, True
                
        except Exception as e:
            logger.error(f"{tool_name}: Error during path validation: {e}")
            return None, False
    
    async def check_for_stale_references(self, output: str, known_files: set, tool_name: str) -> bool:
        """
        Manual stale reference check for tools that need custom handling
        
        Returns:
            bool: True if output is clean, False if stale references detected
        """
        try:
            stale_report = await self.file_validator.detect_stale_references(output, known_files)
            
            if stale_report.is_stale:
                logger.warning(f"{tool_name}: Stale references detected - confidence {stale_report.confidence_score:.1%}")
                return False
            else:
                logger.debug(f"{tool_name}: No stale references detected")
                return True
                
        except Exception as e:
            logger.error(f"{tool_name}: Error during stale reference check: {e}")
            return True  # Err on side of allowing output


# Example usage patterns for different tool types:

def create_validated_tool_methods(tool_integration_instance, file_validator: FileIntegrityValidator):
    """
    Factory function to create validated versions of tool methods
    
    This demonstrates how to apply the decorator to existing methods
    """
    # Create decorator instance
    validation_decorator = with_file_freshness_check(file_validator)
    
    # Apply to tool methods
    validated_methods = {}
    
    if hasattr(tool_integration_instance, 'enhanced_search_code'):
        validated_methods['enhanced_search_code'] = validation_decorator(
            tool_integration_instance.enhanced_search_code
        )
    
    if hasattr(tool_integration_instance, 'enhanced_analyze_code'):
        validated_methods['enhanced_analyze_code'] = validation_decorator(
            tool_integration_instance.enhanced_analyze_code
        )
    
    if hasattr(tool_integration_instance, 'enhanced_check_quality'):
        validated_methods['enhanced_check_quality'] = validation_decorator(
            tool_integration_instance.enhanced_check_quality
        )
    
    return validated_methods