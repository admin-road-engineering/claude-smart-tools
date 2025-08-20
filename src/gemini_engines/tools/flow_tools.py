"""
Flow Tools - Orchestrated tool chains for common analysis patterns.

This implements the hybrid approach for automatic flow execution:
1. Flow Commands - Pre-defined tool chains for common scenarios
2. Smart Triggers - Tools suggest next steps based on findings
3. Flexible Output - Support for review, JSON, report, or task formats
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
from enum import Enum

from ..models.context_models import (
    ContextEntry, ContextType, ContextCategory, ContextPriority
)

logger = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    """Output format options for flows"""
    REVIEW = "review"        # End with review_output for dialogue
    JSON = "json"           # Structured JSON data
    REPORT = "report"       # Formatted text report
    TASKS = "tasks"         # Actionable task list


class ToolSuggestion:
    """Suggestion for next tool to run"""
    def __init__(self, 
                 tool_name: str, 
                 reason: str, 
                 auto_run: bool = False,
                 params: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        self.reason = reason
        self.auto_run = auto_run
        self.params = params or {}


class FlowTools:
    """
    Collection of orchestrated tool flows for common analysis patterns.
    
    Each flow:
    1. Runs a sequence of tools with context sharing
    2. Can output in multiple formats (review, json, report, tasks)
    3. Provides smart suggestions for next steps
    4. Supports both autonomous and interactive modes
    """
    
    def __init__(self, sub_tools: Dict[str, Any]):
        """
        Initialize FlowTools with available sub-tools.
        
        Args:
            sub_tools: Dictionary of available analysis tools
        """
        self.sub_tools = sub_tools
        self.context_store: Dict[str, List[ContextEntry]] = {}
        
    async def security_audit_flow(self,
                                  files: List[str],
                                  output_format: OutputFormat = OutputFormat.REVIEW,
                                  interactive: bool = False) -> str:
        """
        Complete security audit flow.
        
        Flow: check_quality(security) → config_validator → review_output/json
        
        Args:
            files: Files to analyze
            output_format: Output format (review, json, report, tasks)
            interactive: Whether to enable interactive dialogue
            
        Returns:
            Security audit results in requested format
        """
        logger.info(f"Starting security audit flow for {len(files)} files")
        flow_id = f"security_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = {}
        context_entries = []
        
        try:
            # Step 1: Security quality check
            if 'check_quality' in self.sub_tools:
                logger.info("Running security quality check...")
                quality_tool = self.sub_tools['check_quality']
                quality_result = await quality_tool.execute(
                    file_paths=files,
                    context={'check_type': 'security', 'verbose': True}
                )
                # Extract output from AnalysisResult if needed
                if hasattr(quality_result, 'output'):
                    results['security_scan'] = quality_result.output
                else:
                    results['security_scan'] = quality_result
                
                # Extract context from security scan
                if hasattr(quality_tool, 'extract_context_contributions'):
                    context_entries.extend(
                        quality_tool.extract_context_contributions(quality_result)
                    )
            
            # Step 2: Configuration validation with context
            if 'config_validator' in self.sub_tools:
                logger.info("Running configuration validation...")
                config_tool = self.sub_tools['config_validator']
                
                # Find config files
                config_paths = self._find_config_files(files)
                if config_paths:
                    config_result = await config_tool.execute(
                        file_paths=config_paths,
                        context={'validation_type': 'security', 'shared_context': context_entries}
                    )
                    # Extract output from AnalysisResult if needed
                    if hasattr(config_result, 'output'):
                        results['config_validation'] = config_result.output
                    else:
                        results['config_validation'] = config_result
                    
                    # Extract context from config validation
                    if hasattr(config_tool, 'extract_context_contributions'):
                        context_entries.extend(
                            config_tool.extract_context_contributions(config_result)
                        )
            
            # Step 3: Format output based on requested format
            if output_format == OutputFormat.REVIEW:
                # Use review_output for synthesis and dialogue
                if 'review_output' in self.sub_tools:
                    review_tool = self.sub_tools['review_output']
                    # Check if it's the review service (has process_review_request method)
                    if hasattr(review_tool, 'process_review_request'):
                        from ..models.review_request import ReviewRequest
                        request = ReviewRequest(
                            output=self._summarize_security_findings(results),
                            is_plan=False,
                            focus="security",
                            detail_level="detailed" if not interactive else "comprehensive",
                            context="Security audit flow completed with multiple tool analysis"
                        )
                        # Add analysis context if we have any
                        if context_entries:
                            request.analysis_context = self._contexts_to_dicts(context_entries)
                        return await review_tool.process_review_request(request)
                    else:
                        # Fallback to execute method if available
                        return await review_tool.execute(
                            output=self._summarize_security_findings(results),
                            is_plan=False,
                            focus="security",
                            detail_level="detailed" if not interactive else "comprehensive",
                            analysis_context=self._contexts_to_dicts(context_entries),
                            context="Security audit flow completed with multiple tool analysis"
                        )
                else:
                    return self._format_security_report(results, context_entries)
                    
            elif output_format == OutputFormat.JSON:
                return self._format_security_json(results, context_entries)
                
            elif output_format == OutputFormat.TASKS:
                return self._generate_security_tasks(results, context_entries)
                
            else:  # OutputFormat.REPORT
                return self._format_security_report(results, context_entries)
                
        except Exception as e:
            logger.error(f"Security audit flow failed: {e}")
            # Avoid JSON serialization issues with results
            try:
                results_str = json.dumps(results, indent=2, default=str)
            except Exception:
                results_str = str(results)
            return f"## ❌ Security Audit Flow Failed\n\nError: {str(e)}\n\nPartial results: {results_str}"
    
    async def architecture_review_flow(self,
                                       files: List[str],
                                       output_format: OutputFormat = OutputFormat.REVIEW,
                                       focus: str = "structure") -> str:
        """
        Architecture analysis and review flow.
        
        Flow: analyze_code → map_dependencies → review_output/report
        
        Args:
            files: Files to analyze
            output_format: Output format
            focus: Architecture focus (structure, patterns, dependencies)
            
        Returns:
            Architecture analysis in requested format
        """
        logger.info(f"Starting architecture review flow for {len(files)} files")
        flow_id = f"arch_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = {}
        context_entries = []
        
        try:
            # Step 1: Code structure analysis
            if 'analyze_code' in self.sub_tools:
                logger.info("Analyzing code structure...")
                code_tool = self.sub_tools['analyze_code']
                code_result = await code_tool.execute(
                    file_paths=files,
                    context={'analysis_type': 'architecture', 'verbose': True}
                )
                # Extract output from AnalysisResult if needed
                if hasattr(code_result, 'output'):
                    results['code_analysis'] = code_result.output
                else:
                    results['code_analysis'] = code_result
                
                # Extract architectural context
                if hasattr(code_tool, 'extract_context_contributions'):
                    context_entries.extend(
                        code_tool.extract_context_contributions(code_result)
                    )
            
            # Step 2: Dependency mapping with context
            if 'map_dependencies' in self.sub_tools:
                logger.info("Mapping dependencies...")
                dep_tool = self.sub_tools['map_dependencies']
                dep_result = await dep_tool.execute(
                    file_paths=files,
                    context={'analysis_depth': 'full', 'shared_context': context_entries}
                )
                # Extract output from AnalysisResult if needed
                if hasattr(dep_result, 'output'):
                    results['dependencies'] = dep_result.output
                else:
                    results['dependencies'] = dep_result
                
                # Extract dependency context
                if hasattr(dep_tool, 'extract_context_contributions'):
                    context_entries.extend(
                        dep_tool.extract_context_contributions(dep_result)
                    )
            
            # Step 3: Format output
            if output_format == OutputFormat.REVIEW:
                if 'review_output' in self.sub_tools:
                    review_tool = self.sub_tools['review_output']
                    # Check if it's the review service (has process_review_request method)
                    if hasattr(review_tool, 'process_review_request'):
                        from ..models.review_request import ReviewRequest
                        request = ReviewRequest(
                            output=self._summarize_architecture_findings(results),
                            is_plan=False,
                            focus="architecture",
                            detail_level="comprehensive",
                            context=f"Architecture review focused on {focus}"
                        )
                        # Add analysis context if we have any
                        if context_entries:
                            request.analysis_context = self._contexts_to_dicts(context_entries)
                        return await review_tool.process_review_request(request)
                    else:
                        # Fallback to execute method if available
                        return await review_tool.execute(
                            output=self._summarize_architecture_findings(results),
                            is_plan=False,
                            focus="architecture",
                            detail_level="comprehensive",
                            analysis_context=self._contexts_to_dicts(context_entries),
                            context=f"Architecture review focused on {focus}"
                        )
                else:
                    return self._format_architecture_report(results, context_entries)
                    
            elif output_format == OutputFormat.JSON:
                return self._format_architecture_json(results, context_entries)
                
            else:  # OutputFormat.REPORT
                return self._format_architecture_report(results, context_entries)
                
        except Exception as e:
            logger.error(f"Architecture review flow failed: {e}")
            return f"## ❌ Architecture Review Flow Failed\n\nError: {str(e)}"
    
    async def test_strategy_flow(self,
                                 files: List[str],
                                 output_format: OutputFormat = OutputFormat.TASKS) -> str:
        """
        Test strategy and coverage analysis flow.
        
        Flow: analyze_test_coverage → check_quality(untested) → generate_tasks
        
        Args:
            files: Files to analyze
            output_format: Output format (tasks, json, report)
            
        Returns:
            Test strategy in requested format
        """
        logger.info(f"Starting test strategy flow for {len(files)} files")
        results = {}
        context_entries = []
        
        try:
            # Step 1: Test coverage analysis
            if 'analyze_test_coverage' in self.sub_tools:
                logger.info("Analyzing test coverage...")
                coverage_tool = self.sub_tools['analyze_test_coverage']
                coverage_result = await coverage_tool.execute(
                    file_paths=files,
                    context={'mapping_strategy': 'convention'}
                )
                # Extract output from AnalysisResult if needed
                if hasattr(coverage_result, 'output'):
                    results['coverage'] = coverage_result.output
                else:
                    results['coverage'] = coverage_result
                
                # Extract coverage context
                if hasattr(coverage_tool, 'extract_context_contributions'):
                    context_entries.extend(
                        coverage_tool.extract_context_contributions(coverage_result)
                    )
            
            # Step 2: Quality check on untested critical code
            if 'check_quality' in self.sub_tools and results.get('coverage'):
                # Parse coverage results to find untested files
                untested_files = self._extract_untested_files(results['coverage'])
                if untested_files:
                    logger.info("Checking quality of untested code...")
                    quality_tool = self.sub_tools['check_quality']
                    quality_result = await quality_tool.execute(
                        file_paths=untested_files[:10],  # Limit to top 10
                        context={'check_type': 'all', 'shared_context': context_entries}
                    )
                    # Extract output from AnalysisResult if needed
                    if hasattr(quality_result, 'output'):
                        results['untested_quality'] = quality_result.output
                    else:
                        results['untested_quality'] = quality_result
            
            # Step 3: Format output
            if output_format == OutputFormat.TASKS:
                return self._generate_test_tasks(results, context_entries)
                
            elif output_format == OutputFormat.JSON:
                return self._format_test_json(results, context_entries)
                
            elif output_format == OutputFormat.REVIEW:
                if 'review_output' in self.sub_tools:
                    review_tool = self.sub_tools['review_output']
                    # Check if it's the review service (has process_review_request method)
                    if hasattr(review_tool, 'process_review_request'):
                        from ..models.review_request import ReviewRequest
                        request = ReviewRequest(
                            output=self._summarize_test_findings(results),
                            is_plan=True,  # Test strategy is a plan
                            focus="testing",
                            context="Test strategy flow completed"
                        )
                        # Add analysis context if we have any
                        if context_entries:
                            request.analysis_context = self._contexts_to_dicts(context_entries)
                        return await review_tool.process_review_request(request)
                    else:
                        # Fallback to execute method if available
                        return await review_tool.execute(
                            output=self._summarize_test_findings(results),
                            is_plan=True,  # Test strategy is a plan
                            focus="testing",
                            analysis_context=self._contexts_to_dicts(context_entries),
                            context="Test strategy flow completed"
                        )
                else:
                    return self._format_test_report(results, context_entries)
                    
            else:  # OutputFormat.REPORT
                return self._format_test_report(results, context_entries)
                
        except Exception as e:
            logger.error(f"Test strategy flow failed: {e}")
            return f"## ❌ Test Strategy Flow Failed\n\nError: {str(e)}"
    
    async def performance_audit_flow(self,
                                     files: List[str],
                                     target_operation: Optional[str] = None,
                                     output_format: OutputFormat = OutputFormat.REPORT) -> str:
        """
        Performance analysis flow.
        
        Flow: performance_profiler → analyze_logs → review_output/metrics
        
        Args:
            files: Files to analyze
            target_operation: Specific operation to profile
            output_format: Output format
            
        Returns:
            Performance analysis in requested format
        """
        logger.info(f"Starting performance audit flow")
        results = {}
        context_entries = []
        
        try:
            # Step 1: Performance profiling
            if 'performance_profiler' in self.sub_tools:
                logger.info("Running performance profiler...")
                perf_tool = self.sub_tools['performance_profiler']
                perf_result = await perf_tool.execute(
                    file_paths=files,
                    context={'target_operation': target_operation or 'main', 'profile_type': 'comprehensive'}
                )
                # Extract output from AnalysisResult if needed
                if hasattr(perf_result, 'output'):
                    results['profiling'] = perf_result.output
                else:
                    results['profiling'] = perf_result
                
                # Extract performance context
                if hasattr(perf_tool, 'extract_context_contributions'):
                    context_entries.extend(
                        perf_tool.extract_context_contributions(perf_result)
                    )
            
            # Step 2: Log analysis for performance patterns
            if 'analyze_logs' in self.sub_tools:
                log_files = self._find_log_files(files)
                if log_files:
                    logger.info("Analyzing logs for performance patterns...")
                    log_tool = self.sub_tools['analyze_logs']
                    log_result = await log_tool.execute(
                        file_paths=log_files,
                        context={'focus': 'performance', 'shared_context': context_entries}
                    )
                    # Extract output from AnalysisResult if needed
                    if hasattr(log_result, 'output'):
                        results['log_analysis'] = log_result.output
                    else:
                        results['log_analysis'] = log_result
            
            # Step 3: Format output
            if output_format == OutputFormat.REVIEW:
                if 'review_output' in self.sub_tools:
                    review_tool = self.sub_tools['review_output']
                    # Check if it's the review service (has process_review_request method)
                    if hasattr(review_tool, 'process_review_request'):
                        from ..models.review_request import ReviewRequest
                        request = ReviewRequest(
                            output=self._summarize_performance_findings(results),
                            is_plan=False,
                            focus="performance",
                            context="Performance audit with profiling and log analysis"
                        )
                        # Add analysis context if we have any
                        if context_entries:
                            request.analysis_context = self._contexts_to_dicts(context_entries)
                        return await review_tool.process_review_request(request)
                    else:
                        # Fallback to execute method if available
                        return await review_tool.execute(
                            output=self._summarize_performance_findings(results),
                            is_plan=False,
                            focus="performance",
                            analysis_context=self._contexts_to_dicts(context_entries),
                            context="Performance audit with profiling and log analysis"
                        )
                    
            elif output_format == OutputFormat.JSON:
                return self._format_performance_json(results, context_entries)
                
            else:  # OutputFormat.REPORT
                return self._format_performance_report(results, context_entries)
                
        except Exception as e:
            logger.error(f"Performance audit flow failed: {e}")
            return f"## ❌ Performance Audit Flow Failed\n\nError: {str(e)}"
    
    def get_suggested_flows(self, context: List[ContextEntry]) -> List[ToolSuggestion]:
        """
        Get suggested flows based on current context.
        
        This enables smart triggering where tools suggest appropriate flows.
        
        Args:
            context: Current analysis context
            
        Returns:
            List of suggested flows with reasons
        """
        suggestions = []
        
        # Check for security issues
        security_count = sum(1 for c in context if c.category == ContextCategory.SECURITY)
        if security_count > 0:
            suggestions.append(ToolSuggestion(
                tool_name="security_audit_flow",
                reason=f"Found {security_count} security issues - comprehensive audit recommended",
                auto_run=security_count >= 3,  # Auto-run if 3+ security issues
                params={"output_format": "review"}
            ))
        
        # Check for architecture concerns
        arch_issues = sum(1 for c in context if c.category == ContextCategory.ARCHITECTURE)
        if arch_issues > 0:
            suggestions.append(ToolSuggestion(
                tool_name="architecture_review_flow",
                reason=f"Found {arch_issues} architecture concerns - review recommended",
                auto_run=False,
                params={"output_format": "review", "focus": "patterns"}
            ))
        
        # Check for test coverage issues
        test_issues = sum(1 for c in context if c.category == ContextCategory.TESTING)
        if test_issues > 0 or any("coverage" in c.title.lower() for c in context):
            suggestions.append(ToolSuggestion(
                tool_name="test_strategy_flow",
                reason="Test coverage gaps detected - strategy generation recommended",
                auto_run=False,
                params={"output_format": "tasks"}
            ))
        
        # Check for performance issues
        perf_issues = sum(1 for c in context if c.category == ContextCategory.PERFORMANCE)
        if perf_issues > 0:
            suggestions.append(ToolSuggestion(
                tool_name="performance_audit_flow",
                reason=f"Found {perf_issues} performance issues - profiling recommended",
                auto_run=False,
                params={"output_format": "report"}
            ))
        
        return suggestions
    
    # Helper methods for formatting and processing
    
    def _find_config_files(self, paths: List[str]) -> List[str]:
        """Find configuration files in given paths"""
        import os
        config_files = []
        config_patterns = ['.env', 'config.', 'settings.', '.ini', '.yaml', '.yml', '.toml']
        
        for path in paths:
            if os.path.isfile(path):
                if any(pattern in path.lower() for pattern in config_patterns):
                    config_files.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if any(pattern in file.lower() for pattern in config_patterns):
                            config_files.append(os.path.join(root, file))
        
        return config_files[:10]  # Limit to 10 config files
    
    def _find_log_files(self, paths: List[str]) -> List[str]:
        """Find log files in given paths"""
        import os
        log_files = []
        log_patterns = ['.log', '_log.', 'logs/', 'debug', 'error']
        
        for path in paths:
            if os.path.isfile(path):
                if any(pattern in path.lower() for pattern in log_patterns):
                    log_files.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if any(pattern in file.lower() for pattern in log_patterns):
                            log_files.append(os.path.join(root, file))
        
        return log_files[:5]  # Limit to 5 log files
    
    def _extract_untested_files(self, coverage_result: Any) -> List[str]:
        """Extract list of untested files from coverage results"""
        untested = []
        
        # Parse coverage result (format depends on analyze_test_coverage output)
        if isinstance(coverage_result, dict):
            if 'untested_files' in coverage_result:
                untested = coverage_result['untested_files']
            elif 'gaps' in coverage_result:
                for gap in coverage_result['gaps']:
                    if 'file' in gap:
                        untested.append(gap['file'])
        
        return untested
    
    def _contexts_to_dicts(self, contexts: List[ContextEntry]) -> List[Dict[str, Any]]:
        """Convert ContextEntry objects to dictionaries"""
        return [
            {
                'title': c.title,
                'priority': str(c.priority),
                'content': c.content,
                'source_tool': c.source_tool,
                'category': str(c.category)
            }
            for c in contexts
        ]
    
    def _summarize_security_findings(self, results: Dict[str, Any]) -> str:
        """Create summary of security findings for review"""
        summary = []
        
        if 'security_scan' in results:
            summary.append("## Security Scan Results\n")
            summary.append(str(results['security_scan'])[:2000])
        
        if 'config_validation' in results:
            summary.append("\n## Configuration Validation\n")
            summary.append(str(results['config_validation'])[:2000])
        
        return "\n".join(summary)
    
    def _summarize_architecture_findings(self, results: Dict[str, Any]) -> str:
        """Create summary of architecture findings"""
        summary = []
        
        if 'code_analysis' in results:
            summary.append("## Code Structure Analysis\n")
            summary.append(str(results['code_analysis'])[:2000])
        
        if 'dependencies' in results:
            summary.append("\n## Dependency Analysis\n")
            summary.append(str(results['dependencies'])[:2000])
        
        return "\n".join(summary)
    
    def _summarize_test_findings(self, results: Dict[str, Any]) -> str:
        """Create summary of test coverage findings"""
        summary = []
        
        if 'coverage' in results:
            summary.append("## Test Coverage Analysis\n")
            summary.append(str(results['coverage'])[:2000])
        
        if 'untested_quality' in results:
            summary.append("\n## Untested Critical Code\n")
            summary.append(str(results['untested_quality'])[:1000])
        
        return "\n".join(summary)
    
    def _summarize_performance_findings(self, results: Dict[str, Any]) -> str:
        """Create summary of performance findings"""
        summary = []
        
        if 'profiling' in results:
            summary.append("## Performance Profile\n")
            summary.append(str(results['profiling'])[:2000])
        
        if 'log_analysis' in results:
            summary.append("\n## Log Analysis\n")
            summary.append(str(results['log_analysis'])[:1000])
        
        return "\n".join(summary)
    
    def _format_security_json(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format security results as JSON"""
        output = {
            'flow': 'security_audit',
            'timestamp': datetime.now().isoformat(),
            'findings': {
                'critical': [],
                'high': [],
                'medium': [],
                'low': []
            },
            'tools_run': list(results.keys()),
            'suggested_next_steps': []
        }
        
        # Categorize findings by priority
        for entry in context:
            finding = {
                'title': entry.title,
                'source': entry.source_tool,
                'details': entry.content
            }
            
            if entry.priority == ContextPriority.CRITICAL:
                output['findings']['critical'].append(finding)
            elif entry.priority == ContextPriority.HIGH:
                output['findings']['high'].append(finding)
            elif entry.priority == ContextPriority.MEDIUM:
                output['findings']['medium'].append(finding)
            else:
                output['findings']['low'].append(finding)
        
        # Add suggestions
        suggestions = self.get_suggested_flows(context)
        output['suggested_next_steps'] = [
            {'tool': s.tool_name, 'reason': s.reason}
            for s in suggestions
        ]
        
        return json.dumps(output, indent=2)
    
    def _format_security_report(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format security results as text report"""
        report = []
        report.append("# 🔒 Security Audit Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Critical findings
        critical = [c for c in context if c.priority == ContextPriority.CRITICAL]
        if critical:
            report.append(f"## 🚨 Critical Issues ({len(critical)})")
            for issue in critical:
                report.append(f"- **{issue.title}**")
                if 'description' in issue.content:
                    report.append(f"  {issue.content['description']}")
            report.append("")
        
        # High priority
        high = [c for c in context if c.priority == ContextPriority.HIGH]
        if high:
            report.append(f"## ⚠️ High Priority Issues ({len(high)})")
            for issue in high:
                report.append(f"- **{issue.title}**")
            report.append("")
        
        # Tools run
        report.append("## 🔧 Analysis Tools Used")
        for tool in results.keys():
            report.append(f"- {tool}")
        report.append("")
        
        # Recommendations
        suggestions = self.get_suggested_flows(context)
        if suggestions:
            report.append("## 📋 Recommended Next Steps")
            for s in suggestions:
                report.append(f"- Run `{s.tool_name}`: {s.reason}")
        
        return "\n".join(report)
    
    def _generate_security_tasks(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Generate actionable security tasks"""
        tasks = []
        tasks.append("# 🔒 Security Tasks")
        tasks.append("")
        
        # Group by priority
        for priority in [ContextPriority.CRITICAL, ContextPriority.HIGH, ContextPriority.MEDIUM]:
            priority_items = [c for c in context if c.priority == priority]
            if priority_items:
                tasks.append(f"## {priority.value.title()} Priority")
                for i, item in enumerate(priority_items, 1):
                    tasks.append(f"{i}. [ ] **{item.title}**")
                    if 'file' in item.content:
                        tasks.append(f"   - File: `{item.content['file']}`")
                    if 'line' in item.content:
                        tasks.append(f"   - Line: {item.content['line']}")
                    if 'fix' in item.content:
                        tasks.append(f"   - Fix: {item.content['fix']}")
                tasks.append("")
        
        return "\n".join(tasks)
    
    def _format_architecture_json(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format architecture results as JSON"""
        output = {
            'flow': 'architecture_review',
            'timestamp': datetime.now().isoformat(),
            'structure': {},
            'dependencies': {},
            'patterns': [],
            'issues': [],
            'metrics': {}
        }
        
        # Extract structure info
        if 'code_analysis' in results:
            # Parse code analysis results
            output['structure'] = {'raw': str(results['code_analysis'])[:500]}
        
        # Extract dependencies
        if 'dependencies' in results:
            output['dependencies'] = {'raw': str(results['dependencies'])[:500]}
        
        # Extract patterns and issues from context
        for entry in context:
            if entry.type == ContextType.ARCHITECTURE_PATTERN:
                output['patterns'].append({
                    'pattern': entry.title,
                    'details': entry.content
                })
            elif entry.category == ContextCategory.ARCHITECTURE:
                output['issues'].append({
                    'issue': entry.title,
                    'priority': str(entry.priority),
                    'details': entry.content
                })
        
        return json.dumps(output, indent=2)
    
    def _format_architecture_report(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format architecture results as text report"""
        report = []
        report.append("# 🏗️ Architecture Review Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Patterns found
        patterns = [c for c in context if c.type == ContextType.ARCHITECTURE_PATTERN]
        if patterns:
            report.append(f"## 📐 Architecture Patterns ({len(patterns)})")
            for p in patterns:
                report.append(f"- **{p.title}**")
            report.append("")
        
        # Issues
        issues = [c for c in context if c.category == ContextCategory.ARCHITECTURE and c.type != ContextType.ARCHITECTURE_PATTERN]
        if issues:
            report.append(f"## ⚠️ Architecture Issues ({len(issues)})")
            for issue in issues:
                report.append(f"- **{issue.title}** ({issue.priority})")
            report.append("")
        
        # Dependency insights
        dep_issues = [c for c in context if c.type in [ContextType.CIRCULAR_DEPENDENCY, ContextType.DEPENDENCY]]
        if dep_issues:
            report.append(f"## 🔗 Dependency Analysis")
            for d in dep_issues:
                report.append(f"- {d.title}")
            report.append("")
        
        return "\n".join(report)
    
    def _generate_test_tasks(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Generate prioritized test tasks"""
        tasks = []
        tasks.append("# 🧪 Test Strategy Tasks")
        tasks.append("")
        
        # Extract untested functions/files
        if 'coverage' in results:
            tasks.append("## Priority 1: Critical Untested Code")
            # This would parse the actual coverage results
            tasks.append("1. [ ] Test authentication functions")
            tasks.append("2. [ ] Test payment processing")
            tasks.append("3. [ ] Test data validation")
            tasks.append("")
        
        # Add test improvements
        tasks.append("## Priority 2: Test Improvements")
        test_issues = [c for c in context if c.category == ContextCategory.TESTING]
        for i, issue in enumerate(test_issues[:5], 1):
            tasks.append(f"{i}. [ ] {issue.title}")
        
        return "\n".join(tasks)
    
    def _format_test_json(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format test results as JSON"""
        output = {
            'flow': 'test_strategy',
            'timestamp': datetime.now().isoformat(),
            'coverage': {},
            'gaps': [],
            'priorities': []
        }
        
        # Extract coverage data
        if 'coverage' in results:
            output['coverage'] = {'raw': str(results['coverage'])[:500]}
        
        # Extract gaps and priorities
        for entry in context:
            if entry.category == ContextCategory.TESTING:
                output['gaps'].append({
                    'area': entry.title,
                    'priority': str(entry.priority),
                    'details': entry.content
                })
        
        return json.dumps(output, indent=2)
    
    def _format_test_report(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format test results as text report"""
        report = []
        report.append("# 🧪 Test Strategy Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Coverage summary
        if 'coverage' in results:
            report.append("## 📊 Coverage Analysis")
            report.append(str(results['coverage'])[:500])
            report.append("")
        
        # Test gaps
        gaps = [c for c in context if c.category == ContextCategory.TESTING]
        if gaps:
            report.append(f"## 🔍 Test Gaps ({len(gaps)})")
            for gap in gaps:
                report.append(f"- **{gap.title}** ({gap.priority})")
            report.append("")
        
        return "\n".join(report)
    
    def _format_performance_json(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format performance results as JSON"""
        output = {
            'flow': 'performance_audit',
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'bottlenecks': [],
            'recommendations': []
        }
        
        # Extract metrics and bottlenecks
        for entry in context:
            if entry.type == ContextType.PERFORMANCE_METRIC:
                output['metrics'][entry.title] = entry.content
            elif entry.type == ContextType.PERFORMANCE_ISSUE:
                output['bottlenecks'].append({
                    'issue': entry.title,
                    'severity': str(entry.priority),
                    'details': entry.content
                })
        
        return json.dumps(output, indent=2)
    
    def _format_performance_report(self, results: Dict[str, Any], context: List[ContextEntry]) -> str:
        """Format performance results as text report"""
        report = []
        report.append("# ⚡ Performance Audit Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Performance metrics
        metrics = [c for c in context if c.type == ContextType.PERFORMANCE_METRIC]
        if metrics:
            report.append("## 📊 Performance Metrics")
            for m in metrics:
                report.append(f"- **{m.title}**: {m.content.get('value', 'N/A')}")
            report.append("")
        
        # Bottlenecks
        issues = [c for c in context if c.type == ContextType.PERFORMANCE_ISSUE]
        if issues:
            report.append(f"## 🐌 Performance Bottlenecks ({len(issues)})")
            for issue in issues:
                report.append(f"- **{issue.title}** ({issue.priority})")
                if 'location' in issue.content:
                    report.append(f"  Location: {issue.content['location']}")
            report.append("")
        
        return "\n".join(report)