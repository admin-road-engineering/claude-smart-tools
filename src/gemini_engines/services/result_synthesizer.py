"""
Enhanced result synthesis service with context management and intelligent model selection.

Generates comprehensive synthesis reports from multiple tool results, providing
actionable insights with context-aware narrative flow and adaptive complexity handling.
"""
import json
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import Counter, defaultdict

from ..tools.interfaces import (
    IResultSynthesizer, AnalysisResult, ToolStatus,
    ResultSynthesizerConfig
)
from ..models.dialogue_models import ToolOutput, DialogueState, ErrorType, ToolStatus as NewToolStatus
from ..clients.gemini_client import GeminiClient
from ..exceptions import SynthesisError

logger = logging.getLogger(__name__)


class ResultSynthesizer(IResultSynthesizer):
    """
    Intelligent synthesis service that creates comprehensive reports from tool results.
    
    Features:
    - Context-aware synthesis with dialogue history integration
    - Intelligent model selection based on complexity and focus
    - Progressive report building with modular sections
    - Error-tolerant processing with partial result handling
    - Structured output with actionable recommendations
    """
    
    def __init__(self, 
                 gemini_client: GeminiClient,
                 config: ResultSynthesizerConfig = None):
        """
        Initialize ResultSynthesizer.
        
        Args:
            gemini_client: Configured Gemini client for AI synthesis
            config: Configuration for synthesis behavior
        """
        self.gemini_client = gemini_client
        self.config = config or ResultSynthesizerConfig()
        
        # Synthesis metrics
        self.metrics = {
            'total_syntheses': 0,
            'successful_syntheses': 0,
            'failed_syntheses': 0,
            'model_usage': Counter(),
            'average_synthesis_time': 0.0,
            'total_synthesis_time': 0.0
        }
        
        logger.info(f"ResultSynthesizer initialized with {self.config.default_model} model")
    
    async def synthesize_report(self, 
                               tool_results: Dict[str, AnalysisResult],
                               context: Optional[str] = None,
                               focus: str = "all") -> str:
        """
        Generate comprehensive synthesis report from tool results.
        
        Args:
            tool_results: Results from all executed tools (legacy format)
            context: Additional context for synthesis
            focus: Focus area for the review
            
        Returns:
            Formatted comprehensive report as Markdown string
        """
        # Convert to ToolOutput format for enhanced processing
        enhanced_results = {}
        for tool_name, result in tool_results.items():
            enhanced_results[tool_name] = self._convert_to_tool_output(result)
        
        return await self.synthesize_report_enhanced(enhanced_results, context, focus)
    
    async def synthesize_report_enhanced(self,
                                       tool_results: Dict[str, ToolOutput],
                                       context: Optional[str] = None,
                                       focus: str = "all",
                                       dialogue_state: Optional[DialogueState] = None) -> str:
        """
        Generate enhanced synthesis report with dialogue context integration.
        
        Args:
            tool_results: Enhanced tool results with ToolOutput format
            context: Additional context for synthesis
            focus: Focus area for the review
            dialogue_state: Current dialogue state for context
            
        Returns:
            Formatted comprehensive report with context-aware insights
        """
        start_time = time.time()
        
        try:
            self.metrics['total_syntheses'] += 1
            
            logger.info(f"Starting synthesis for {len(tool_results)} tool results (focus: {focus})")
            
            # Validate inputs
            if not tool_results:
                raise SynthesisError("No tool results provided for synthesis")
            
            # Select appropriate model
            model_name = self.select_synthesis_model(tool_results, focus)
            logger.info(f"Selected model: {model_name}")
            
            # Build synthesis sections
            synthesis_data = await self._build_synthesis_data(
                tool_results, context, focus, dialogue_state
            )
            
            # Generate synthesis prompt
            synthesis_prompt = self._create_synthesis_prompt(synthesis_data, focus)
            
            # Execute synthesis with selected model
            synthesis_result = await self._execute_synthesis(
                synthesis_prompt, model_name, synthesis_data
            )
            
            # Post-process and validate result
            final_report = self._post_process_synthesis_enhanced(synthesis_result, synthesis_data)
            
            # Update metrics
            execution_time = time.time() - start_time
            self._update_synthesis_metrics(model_name, execution_time, success=True)
            
            logger.info(f"Synthesis completed successfully in {execution_time:.2f}s")
            return final_report
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_synthesis_metrics("unknown", execution_time, success=False)
            
            logger.error(f"Synthesis failed after {execution_time:.2f}s: {e}")
            
            # Return fallback synthesis for partial results
            return await self._generate_fallback_synthesis(tool_results, focus, str(e))
    
    def select_synthesis_model(self, 
                              tool_results: Dict[str, ToolOutput],
                              focus: str) -> str:
        """
        Select appropriate model for synthesis based on complexity.
        
        Args:
            tool_results: Tool results to be synthesized
            focus: Review focus area
            
        Returns:
            Model name (pro, flash, flash-lite)
        """
        # Calculate complexity score
        complexity_score = self._calculate_synthesis_complexity(tool_results, focus)
        
        # Determine content size
        total_content_size = sum(
            len(str(result.summary)) + len(str(result.artifacts)) + len(str(result.recommendations))
            for result in tool_results.values()
        )
        
        # Model selection logic
        if focus in self.config.pro_model_focus_areas:
            logger.debug(f"Pro model selected for focus area: {focus}")
            return "pro"
        elif total_content_size > self.config.pro_model_threshold_chars:
            logger.debug(f"Pro model selected for large content: {total_content_size} chars")
            return "pro"
        elif complexity_score > 7:
            logger.debug(f"Flash model selected for complex synthesis: score {complexity_score}")
            return "flash"
        else:
            logger.debug(f"Flash-lite model selected for standard synthesis: score {complexity_score}")
            return self.config.default_model
    
    def _calculate_synthesis_complexity(self, 
                                      tool_results: Dict[str, ToolOutput],
                                      focus: str) -> int:
        """
        Calculate complexity score for synthesis task.
        
        Args:
            tool_results: Tool results to analyze
            focus: Review focus area
            
        Returns:
            Complexity score (1-10 scale)
        """
        complexity = 0
        
        # Base complexity from number of tools
        tool_count = len(tool_results)
        complexity += min(tool_count, 5)  # Max 5 points
        
        # Complexity from successful vs failed tools
        successful_tools = [r for r in tool_results.values() if r.is_success]
        if len(successful_tools) > 3:
            complexity += 2  # More results to synthesize
        
        # Complexity from focus area
        complex_focus_areas = ["architecture", "security", "performance"]
        if focus in complex_focus_areas:
            complexity += 2
        
        # Complexity from result richness
        rich_results = sum(1 for result in tool_results.values()
                          if len(result.artifacts) > 3 or len(result.recommendations) > 5)
        complexity += min(rich_results, 3)
        
        # Complexity from error diversity
        error_types = set(result.error_type for result in tool_results.values() 
                         if result.error_type is not None)
        complexity += min(len(error_types), 2)
        
        return min(complexity, 10)  # Cap at 10
    
    async def _build_synthesis_data(self,
                                  tool_results: Dict[str, ToolOutput],
                                  context: Optional[str],
                                  focus: str,
                                  dialogue_state: Optional[DialogueState]) -> Dict[str, Any]:
        """
        Build structured data for synthesis generation.
        
        Args:
            tool_results: Tool execution results
            context: Additional context
            focus: Review focus area
            dialogue_state: Current dialogue state
            
        Returns:
            Structured synthesis data
        """
        # Categorize results
        successful_results = {name: result for name, result in tool_results.items() 
                            if result.is_success}
        failed_results = {name: result for name, result in tool_results.items() 
                         if result.is_failure}
        
        # Extract key findings
        all_artifacts = []
        all_recommendations = []
        
        for result in successful_results.values():
            all_artifacts.extend(result.artifacts)
            all_recommendations.extend(result.recommendations)
        
        # Calculate execution statistics
        total_execution_time = sum(result.execution_time_seconds for result in tool_results.values())
        success_rate = len(successful_results) / len(tool_results) if tool_results else 0
        
        # Build focus-specific insights
        focus_insights = await self._extract_focus_insights(successful_results, focus)
        
        # Build error analysis
        error_analysis = self._analyze_execution_errors(failed_results)
        
        # Extract dialogue context if available
        dialogue_context = self._extract_dialogue_context(dialogue_state) if dialogue_state else {}
        
        return {
            'overview': {
                'total_tools': len(tool_results),
                'successful_tools': len(successful_results),
                'failed_tools': len(failed_results),
                'success_rate': success_rate,
                'total_execution_time': total_execution_time,
                'focus': focus
            },
            'successful_results': successful_results,
            'failed_results': failed_results,
            'key_findings': {
                'artifacts': all_artifacts[:20],  # Limit for prompt size
                'recommendations': all_recommendations[:15]
            },
            'focus_insights': focus_insights,
            'error_analysis': error_analysis,
            'context': context,
            'dialogue_context': dialogue_context,
            'synthesis_metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'complexity_score': self._calculate_synthesis_complexity(tool_results, focus)
            }
        }
    
    async def _extract_focus_insights(self,
                                    successful_results: Dict[str, ToolOutput],
                                    focus: str) -> Dict[str, Any]:
        """
        Extract focus-specific insights from successful tool results.
        
        Args:
            successful_results: Successfully executed tools
            focus: Review focus area
            
        Returns:
            Focus-specific insights and patterns
        """
        insights = {
            'focus_area': focus,
            'relevant_tools': [],
            'key_patterns': [],
            'priority_recommendations': []
        }
        
        # Focus-specific tool relevance mapping
        focus_tool_mapping = {
            'security': ['config_validator', 'api_contract_checker'],
            'performance': ['performance_profiler'],
            'architecture': ['dependency_mapper', 'interface_inconsistency_detector'],
            'maintainability': ['test_coverage_analyzer', 'interface_inconsistency_detector'],
            'usability': ['accessibility_checker']
        }
        
        # Identify relevant tools for this focus
        relevant_tool_names = focus_tool_mapping.get(focus, list(successful_results.keys()))
        insights['relevant_tools'] = [
            name for name in relevant_tool_names 
            if name in successful_results
        ]
        
        # Extract focus-specific patterns
        if focus == "security":
            insights['key_patterns'] = self._extract_security_patterns(successful_results)
        elif focus == "performance":
            insights['key_patterns'] = self._extract_performance_patterns(successful_results)
        elif focus == "architecture":
            insights['key_patterns'] = self._extract_architecture_patterns(successful_results)
        else:
            # General pattern extraction
            insights['key_patterns'] = self._extract_general_patterns(successful_results)
        
        # Prioritize recommendations by focus
        insights['priority_recommendations'] = self._prioritize_recommendations_by_focus(
            successful_results, focus
        )
        
        return insights
    
    def _extract_security_patterns(self, results: Dict[str, ToolOutput]) -> List[str]:
        """Extract security-specific patterns from results"""
        patterns = []
        
        for tool_name, result in results.items():
            if tool_name == 'config_validator':
                # Look for configuration security issues
                security_artifacts = [
                    artifact for artifact in result.artifacts
                    if any(keyword in str(artifact).lower() 
                          for keyword in ['secret', 'key', 'password', 'token', 'credential'])
                ]
                if security_artifacts:
                    patterns.append(f"Configuration security concerns detected in {len(security_artifacts)} items")
            
            elif tool_name == 'api_contract_checker':
                # Look for API security patterns
                api_security = [
                    artifact for artifact in result.artifacts
                    if any(keyword in str(artifact).lower()
                          for keyword in ['authentication', 'authorization', 'cors', 'validation'])
                ]
                if api_security:
                    patterns.append(f"API security patterns found in {len(api_security)} specifications")
        
        return patterns[:5]  # Limit to top 5 patterns
    
    def _extract_performance_patterns(self, results: Dict[str, ToolOutput]) -> List[str]:
        """Extract performance-specific patterns from results"""
        patterns = []
        
        for tool_name, result in results.items():
            if tool_name == 'performance_profiler':
                # Look for performance bottlenecks
                bottlenecks = [
                    artifact for artifact in result.artifacts
                    if any(keyword in str(artifact).lower()
                          for keyword in ['slow', 'bottleneck', 'memory', 'cpu', 'latency'])
                ]
                if bottlenecks:
                    patterns.append(f"Performance bottlenecks identified in {len(bottlenecks)} areas")
        
        return patterns[:5]
    
    def _extract_architecture_patterns(self, results: Dict[str, ToolOutput]) -> List[str]:
        """Extract architecture-specific patterns from results"""
        patterns = []
        
        for tool_name, result in results.items():
            if tool_name == 'dependency_mapper':
                # Look for architectural patterns
                arch_artifacts = [
                    artifact for artifact in result.artifacts
                    if any(keyword in str(artifact).lower()
                          for keyword in ['circular', 'coupling', 'cohesion', 'dependency'])
                ]
                if arch_artifacts:
                    patterns.append(f"Architectural patterns found in {len(arch_artifacts)} components")
            
            elif tool_name == 'interface_inconsistency_detector':
                # Look for consistency patterns
                consistency_issues = [
                    artifact for artifact in result.artifacts
                    if 'inconsistent' in str(artifact).lower()
                ]
                if consistency_issues:
                    patterns.append(f"Interface consistency issues in {len(consistency_issues)} areas")
        
        return patterns[:5]
    
    def _extract_general_patterns(self, results: Dict[str, ToolOutput]) -> List[str]:
        """Extract general patterns from all results"""
        patterns = []
        
        # Count artifacts by type/category
        artifact_categories = defaultdict(int)
        for result in results.values():
            for artifact in result.artifacts:
                artifact_str = str(artifact).lower()
                if 'error' in artifact_str or 'issue' in artifact_str:
                    artifact_categories['issues'] += 1
                elif 'warning' in artifact_str:
                    artifact_categories['warnings'] += 1
                elif 'improvement' in artifact_str or 'optimization' in artifact_str:
                    artifact_categories['improvements'] += 1
        
        for category, count in artifact_categories.items():
            if count > 0:
                patterns.append(f"{count} {category} identified across tools")
        
        return patterns[:5]
    
    def _prioritize_recommendations_by_focus(self,
                                           results: Dict[str, ToolOutput], 
                                           focus: str) -> List[str]:
        """Prioritize recommendations based on focus area"""
        all_recommendations = []
        
        for tool_name, result in results.items():
            for rec in result.recommendations:
                rec_str = str(rec).lower()
                priority_score = 1
                
                # Boost priority based on focus
                if focus == "security" and any(keyword in rec_str 
                                             for keyword in ['security', 'auth', 'encrypt', 'validate']):
                    priority_score = 3
                elif focus == "performance" and any(keyword in rec_str
                                                  for keyword in ['performance', 'optimize', 'cache', 'speed']):
                    priority_score = 3
                elif focus == "architecture" and any(keyword in rec_str
                                                   for keyword in ['architecture', 'design', 'structure', 'pattern']):
                    priority_score = 3
                
                all_recommendations.append((priority_score, rec, tool_name))
        
        # Sort by priority and return top recommendations
        sorted_recs = sorted(all_recommendations, key=lambda x: x[0], reverse=True)
        return [f"{rec} (from {tool})" for _, rec, tool in sorted_recs[:10]]
    
    def _analyze_execution_errors(self, failed_results: Dict[str, ToolOutput]) -> Dict[str, Any]:
        """Analyze execution errors and provide insights"""
        if not failed_results:
            return {'error_count': 0, 'error_summary': 'No execution errors'}
        
        error_analysis = {
            'error_count': len(failed_results),
            'error_types': Counter(),
            'retryable_count': 0,
            'user_action_required': 0,
            'error_summary': '',
            'recommendations': []
        }
        
        for tool_name, result in failed_results.items():
            if result.error_type:
                error_analysis['error_types'][result.error_type.value] += 1
                
                if result.error_type in [ErrorType.TRANSIENT, ErrorType.INTERNAL]:
                    error_analysis['retryable_count'] += 1
                elif result.error_type == ErrorType.USER_INPUT:
                    error_analysis['user_action_required'] += 1
        
        # Generate error summary
        if error_analysis['retryable_count'] > 0:
            error_analysis['recommendations'].append(
                f"{error_analysis['retryable_count']} tools can be retried"
            )
        
        if error_analysis['user_action_required'] > 0:
            error_analysis['recommendations'].append(
                f"{error_analysis['user_action_required']} tools need user input fixes"
            )
        
        error_analysis['error_summary'] = f"{len(failed_results)} tools failed: " + \
            ", ".join(f"{count} {error_type}" for error_type, count in error_analysis['error_types'].items())
        
        return error_analysis
    
    def _extract_dialogue_context(self, dialogue_state: DialogueState) -> Dict[str, Any]:
        """Extract relevant context from dialogue state"""
        return {
            'current_round': dialogue_state.current_round,
            'max_rounds': dialogue_state.max_rounds,
            'total_tools_executed': len(dialogue_state.executed_tools),
            'session_focus': dialogue_state.focus,
            'files_analyzed': dialogue_state.file_paths,
            'synthesis_available': dialogue_state.synthesis_available,
            'session_status': dialogue_state.status
        }
    
    def _extract_code_context(self, file_path: str, line_number: int, context_lines: int = 2) -> Dict[str, Any]:
        """
        Extract code context around a specific line.
        
        Args:
            file_path: Path to the file
            line_number: Line number where the issue is found
            context_lines: Number of lines before/after to include
            
        Returns:
            Dictionary with code context
        """
        try:
            import os
            if not os.path.exists(file_path):
                return {
                    'available': False,
                    'reason': 'File not found'
                }
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Calculate line range
            start_line = max(0, line_number - context_lines - 1)  # -1 for 0-based indexing
            end_line = min(len(lines), line_number + context_lines)
            
            # Extract context
            context = {
                'available': True,
                'file': file_path,
                'issue_line': line_number,
                'code_snippet': {
                    'before': [],
                    'issue': '',
                    'after': []
                }
            }
            
            # Extract lines before
            for i in range(start_line, line_number - 1):
                context['code_snippet']['before'].append({
                    'line_number': i + 1,
                    'content': lines[i].rstrip()
                })
            
            # Extract issue line
            if 0 <= line_number - 1 < len(lines):
                context['code_snippet']['issue'] = {
                    'line_number': line_number,
                    'content': lines[line_number - 1].rstrip()
                }
            
            # Extract lines after
            for i in range(line_number, end_line):
                context['code_snippet']['after'].append({
                    'line_number': i + 1,
                    'content': lines[i].rstrip()
                })
            
            return context
            
        except Exception as e:
            logger.warning(f"Failed to extract code context from {file_path}:{line_number}: {e}")
            return {
                'available': False,
                'reason': str(e)
            }
    
    def _create_synthesis_prompt(self, synthesis_data: Dict[str, Any], focus: str) -> str:
        """
        Create synthesis prompt for Gemini model.
        
        Args:
            synthesis_data: Structured synthesis data
            focus: Review focus area
            
        Returns:
            Formatted synthesis prompt
        """
        overview = synthesis_data['overview']
        key_findings = synthesis_data['key_findings']
        focus_insights = synthesis_data['focus_insights']
        error_analysis = synthesis_data['error_analysis']
        dialogue_context = synthesis_data['dialogue_context']
        
        prompt = f"""# Comprehensive Code Review Synthesis

You are an expert technical reviewer creating a comprehensive synthesis report from multiple analysis tools.

## Analysis Overview
- **Focus Area**: {focus}
- **Tools Executed**: {overview['total_tools']} ({overview['successful_tools']} successful, {overview['failed_tools']} failed)
- **Success Rate**: {overview['success_rate']:.1%}
- **Execution Time**: {overview['total_execution_time']:.1f} seconds"""
        
        # Add dialogue context if available
        if dialogue_context:
            prompt += f"""
- **Review Round**: {dialogue_context['current_round']}/{dialogue_context['max_rounds']}
- **Files Analyzed**: {len(dialogue_context['files_analyzed'])} files"""
        
        prompt += f"""

## Key Findings Summary
**Artifacts Identified**: {len(key_findings['artifacts'])} findings
**Recommendations Generated**: {len(key_findings['recommendations'])} recommendations

### Focus-Specific Insights ({focus.title()})
**Relevant Tools**: {', '.join(focus_insights['relevant_tools'])}
**Key Patterns**: 
{chr(10).join(f"- {pattern}" for pattern in focus_insights['key_patterns'])}

**Priority Recommendations**:
{chr(10).join(f"- {rec}" for rec in focus_insights['priority_recommendations'][:5])}

### Execution Analysis
{error_analysis['error_summary']}
{chr(10).join(f"- {rec}" for rec in error_analysis.get('recommendations', []))}

## Detailed Tool Results

### Successful Tools"""
        
        # Add successful tool details
        for tool_name, result in synthesis_data['successful_results'].items():
            prompt += f"""

**{tool_name.replace('_', ' ').title()}**
- Summary: {result.summary}
- Key Findings: {len(result.artifacts)} artifacts, {len(result.recommendations)} recommendations
- Execution: {result.execution_time_seconds:.1f}s"""
            
            if result.artifacts:
                prompt += f"\n- Top Findings: {str(result.artifacts[:3])}"
        
        # Add failed tool information
        if synthesis_data['failed_results']:
            prompt += f"""

### Failed Tools"""
            for tool_name, result in synthesis_data['failed_results'].items():
                prompt += f"""
**{tool_name.replace('_', ' ').title()}**: {result.error_message} ({result.error_type.value if result.error_type else 'unknown'})"""
        
        # Add context if provided
        if synthesis_data['context']:
            prompt += f"""

## Additional Context
{synthesis_data['context']}"""
        
        prompt += f"""

## Synthesis Instructions

Generate a comprehensive technical review report in Markdown format with:

1. **Executive Summary** (2-3 paragraphs)
   - Overall assessment of code quality and architecture
   - Key strengths and areas for improvement
   - Priority recommendations based on {focus} focus

2. **Detailed Findings** (organized by category)
   - Security issues and recommendations
   - Performance concerns and optimizations  
   - Architecture and design patterns
   - Code quality and maintainability
   - Testing and reliability

3. **Action Items** (prioritized list with code context)
   - High priority issues requiring immediate attention
     - Include specific file:line references
     - Show 2-3 lines of context before/after the issue
   - Medium priority improvements for next iteration
   - Long-term architectural considerations

4. **Next Steps**
   - Recommended follow-up analysis if tools failed
   - Suggested development workflow improvements
   - Monitoring and validation strategies

**Requirements**:
- Focus on actionable insights, not just problem identification
- Provide context for why issues matter (business/technical impact)
- Include code examples or specific file references when relevant
- Maintain technical accuracy while being accessible
- Prioritize findings based on the {focus} focus area
- Be concise but comprehensive - aim for 800-1500 words

Generate the synthesis report now:"""
        
        return prompt
    
    async def _execute_synthesis(self,
                               prompt: str,
                               model_name: str,
                               synthesis_data: Dict[str, Any]) -> str:
        """Execute synthesis with selected model and error handling"""
        try:
            # Calculate timeout based on complexity
            complexity_score = synthesis_data['synthesis_metadata']['complexity_score']
            timeout = min(self.config.timeout_seconds + (complexity_score * 10), 300)  # Max 5 minutes
            
            logger.debug(f"Executing synthesis with {model_name} model (timeout: {timeout}s)")
            
            # Execute synthesis request
            # generate_content returns a tuple: (text, model_name, attempts)
            synthesis_response = await asyncio.wait_for(
                self.gemini_client.generate_content(
                    prompt=prompt,
                    model_name=model_name
                ),
                timeout=timeout
            )
            
            # Unpack the tuple - we need the text content
            if isinstance(synthesis_response, tuple):
                synthesis_result = synthesis_response[0]  # Get the text content
                used_model = synthesis_response[1] if len(synthesis_response) > 1 else model_name
                logger.debug(f"Synthesis completed with model: {used_model}")
            else:
                # Fallback if response format changes
                synthesis_result = synthesis_response
            
            if not synthesis_result or len(synthesis_result.strip()) < 100:
                raise SynthesisError("Synthesis result too short or empty")
            
            return synthesis_result
            
        except asyncio.TimeoutError:
            raise SynthesisError(f"Synthesis timed out after {timeout}s with {model_name}")
        except Exception as e:
            raise SynthesisError(f"Synthesis execution failed with {model_name}: {str(e)}")
    
    def _post_process_synthesis_enhanced(self, synthesis_result: str, synthesis_data: Dict[str, Any]) -> str:
        """Post-process synthesis result and add metadata"""
        
        # Validate synthesis result
        if len(synthesis_result.strip()) < 50:
            raise SynthesisError("Synthesis result too short")
        
        # Add metadata footer
        metadata_footer = f"""

---

**Synthesis Metadata**
- Generated: {synthesis_data['synthesis_metadata']['timestamp']}
- Tools Analyzed: {synthesis_data['overview']['total_tools']} ({synthesis_data['overview']['successful_tools']} successful)
- Focus: {synthesis_data['overview']['focus'].title()}
- Complexity Score: {synthesis_data['synthesis_metadata']['complexity_score']}/10

*This synthesis was generated by the Claude-Gemini MCP Collaborative Review System*"""
        
        return synthesis_result.strip() + metadata_footer
    
    async def _generate_fallback_synthesis(self,
                                         tool_results: Dict[str, ToolOutput],
                                         focus: str,
                                         error_message: str) -> str:
        """Generate fallback synthesis when main synthesis fails"""
        
        logger.warning("Generating fallback synthesis due to synthesis failure")
        
        successful_results = {name: result for name, result in tool_results.items() 
                            if result.is_success}
        failed_results = {name: result for name, result in tool_results.items() 
                         if result.is_failure}
        
        fallback_report = f"""# Code Review Synthesis Report (Fallback Mode)

## Executive Summary
Analysis completed with {len(successful_results)} successful tools and {len(failed_results)} failed tools.
Focus area: **{focus.title()}**

⚠️ **Note**: This is a simplified synthesis due to processing error: {error_message}

## Successful Tool Results
"""
        
        for tool_name, result in successful_results.items():
            fallback_report += f"""
### {tool_name.replace('_', ' ').title()}
- **Summary**: {result.summary}
- **Findings**: {len(result.artifacts)} artifacts identified
- **Recommendations**: {len(result.recommendations)} recommendations
- **Execution Time**: {result.execution_time_seconds:.1f}s

**Key Recommendations**:
{chr(10).join(f"- {rec}" for rec in result.recommendations[:3])}
"""
        
        if failed_results:
            fallback_report += f"""
## Failed Tools
{chr(10).join(f"- **{name}**: {result.error_message}" for name, result in failed_results.items())}

## Recommended Actions
1. Review and retry failed tools if possible
2. Address any configuration or input issues
3. Consider running additional analysis tools
"""
        
        fallback_report += f"""
## Next Steps
- Address failed tool issues to get complete analysis
- Focus on {focus} improvements based on successful results
- Consider re-running synthesis once all tools complete successfully

---
*Fallback synthesis generated at {datetime.now(timezone.utc).isoformat()}*
"""
        
        return fallback_report
    
    def _convert_to_tool_output(self, result: AnalysisResult) -> ToolOutput:
        """Convert legacy AnalysisResult to ToolOutput format"""
        
        # Parse artifacts and recommendations from string output if needed
        if isinstance(result.output, dict):
            # Already structured - use as-is
            summary = result.output.get('summary', '')
            artifacts = result.output.get('artifacts', [])
            recommendations = result.output.get('recommendations', [])
        else:
            # Parse from string output (this was the bug - always returned empty lists)
            output_str = str(result.output)
            summary = self._extract_summary_from_output(output_str)
            artifacts = self._parse_artifacts_from_string(output_str)
            recommendations = self._parse_recommendations_from_string(output_str)
        
        return ToolOutput(
            tool_name=result.tool_name,
            status=NewToolStatus.SUCCESS if result.is_success else NewToolStatus.FAILURE,
            summary=summary,
            artifacts=artifacts,
            recommendations=recommendations,
            execution_time_seconds=result.execution_time_seconds,
            error_message=result.error_message if result.is_failure else None
        )
    
    def _extract_summary_from_output(self, output_str: str) -> str:
        """Extract a brief summary from tool output string"""
        if not output_str:
            return ""
        
        # Take first non-empty line or first 200 chars as summary
        lines = [line.strip() for line in output_str.split('\n') if line.strip()]
        if lines:
            first_line = lines[0]
            # Remove markdown headers and formatting
            first_line = first_line.lstrip('# ').lstrip('## ').lstrip('### ')
            return first_line[:200] + "..." if len(first_line) > 200 else first_line
        return output_str[:200] + "..." if len(output_str) > 200 else output_str
    
    def _parse_artifacts_from_string(self, output_str: str) -> List[Dict[str, Any]]:
        """Parse artifacts/findings from tool output string"""
        artifacts = []
        
        try:
            # Try to parse as JSON first (for tools that return JSON)
            import json
            import re
            
            # Look for JSON arrays or objects in the output
            json_pattern = r'```json\s*(\[.*?\])\s*```|```json\s*(\{.*?\})\s*```'
            json_matches = re.findall(json_pattern, output_str, re.DOTALL)
            
            for match in json_matches:
                json_str = match[0] or match[1]  # One of the groups will be empty
                try:
                    parsed_json = json.loads(json_str)
                    if isinstance(parsed_json, list):
                        # List of findings
                        for item in parsed_json:
                            if isinstance(item, dict):
                                artifacts.append(item)
                            else:
                                artifacts.append({"finding": str(item), "type": "general"})
                    elif isinstance(parsed_json, dict):
                        artifacts.append(parsed_json)
                except json.JSONDecodeError:
                    continue
            
            # If we found JSON artifacts, return them
            if artifacts:
                return artifacts
            
            # Fallback: Parse text-based findings
            lines = output_str.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for issue patterns
                issue_patterns = [
                    r'- \*\*(.*?)\*\*:?\s*(.*)',  # Markdown bold items
                    r'^\d+\.\s+(.+)',  # Numbered list items  
                    r'^[-*]\s+(.+)',  # Bullet points
                    r'(ERROR|WARNING|CRITICAL|INFO):\s*(.+)',  # Log-style entries
                    r'file:\s*(.+?),.*?line.*?(\d+).*?(.+)',  # File/line references
                    r'Finding:\s*(.+)',  # Explicit findings
                    r'Issue:\s*(.+)',  # Explicit issues
                ]
                
                for pattern in issue_patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        groups = match.groups()
                        if len(groups) >= 2:
                            artifacts.append({
                                "type": groups[0].lower() if groups[0] else "finding",
                                "description": groups[1] if len(groups) > 1 else groups[0],
                                "source": "parsed_text"
                            })
                        elif len(groups) == 1:
                            artifacts.append({
                                "type": "finding", 
                                "description": groups[0],
                                "source": "parsed_text"
                            })
                        break
            
            # Look for sections with findings
            sections_with_findings = []
            current_section = ""
            
            for line in lines:
                line = line.strip()
                
                # Detect section headers
                if line.startswith('##') or line.startswith('#'):
                    current_section = line.lstrip('#').strip()
                elif line.startswith('**') and line.endswith('**'):
                    current_section = line.strip('*')
                elif current_section and line and not line.startswith('-'):
                    # Content in section
                    if any(keyword in line.lower() for keyword in 
                          ['error', 'issue', 'problem', 'warning', 'critical', 'missing', 'invalid', 'fail']):
                        sections_with_findings.append({
                            "type": "section_finding",
                            "section": current_section,
                            "description": line,
                            "source": "section_parse"
                        })
            
            artifacts.extend(sections_with_findings)
            
        except Exception as e:
            # Fallback: create basic artifact from output
            logger.debug(f"Artifact parsing failed: {e}")
            if output_str and len(output_str.strip()) > 0:
                artifacts.append({
                    "type": "raw_output",
                    "description": output_str[:500] + "..." if len(output_str) > 500 else output_str,
                    "source": "fallback_parse"
                })
        
        return artifacts
    
    def _parse_recommendations_from_string(self, output_str: str) -> List[str]:
        """Parse recommendations from tool output string"""
        recommendations = []
        
        try:
            import re
            
            lines = output_str.split('\n')
            in_recommendations_section = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detect recommendation sections
                if re.search(r'(recommendation|action|suggest|fix|improve|address)', line.lower()) and \
                   (line.startswith('#') or line.startswith('**') or ':' in line):
                    in_recommendations_section = True
                    continue
                
                # Parse recommendation items
                rec_patterns = [
                    r'^\d+\.\s*(.+)',  # Numbered recommendations
                    r'^[-*]\s*(.+)',   # Bullet recommendations  
                    r'^\s*-\s*(.+)',   # Indented bullets
                    r'Recommendation:\s*(.+)',  # Explicit recommendations
                    r'Action:\s*(.+)',  # Action items
                    r'Fix:\s*(.+)',    # Fix suggestions
                    r'Consider:\s*(.+)',  # Considerations
                    r'Should:\s*(.+)',    # Should statements
                ]
                
                for pattern in rec_patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        recommendation = match.group(1).strip()
                        if len(recommendation) > 10:  # Filter out very short items
                            recommendations.append(recommendation)
                        break
                
                # Look for imperative statements (typical recommendations)
                imperative_patterns = [
                    r'^(Add|Remove|Fix|Update|Implement|Use|Avoid|Consider|Ensure|Check|Review|Replace|Refactor)\s+(.+)',
                    r'^(Make sure|Be sure|Don\'t forget)\s+(.+)',
                ]
                
                for pattern in imperative_patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match and len(line) > 15:  # Reasonable length
                        recommendations.append(line)
                        break
            
            # Remove duplicates while preserving order
            seen = set()
            unique_recommendations = []
            for rec in recommendations:
                rec_lower = rec.lower()
                if rec_lower not in seen and len(rec.strip()) > 10:
                    seen.add(rec_lower)
                    unique_recommendations.append(rec.strip())
            
            return unique_recommendations[:15]  # Limit to 15 recommendations
            
        except Exception as e:
            logger.debug(f"Recommendation parsing failed: {e}")
            return []
    
    def _update_synthesis_metrics(self, model_name: str, execution_time: float, success: bool):
        """Update synthesis metrics"""
        self.metrics['model_usage'][model_name] += 1
        self.metrics['total_synthesis_time'] += execution_time
        
        if success:
            self.metrics['successful_syntheses'] += 1
        else:
            self.metrics['failed_syntheses'] += 1
        
        # Update average synthesis time
        total_syntheses = self.metrics['total_syntheses']
        if total_syntheses > 0:
            self.metrics['average_synthesis_time'] = self.metrics['total_synthesis_time'] / total_syntheses
    
    def get_synthesis_metrics(self) -> Dict[str, Any]:
        """Get synthesis performance metrics"""
        total_syntheses = self.metrics['total_syntheses']
        success_rate = (self.metrics['successful_syntheses'] / total_syntheses) if total_syntheses > 0 else 0
        
        return {
            **self.metrics,
            'success_rate': success_rate,
            'config': {
                'default_model': self.config.default_model,
                'pro_model_threshold_chars': self.config.pro_model_threshold_chars,
                'pro_model_focus_areas': self.config.pro_model_focus_areas,
                'timeout_seconds': self.config.timeout_seconds
            }
        }
    
    def reset_metrics(self):
        """Reset synthesis metrics"""
        self.metrics = {
            'total_syntheses': 0,
            'successful_syntheses': 0,
            'failed_syntheses': 0,
            'model_usage': Counter(),
            'average_synthesis_time': 0.0,
            'total_synthesis_time': 0.0
        }
        logger.info("Synthesis metrics reset")
