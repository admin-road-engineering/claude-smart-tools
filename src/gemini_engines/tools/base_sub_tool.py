"""
Adapter pattern implementation for existing tools to conform to IAnalysisTool interface.
This bridges the gap between legacy tool implementations and the new architecture.
"""
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional

from .interfaces import IAnalysisTool, AnalysisResult, ToolStatus
from .base_tool import BaseTool, ToolResult
from ..constants.tool_names import *

logger = logging.getLogger(__name__)


class BaseSubToolAdapter(IAnalysisTool):
    """
    Adapter that wraps existing BaseTool instances to conform to IAnalysisTool interface.
    Handles conversion between old ToolResult and new AnalysisResult formats.
    """
    
    def __init__(self, wrapped_tool: BaseTool):
        """
        Initialize the adapter with a BaseTool instance.
        
        Args:
            wrapped_tool: The BaseTool instance to wrap
        """
        self.wrapped_tool = wrapped_tool
        self._tool_name = wrapped_tool.tool_name if hasattr(wrapped_tool, 'tool_name') else wrapped_tool.__class__.__name__
    
    @property
    def name(self) -> str:
        """Return the name of the wrapped tool"""
        return self._tool_name
    
    async def execute(self, 
                     file_paths: List[str], 
                     context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute the wrapped tool and convert its result to AnalysisResult format.
        
        Args:
            file_paths: List of file paths to analyze
            context: Context dictionary with review parameters
            
        Returns:
            AnalysisResult with standardized format
        """
        start_time = time.time()
        
        try:
            # Handle dry run mode
            if context.get('dry_run', False):
                return self._create_dry_run_result(file_paths, context)
            
            # Prepare parameters for the wrapped tool
            tool_params = self._prepare_tool_parameters(file_paths, context)
            
            # Execute the wrapped tool
            logger.debug(f"Executing wrapped tool {self.name} with {len(file_paths)} files")
            
            if asyncio.iscoroutinefunction(self.wrapped_tool.execute):
                # Tool has async execute method
                tool_result = await self.wrapped_tool.execute(**tool_params)
            else:
                # Tool has sync execute method, run in thread pool
                tool_result = await asyncio.to_thread(self.wrapped_tool.execute, **tool_params)
            
            execution_time = time.time() - start_time
            
            # Convert ToolResult to AnalysisResult
            return self._convert_tool_result(tool_result, execution_time)
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool {self.name} execution failed: {e}")
            
            return AnalysisResult(
                tool_name=self.name,
                status=ToolStatus.FAILURE,
                error_message=str(e),
                execution_time_seconds=execution_time
            )
    
    def _prepare_tool_parameters(self, file_paths: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare parameters for the wrapped tool based on its expected interface.
        Maps new context format to legacy tool parameters.
        """
        params = {
            'files': file_paths,
            'with_ai': True,  # Most tools support AI interpretation
            'context': context.get('review_focus', 'comprehensive review')
        }
        
        # Add tool-specific parameters based on tool name
        
        tool_name = self.name.lower()
        
        if CONFIG_VALIDATOR in tool_name:
            params.update({
                'check_security': context.get('check_security', True),
                'check_deprecated': context.get('check_deprecated', True),
                'check_required': context.get('check_required', True)
            })
        
        elif API_CONTRACT_CHECKER in tool_name:
            params.update({
                'baseline_spec': context.get('baseline_spec'),
                'compare_mode': context.get('compare_mode', False)
            })
        
        elif INTERFACE_INCONSISTENCY_DETECTOR in tool_name:
            params.update({
                'check_methods': context.get('check_methods', True),
                'check_properties': context.get('check_properties', True),
                'check_returns': context.get('check_returns', True),
                'check_parameters': context.get('check_parameters', True)
            })
        
        elif TEST_COVERAGE_ANALYZER in tool_name:
            # Split files into source and test files
            source_files = [f for f in file_paths if not any(test_indicator in f.lower() 
                           for test_indicator in ['test_', '_test', 'tests/'])]
            test_files = [f for f in file_paths if any(test_indicator in f.lower() 
                         for test_indicator in ['test_', '_test', 'tests/'])]
            
            params.update({
                'source_paths': source_files,
                'test_paths': test_files,
                'mapping_strategy': context.get('mapping_strategy', 'convention')
            })
            # Remove 'files' key as this tool uses source_paths/test_paths
            params.pop('files', None)
        
        elif DEPENDENCY_MAPPER in tool_name:
            params.update({
                'source_paths': file_paths,
                'analysis_depth': context.get('analysis_depth', 'transitive')
            })
            # Remove 'files' key as this tool uses source_paths
            params.pop('files', None)
        
        elif PERFORMANCE_PROFILER in tool_name:
            # Performance profiler is a service, needs special handling
            params.update({
                'operation_name': context.get('operation_name', 'comprehensive_review'),
                'trace_id': context.get('session_id')
            })
        
        elif ACCESSIBILITY_CHECKER in tool_name:
            params.update({
                'check_images': context.get('check_images', True),
                'check_headings': context.get('check_headings', True),
                'check_forms': context.get('check_forms', True),
                'check_aria': context.get('check_aria', True),
                'check_keyboard': context.get('check_keyboard', True),
                'check_contrast': context.get('check_contrast', False)
            })
        
        return params
    
    def _convert_tool_result(self, tool_result: ToolResult, execution_time: float) -> AnalysisResult:
        """
        Convert legacy ToolResult to new AnalysisResult format.
        
        Args:
            tool_result: Original ToolResult from wrapped tool
            execution_time: Execution time in seconds
            
        Returns:
            AnalysisResult with converted data
        """
        if isinstance(tool_result, str):
            # Some tools return string directly
            return AnalysisResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={'formatted_result': tool_result},
                execution_time_seconds=execution_time
            )
        
        if not isinstance(tool_result, ToolResult):
            # Handle unexpected result types
            return AnalysisResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={'raw_result': str(tool_result)},
                execution_time_seconds=execution_time
            )
        
        # Convert ToolResult to AnalysisResult
        status = ToolStatus.SUCCESS if tool_result.success else ToolStatus.FAILURE
        
        output = {
            'core_results': tool_result.core_results,
            'ai_interpretation': tool_result.ai_interpretation,
            'recommendations': tool_result.recommendations,
            'formatted_output': getattr(tool_result, 'formatted_output', None)
        }
        
        return AnalysisResult(
            tool_name=self.name,
            status=status,
            output=output,
            error_message=tool_result.error if hasattr(tool_result, 'error') else None,
            execution_time_seconds=execution_time,
            timestamp=tool_result.timestamp
        )
    
    def _create_dry_run_result(self, file_paths: List[str], context: Dict[str, Any]) -> AnalysisResult:
        """
        Create a mock result for dry-run mode.
        
        Args:
            file_paths: Files that would be analyzed
            context: Analysis context
            
        Returns:
            Mock AnalysisResult for testing
        """
        mock_output = {
            'dry_run': True,
            'tool_name': self.name,
            'files_analyzed': len(file_paths),
            'focus': context.get('review_focus', 'all'),
            'mock_findings': [
                f"Mock finding 1 from {self.name}",
                f"Mock finding 2 from {self.name}"
            ],
            'mock_recommendations': [
                f"Mock recommendation 1 from {self.name}",
                f"Mock recommendation 2 from {self.name}"
            ]
        }
        
        return AnalysisResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output=mock_output,
            execution_time_seconds=0.1  # Instant for dry run
        )


