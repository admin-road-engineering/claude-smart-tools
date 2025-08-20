"""
Wrapper to adapt GeminiToolImplementations methods to IAnalysisTool interface
Now with context sharing support for cross-tool intelligence
"""
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base_tool import BaseTool, ToolResult
from .interfaces import IAnalysisTool, AnalysisResult, ToolStatus
from ..constants.tool_names import *
from ..models.context_models import (
    ContextEntry, ContextType, ContextCategory, ContextPriority,
    CodeLocus, ToolContextRequirements
)

logger = logging.getLogger(__name__)


class GeminiToolWrapper(IAnalysisTool):
    """
    Wrapper that adapts GeminiToolImplementations methods to the IAnalysisTool interface.
    This allows Gemini tools to be used within the comprehensive review orchestration.
    """
    
    def __init__(self, tool_name: str, tool_method, gemini_client=None):
        """
        Initialize the wrapper with a specific Gemini tool method.
        
        Args:
            tool_name: Name of the tool
            tool_method: The actual method from GeminiToolImplementations to call
            gemini_client: Optional Gemini client for AI interpretation
        """
        self._name = tool_name
        self.tool_name = tool_name  # Some code expects this attribute
        self.tool_method = tool_method
        self.gemini_client = gemini_client
    
    @property
    def name(self) -> str:
        """The unique name of the tool"""
        return self._name
    
    async def execute(self, 
                     file_paths: List[str], 
                     context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute the wrapped Gemini tool and return standardized result.
        
        This is the required method from IAnalysisTool interface that was missing.
        It delegates to _core_utility for actual execution and wraps the result
        in an AnalysisResult object.
        
        Args:
            file_paths: List of file paths to analyze
            context: Execution context dictionary
            
        Returns:
            AnalysisResult with status and output
        """
        start_time = time.time()
        
        try:
            # Call the existing _core_utility method which already handles tool execution
            # Pass relevant context parameters as kwargs
            kwargs = {}
            if 'focus' in context:
                kwargs['focus'] = context['focus']
            if 'detail_level' in context:
                kwargs['detail_level'] = context['detail_level']
            if 'context' in context:
                kwargs['context'] = context['context']
                
            result = await self._core_utility(file_paths, **kwargs)
            
            # Check if the result contains an error
            if isinstance(result, dict) and 'error' in result:
                # Tool execution failed but returned an error dict
                return AnalysisResult(
                    tool_name=self._name,
                    status=ToolStatus.FAILURE,
                    error_message=result.get('error', 'Unknown error'),
                    output=result,
                    execution_time_seconds=time.time() - start_time
                )
            
            # Get AI interpretation if available
            interpretation = None
            if hasattr(self, '_get_ai_interpretation'):
                try:
                    interpretation = await self._get_ai_interpretation(result, context.get('context'))
                except Exception as e:
                    logger.warning(f"Failed to get AI interpretation for {self._name}: {e}")
                    interpretation = None
            
            # Return successful AnalysisResult
            return AnalysisResult(
                tool_name=self._name,
                status=ToolStatus.SUCCESS,
                output={
                    "result": result, 
                    "interpretation": interpretation if interpretation else result.get('analysis', str(result))
                },
                execution_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Tool {self._name} execution failed: {e}", exc_info=True)
            
            # Return failure AnalysisResult with detailed error
            return AnalysisResult(
                tool_name=self._name,
                status=ToolStatus.FAILURE,
                error_message=f"Tool execution failed: {str(e)}",
                output=None,
                execution_time_seconds=time.time() - start_time
            )
    
    async def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Execute the wrapped Gemini tool method.
        
        Args:
            files: List of file paths to analyze
            **kwargs: Tool-specific parameters
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Call the wrapped tool method using standardized tool names
            # Most Gemini tools expect specific parameter names
            if self._name == TEST_COVERAGE_ANALYZER:
                result = await self.tool_method(source_paths=files, **kwargs)
            elif self._name == CONFIG_VALIDATOR:
                result = await self.tool_method(config_paths=files, **kwargs)
            elif self._name == DEPENDENCY_MAPPER:
                result = await self.tool_method(project_paths=files, **kwargs)
            elif self._name == API_CONTRACT_CHECKER:
                result = await self.tool_method(spec_paths=files, **kwargs)
            elif self._name == INTERFACE_INCONSISTENCY_DETECTOR:
                result = await self.tool_method(source_paths=files, **kwargs)
            elif self._name == PERFORMANCE_PROFILER:
                # Performance profiler expects target_operation
                result = await self.tool_method(target_operation=files[0] if files else "unknown", **kwargs)
            elif self._name == ANALYZE_CODE:
                result = await self.tool_method(paths=files, **kwargs)
            elif self._name == SEARCH_CODE:
                # Search code needs a query - use a default
                result = await self.tool_method(query="class|function|def", paths=files, **kwargs)
            elif self._name == CHECK_QUALITY:
                result = await self.tool_method(paths=files, **kwargs)
            elif self._name == ANALYZE_DOCS:
                result = await self.tool_method(sources=files, **kwargs)
            elif self._name == ANALYZE_LOGS:
                result = await self.tool_method(log_paths=files, **kwargs)
            elif self._name == ANALYZE_DATABASE:
                result = await self.tool_method(schema_paths=files, **kwargs)
            else:
                # Default: try with paths parameter
                result = await self.tool_method(paths=files, **kwargs)
            
            # Convert result to dict if it's a string
            if isinstance(result, str):
                return {
                    "analysis": result,
                    "files_analyzed": len(files),
                    "tool": self.tool_name
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Tool {self._name} failed: {e}")
            return {
                "error": str(e),
                "files_attempted": len(files),
                "tool": self._name
            }
    
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get AI interpretation of the results.
        
        Since Gemini tools already include AI analysis in their output,
        we can often just format the existing results.
        
        Args:
            core_results: Results from _core_utility
            context: Optional additional context
            
        Returns:
            Formatted interpretation string
        """
        if "error" in core_results:
            return f"Tool {self._name} encountered an error: {core_results['error']}"
        
        if "analysis" in core_results:
            # The tool already provided AI analysis
            return core_results["analysis"]
        
        # Format the results as a summary
        summary = f"## {self._name} Analysis\n\n"
        for key, value in core_results.items():
            if key not in ["tool", "files_analyzed"]:
                if isinstance(value, dict):
                    summary += f"**{key}**:\n"
                    for sub_key, sub_value in value.items():
                        summary += f"  - {sub_key}: {sub_value}\n"
                elif isinstance(value, list):
                    summary += f"**{key}**: {len(value)} items\n"
                else:
                    summary += f"**{key}**: {value}\n"
        
        return summary
    
    async def execute(self, 
                     file_paths: List[str], 
                     context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute the wrapped tool and return results in AnalysisResult format.
        
        Args:
            file_paths: Files to analyze
            context: Context dictionary with execution parameters
            
        Returns:
            AnalysisResult with analysis results
        """
        import time
        start_time = time.time()
        
        try:
            # Extract any specific parameters from context
            kwargs = {}
            if 'check_security' in context:
                kwargs['validation_type'] = 'security'
            if 'check_methods' in context:
                kwargs['pattern_types'] = ['naming', 'parameters']
            
            # Execute core utility (async method)
            core_results = await self._core_utility(file_paths, **kwargs)
            
            # Check for errors in results
            if "error" in core_results:
                return AnalysisResult(
                    tool_name=self._name,
                    status=ToolStatus.FAILURE,
                    error_message=core_results["error"],
                    execution_time_seconds=time.time() - start_time
                )
            
            # Get AI interpretation if enabled
            with_ai = context.get('with_ai', True)
            if with_ai:
                ai_interpretation = await self._get_ai_interpretation(core_results, context.get('user_context'))
                # Include AI interpretation in output
                if isinstance(core_results, dict):
                    core_results['ai_interpretation'] = ai_interpretation
            
            return AnalysisResult(
                tool_name=self._name,
                status=ToolStatus.SUCCESS,
                output=core_results,
                execution_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Tool {self._name} execution failed: {e}")
            return AnalysisResult(
                tool_name=self._name,
                status=ToolStatus.FAILURE,
                error_message=str(e),
                execution_time_seconds=time.time() - start_time
            )
    
    def get_context_requirements(self) -> Optional[ToolContextRequirements]:
        """
        Get context requirements for this tool.
        Each tool specifies what context it needs and provides.
        """
        requirements_map = {
            ANALYZE_CODE: ToolContextRequirements(
                tool_name=ANALYZE_CODE,
                provides_context_types={
                    ContextType.ARCHITECTURE_PATTERN,
                    ContextType.CODE_PATTERN,
                    ContextType.AUTH_MODULE,
                    ContextType.ENTRY_POINT,
                    ContextType.CRITICAL_PATH
                },
                provides_categories={
                    ContextCategory.ARCHITECTURE,
                    ContextCategory.SECURITY,
                    ContextCategory.PERFORMANCE
                }
            ),
            CHECK_QUALITY: ToolContextRequirements(
                tool_name=CHECK_QUALITY,
                required_context_types={
                    ContextType.AUTH_MODULE,
                    ContextType.CRITICAL_PATH
                },
                optional_context_types={
                    ContextType.CODE_PATTERN,
                    ContextType.ARCHITECTURE_PATTERN
                },
                required_categories={
                    ContextCategory.SECURITY,
                    ContextCategory.ARCHITECTURE
                },
                provides_context_types={
                    ContextType.SECURITY_FINDING,
                    ContextType.PERFORMANCE_ISSUE,
                    ContextType.BUG
                },
                provides_categories={
                    ContextCategory.SECURITY,
                    ContextCategory.QUALITY,
                    ContextCategory.PERFORMANCE
                }
            ),
            CONFIG_VALIDATOR: ToolContextRequirements(
                tool_name=CONFIG_VALIDATOR,
                required_context_types={
                    ContextType.SECURITY_FINDING,
                    ContextType.AUTH_MODULE
                },
                optional_context_types={
                    ContextType.ARCHITECTURE_PATTERN
                },
                required_categories={
                    ContextCategory.SECURITY,
                    ContextCategory.CONFIGURATION
                },
                provides_context_types={
                    ContextType.SECURITY_FINDING,
                    ContextType.FINDING
                },
                provides_categories={
                    ContextCategory.SECURITY,
                    ContextCategory.CONFIGURATION
                }
            )
        }
        
        return requirements_map.get(self._name)
    
    async def process_with_context(self, 
                                   files: List[str],
                                   shared_context: List[ContextEntry],
                                   **kwargs) -> Dict[str, Any]:
        """
        Process files with shared context from other tools.
        This enhances the analysis by focusing on areas identified by previous tools.
        """
        # Filter context relevant to this tool
        requirements = self.get_context_requirements()
        if not requirements:
            # Tool doesn't use context, fall back to normal processing
            return await self._core_utility(files, **kwargs)
        
        relevant_context = [
            ctx for ctx in shared_context
            if requirements.can_use_context(ctx)
        ]
        
        if not relevant_context:
            logger.info(f"{self._name}: No relevant context found, proceeding with standard analysis")
            return await self._core_utility(files, **kwargs)
        
        logger.info(f"{self._name}: Using {len(relevant_context)} context entries to focus analysis")
        
        # Enhance analysis based on context type
        if self._name == CHECK_QUALITY:
            return await self._enhance_quality_check_with_context(files, relevant_context, **kwargs)
        elif self._name == CONFIG_VALIDATOR:
            return await self._enhance_config_validation_with_context(files, relevant_context, **kwargs)
        else:
            # Default behavior with context summary
            context_summary = self._create_context_summary(relevant_context)
            kwargs['context_summary'] = context_summary
            return await self._core_utility(files, **kwargs)
    
    async def _enhance_quality_check_with_context(self, files: List[str], context: List[ContextEntry], **kwargs):
        """Enhance quality check using context from analyze_code"""
        # Focus on files with auth modules or security patterns
        auth_modules = [ctx for ctx in context if ctx.type == ContextType.AUTH_MODULE]
        critical_paths = [ctx for ctx in context if ctx.type == ContextType.CRITICAL_PATH]
        
        if auth_modules:
            # Focus security checks on authentication modules
            auth_files = [ctx.source_file for ctx in auth_modules if ctx.source_file]
            if auth_files:
                kwargs['security_focus_files'] = auth_files
                kwargs['check_auth_patterns'] = True
                logger.info(f"{self._name}: Focusing security analysis on {len(auth_files)} auth modules")
        
        if critical_paths:
            # Focus performance checks on critical paths
            performance_files = [ctx.source_file for ctx in critical_paths if ctx.source_file]
            if performance_files:
                kwargs['performance_focus_files'] = performance_files
                logger.info(f"{self._name}: Focusing performance analysis on {len(performance_files)} critical paths")
        
        # Add context summary to help Gemini understand what to look for
        kwargs['context_summary'] = self._create_context_summary(context)
        return await self._core_utility(files, **kwargs)
    
    async def _enhance_config_validation_with_context(self, files: List[str], context: List[ContextEntry], **kwargs):
        """Enhance config validation using security findings from other tools"""
        security_findings = [ctx for ctx in context if ctx.type == ContextType.SECURITY_FINDING]
        
        if security_findings:
            # Focus on configs related to security issues
            kwargs['focus_security_configs'] = True
            
            # Extract specific issues to look for in configs
            issues_to_check = []
            for finding in security_findings:
                content = finding.content
                if 'hardcoded' in str(content).lower():
                    issues_to_check.append('hardcoded_secrets')
                if 'jwt' in str(content).lower():
                    issues_to_check.append('jwt_configuration')
                if 'database' in str(content).lower():
                    issues_to_check.append('database_credentials')
            
            if issues_to_check:
                kwargs['specific_security_checks'] = issues_to_check
                logger.info(f"{self._name}: Focusing on specific security issues: {issues_to_check}")
        
        kwargs['context_summary'] = self._create_context_summary(context)
        return await self._core_utility(files, **kwargs)
    
    def _create_context_summary(self, context_entries: List[ContextEntry]) -> str:
        """Create a summary of context for the tool to use"""
        if not context_entries:
            return ""
        
        summary = ["## Context from Previous Analysis:\n"]
        
        for entry in context_entries:
            summary.append(f"- **{entry.title}** ({entry.source_tool})")
            if entry.code_locus:
                summary.append(f"  - Location: {entry.code_locus.file_path}:{entry.code_locus.start_line}")
            if entry.content:
                # Extract key info from content
                for key, value in entry.content.items():
                    if key in ['auth_type', 'issue', 'severity', 'pattern']:
                        summary.append(f"  - {key}: {value}")
            summary.append("")
        
        return "\n".join(summary)
    
    def get_suggested_next_tools(self, result: AnalysisResult) -> List[Dict[str, Any]]:
        """
        Get suggested next tools based on analysis results.
        This enables smart triggering where tools recommend what should run next.
        
        Args:
            result: The analysis result from this tool
            
        Returns:
            List of tool suggestions with reasons
        """
        suggestions = []
        
        # Tool-specific suggestions based on findings
        if self._name == CHECK_QUALITY:
            # If security issues found, suggest config validation
            if isinstance(result.output, dict):
                output_str = str(result.output).lower()
                if 'security' in output_str or 'vulnerability' in output_str:
                    suggestions.append({
                        'tool': 'config_validator',
                        'reason': "Security issues found - check configurations",
                        'auto_run': False,
                        'params': {'validation_type': 'security'}
                    })
                    suggestions.append({
                        'tool': 'security_audit_flow',
                        'reason': "Complete security audit recommended for comprehensive analysis",
                        'auto_run': False
                    })
                
                if 'performance' in output_str or 'bottleneck' in output_str:
                    suggestions.append({
                        'tool': 'performance_profiler',
                        'reason': "Performance issues detected - profile for details",
                        'auto_run': False
                    })
        
        elif self._name == ANALYZE_CODE:
            # If architecture issues found, suggest dependency analysis
            if isinstance(result.output, dict):
                output_str = str(result.output).lower()
                if 'circular' in output_str or 'dependency' in output_str:
                    suggestions.append({
                        'tool': 'map_dependencies',
                        'reason': "Dependency issues detected - map full dependency graph",
                        'auto_run': False,
                        'params': {'analysis_depth': 'full'}
                    })
                if 'architecture' in output_str or 'pattern' in output_str:
                    suggestions.append({
                        'tool': 'architecture_review_flow', 
                        'reason': "Architecture patterns found - comprehensive review available",
                        'auto_run': False
                    })
        
        elif self._name == CONFIG_VALIDATOR:
            # If config issues found, suggest security flow
            if isinstance(result.output, dict):
                output_str = str(result.output).lower()
                if 'security' in output_str or 'credential' in output_str or 'secret' in output_str:
                    suggestions.append({
                        'tool': 'security_audit_flow',
                        'reason': "Configuration security issues - full audit recommended",
                        'auto_run': False,
                        'params': {'output_format': 'review'}
                    })
        
        elif self._name == ANALYZE_TEST_COVERAGE:
            # If low coverage, suggest test strategy flow
            if isinstance(result.output, dict):
                output_str = str(result.output).lower()
                if 'low coverage' in output_str or 'untested' in output_str or 'gap' in output_str:
                    suggestions.append({
                        'tool': 'test_strategy_flow',
                        'reason': "Test coverage gaps found - generate test strategy",
                        'auto_run': False,
                        'params': {'output_format': 'tasks'}
                    })
        
        elif self._name == PERFORMANCE_PROFILER:
            # If bottlenecks found, suggest log analysis
            if isinstance(result.output, dict):
                output_str = str(result.output).lower()
                if 'bottleneck' in output_str or 'slow' in output_str:
                    suggestions.append({
                        'tool': 'analyze_logs',
                        'reason': "Performance bottlenecks found - check logs for patterns",
                        'auto_run': False,
                        'params': {'focus': 'performance'}
                    })
        
        return suggestions
    
    def extract_context_contributions(self, result: AnalysisResult) -> List[ContextEntry]:
        """
        Extract context entries that this tool wants to share with other tools.
        """
        if not result.is_success or not result.output:
            return []
        
        context_entries = []
        
        if self._name == ANALYZE_CODE:
            context_entries.extend(self._extract_analyze_code_context(result))
        elif self._name == CHECK_QUALITY:
            context_entries.extend(self._extract_check_quality_context(result))
        elif self._name == CONFIG_VALIDATOR:
            context_entries.extend(self._extract_config_validator_context(result))
        
        return context_entries
    
    def _extract_analyze_code_context(self, result: AnalysisResult) -> List[ContextEntry]:
        """Extract shareable context from analyze_code results"""
        context_entries = []
        output = result.output
        
        if not isinstance(output, dict):
            return context_entries
        
        analysis_text = output.get('analysis', output.get('result', ''))
        if isinstance(analysis_text, str):
            # Look for authentication modules mentioned
            if 'auth' in analysis_text.lower():
                context_entries.append(ContextEntry(
                    type=ContextType.AUTH_MODULE,
                    category=ContextCategory.SECURITY,
                    priority=ContextPriority.HIGH,
                    title="Authentication Module Detected",
                    content={'detected_auth': True, 'analysis': analysis_text[:200]},
                    source_tool=self._name,
                    confidence=0.8
                ))
            
            # Look for critical paths mentioned
            if any(word in analysis_text.lower() for word in ['critical', 'bottleneck', 'performance']):
                context_entries.append(ContextEntry(
                    type=ContextType.CRITICAL_PATH,
                    category=ContextCategory.PERFORMANCE,
                    priority=ContextPriority.MEDIUM,
                    title="Performance Critical Code Detected",
                    content={'detected_performance_critical': True, 'analysis': analysis_text[:200]},
                    source_tool=self._name,
                    confidence=0.7
                ))
        
        return context_entries
    
    def _extract_check_quality_context(self, result: AnalysisResult) -> List[ContextEntry]:
        """Extract shareable context from check_quality results"""
        context_entries = []
        output = result.output
        
        if not isinstance(output, dict):
            return context_entries
        
        analysis_text = output.get('analysis', output.get('result', ''))
        if isinstance(analysis_text, str):
            # Look for security findings
            security_keywords = ['vulnerability', 'security', 'hardcoded', 'injection', 'xss']
            if any(keyword in analysis_text.lower() for keyword in security_keywords):
                priority = ContextPriority.CRITICAL if 'critical' in analysis_text.lower() else ContextPriority.HIGH
                context_entries.append(ContextEntry(
                    type=ContextType.SECURITY_FINDING,
                    category=ContextCategory.SECURITY,
                    priority=priority,
                    title="Security Issue Found",
                    content={'security_issue': True, 'details': analysis_text[:300]},
                    source_tool=self._name,
                    confidence=0.9
                ))
            
            # Look for performance issues
            perf_keywords = ['slow', 'performance', 'bottleneck', 'inefficient', 'memory']
            if any(keyword in analysis_text.lower() for keyword in perf_keywords):
                context_entries.append(ContextEntry(
                    type=ContextType.PERFORMANCE_ISSUE,
                    category=ContextCategory.PERFORMANCE,
                    priority=ContextPriority.MEDIUM,
                    title="Performance Issue Found",
                    content={'performance_issue': True, 'details': analysis_text[:300]},
                    source_tool=self._name,
                    confidence=0.8
                ))
        
        return context_entries
    
    def _extract_config_validator_context(self, result: AnalysisResult) -> List[ContextEntry]:
        """Extract shareable context from config_validator results"""
        context_entries = []
        output = result.output
        
        if not isinstance(output, dict):
            return context_entries
        
        analysis_text = output.get('analysis', output.get('result', ''))
        if isinstance(analysis_text, str):
            # Look for configuration security issues
            if 'secret' in analysis_text.lower() or 'credential' in analysis_text.lower():
                context_entries.append(ContextEntry(
                    type=ContextType.SECURITY_FINDING,
                    category=ContextCategory.CONFIGURATION,
                    priority=ContextPriority.CRITICAL,
                    title="Configuration Security Issue",
                    content={'config_security_issue': True, 'details': analysis_text[:300]},
                    source_tool=self._name,
                    confidence=0.95
                ))
        
        return context_entries