class GeminiToolImplementationAdapter(IAnalysisTool):
    """
    Special adapter for GeminiToolImplementations that don't follow BaseTool pattern.
    These tools are methods on the GeminiToolImplementations class.
    """
    
    def __init__(self, tool_impl_instance, tool_method_name: str, tool_display_name: str):
        """
        Initialize adapter for GeminiToolImplementations methods.
        
        Args:
            tool_impl_instance: Instance of GeminiToolImplementations
            tool_method_name: Name of the method to call
            tool_display_name: Display name for the tool
        """
        self.tool_impl = tool_impl_instance
        self.method_name = tool_method_name
        self._tool_name = tool_display_name
    
    @property
    def name(self) -> str:
        return self._tool_name
    
    async def execute(self, 
                     file_paths: List[str], 
                     context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute the GeminiToolImplementations method.
        
        Args:
            file_paths: Files to analyze
            context: Analysis context
            
        Returns:
            AnalysisResult with tool output
        """
        start_time = time.time()
        
        try:
            if context.get('dry_run', False):
                return self._create_dry_run_result(file_paths, context)
            
            # Get the method to call
            method = getattr(self.tool_impl, self.method_name)
            
            # Prepare method parameters based on tool type
            params = self._prepare_method_parameters(file_paths, context)
            
            logger.debug(f"Executing GeminiToolImplementations.{self.method_name}")
            
            # Execute the method
            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = await asyncio.to_thread(method, **params)
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={'result': result},
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"GeminiTool {self.name} execution failed: {e}")
            
            return AnalysisResult(
                tool_name=self.name,
                status=ToolStatus.FAILURE,
                error_message=str(e),
                execution_time_seconds=execution_time
            )
    
    def _prepare_method_parameters(self, file_paths: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare parameters for GeminiToolImplementations methods"""
        
        # Map common parameters
        params = {}
        
        if self.method_name == 'analyze_code':
            params = {
                'paths': file_paths,
                'analysis_type': context.get('analysis_type', 'overview'),
                'question': context.get('question', ''),
                'verbose': context.get('verbose', True),
                'output_format': 'text'
            }
        
        elif self.method_name == 'check_quality':
            params = {
                'paths': file_paths,
                'check_type': context.get('check_type', 'all'),
                'test_paths': context.get('test_paths', []),
                'verbose': context.get('verbose', True)
            }
        
        elif self.method_name == 'search_code':
            params = {
                'query': context.get('query', 'TODO'),
                'paths': file_paths,
                'search_type': 'text',
                'context_question': context.get('context_question', 'What does this code do?')
            }
        
        return params
    
    def _create_dry_run_result(self, file_paths: List[str], context: Dict[str, Any]) -> AnalysisResult:
        """Create dry-run result for GeminiToolImplementations"""
        return AnalysisResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                'dry_run': True,
                'method': self.method_name,
                'files_count': len(file_paths),
                'mock_result': f"Mock result from {self.name}"
            },
            execution_time_seconds=0.1
        )