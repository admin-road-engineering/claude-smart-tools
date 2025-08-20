"""
REFERENCE IMPLEMENTATION: Sequential Investigate Tool

This file serves as a reference implementation for sequential execution patterns.
The main investigate_tool.py now supports both parallel and sequential modes.

This file is kept for:
- Reference for sequential execution patterns
- Fallback implementation if needed
- Comparison during testing and validation

DO NOT USE THIS FILE DIRECTLY - use investigate_tool.py with INVESTIGATE_EXECUTION_MODE=sequential
"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
import psutil  # For memory monitoring
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer

logger = logging.getLogger(__name__)


class InvestigateTool(BaseSmartTool):
    """
    Smart tool for problem-solving and debugging
    Intelligently routes to multiple engines based on problem description
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], problem: str, **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use based on the problem description and context
        """
        engines_to_use = []
        routing_explanation = []
        
        # Analyze problem keywords to determine investigation strategy
        problem_lower = problem.lower()
        
        # Always start with code search to locate relevant areas
        engines_to_use.append('search_code')
        routing_explanation.append("Starting with code search to locate problem areas")
        
        # Performance-related problems
        if any(keyword in problem_lower for keyword in [
            'slow', 'performance', 'timeout', 'memory', 'cpu', 'bottleneck', 
            'latency', 'hanging', 'freeze', 'lag', 'optimization'
        ]):
            engines_to_use.extend(['performance_profiler', 'check_quality'])
            routing_explanation.append("Performance issue detected - adding profiler and quality analysis")
            
        # Error and exception problems
        elif any(keyword in problem_lower for keyword in [
            'error', 'exception', 'crash', 'fail', 'bug', 'broken', 'issue',
            'problem', 'not working', 'traceback', 'stack trace'
        ]):
            engines_to_use.extend(['analyze_logs', 'check_quality'])
            routing_explanation.append("Error investigation - adding log analysis and quality checks")
            
        # Security-related problems
        elif any(keyword in problem_lower for keyword in [
            'security', 'vulnerability', 'exploit', 'breach', 'unauthorized',
            'authentication', 'authorization', 'injection', 'xss', 'csrf'
        ]):
            engines_to_use.extend(['check_quality', 'config_validator'])
            routing_explanation.append("Security concern - adding security analysis and config validation")
            
        # Integration and API problems
        elif any(keyword in problem_lower for keyword in [
            'api', 'integration', 'connection', 'network', 'endpoint',
            'service', 'external', 'third-party', 'webhook'
        ]):
            engines_to_use.extend(['api_contract_checker', 'check_quality'])
            routing_explanation.append("API/Integration issue - adding contract checking and quality analysis")
            
        # Database-related problems
        elif any(keyword in problem_lower for keyword in [
            'database', 'sql', 'query', 'schema', 'migration', 'data',
            'table', 'index', 'constraint', 'relation'
        ]):
            engines_to_use.extend(['analyze_database', 'check_quality'])
            routing_explanation.append("Database issue - adding database analysis and quality checks")
            
        # General code quality or architectural problems
        else:
            engines_to_use.extend(['analyze_code', 'check_quality'])
            routing_explanation.append("General investigation - adding code analysis and quality checks")
        
        # Always add dependency analysis for complex problems
        if len(files) > 1 or any(keyword in problem_lower for keyword in [
            'dependency', 'import', 'module', 'circular', 'coupling'
        ]):
            engines_to_use.append('map_dependencies')
            routing_explanation.append("Multi-file or dependency issue - adding dependency mapping")
        
        # Remove duplicates while preserving order
        engines_to_use = list(dict.fromkeys(engines_to_use))
        
        return {
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'problem_type': self._classify_problem_type(problem_lower)
        }
    
    def _classify_problem_type(self, problem_lower: str) -> str:
        """Classify the type of problem for better analysis"""
        if any(keyword in problem_lower for keyword in ['slow', 'performance', 'timeout']):
            return 'performance'
        elif any(keyword in problem_lower for keyword in ['error', 'exception', 'crash']):
            return 'error'
        elif any(keyword in problem_lower for keyword in ['security', 'vulnerability']):
            return 'security'
        elif any(keyword in problem_lower for keyword in ['api', 'integration']):
            return 'integration'
        elif any(keyword in problem_lower for keyword in ['database', 'sql']):
            return 'database'
        else:
            return 'general'
    
    async def execute(self, files: List[str], problem: str, focus: str = "debug", **kwargs) -> SmartToolResult:
        """
        Execute investigation using coordinated multi-engine analysis
        """
        try:
            routing_strategy = self.get_routing_strategy(files=files, problem=problem, **kwargs)
            engines_used = routing_strategy['engines']
            problem_type = routing_strategy['problem_type']
            
            analysis_results = {}
            
            # Phase 1: Code Search - Find relevant code areas
            if 'search_code' in engines_used:
                search_keywords = self._extract_search_keywords(problem)
                search_result = await self.execute_engine(
                    'search_code', 
                    query=search_keywords,
                    paths=files,
                    context_question=f"Find code related to: {problem}",
                    output_format="text"
                )
                analysis_results['code_search'] = search_result
            
            # Phase 2: Specialized Analysis based on problem type
            if problem_type == 'performance' and 'performance_profiler' in engines_used:
                # Look for performance bottlenecks
                perf_result = await self.execute_engine(
                    'performance_profiler',
                    target_operation=problem
                )
                analysis_results['performance'] = perf_result
            
            elif problem_type == 'error' and 'analyze_logs' in engines_used:
                # Analyze logs for error patterns
                log_result = await self.execute_engine(
                    'analyze_logs',
                    log_paths=files,
                    focus="errors"
                )
                analysis_results['logs'] = log_result
            
            elif problem_type == 'security' and 'config_validator' in engines_used:
                # Check for security configuration issues
                config_result = await self.execute_engine(
                    'config_validator',
                    config_paths=files,
                    validation_type="security"
                )
                analysis_results['security_config'] = config_result
            
            elif problem_type == 'integration' and 'api_contract_checker' in engines_used:
                # Validate API contracts
                api_result = await self.execute_engine(
                    'api_contract_checker',
                    spec_paths=files
                )
                analysis_results['api_contracts'] = api_result
            
            elif problem_type == 'database' and 'analyze_database' in engines_used:
                # Analyze database schema and relationships
                db_result = await self.execute_engine(
                    'analyze_database',
                    schema_paths=files,
                    analysis_type="relationships"
                )
                analysis_results['database'] = db_result
            
            # Phase 3: Quality Analysis - Always run for comprehensive investigation
            if 'check_quality' in engines_used:
                quality_focus = self._map_problem_to_quality_focus(problem_type)
                quality_result = await self.execute_engine(
                    'check_quality',
                    paths=files,
                    check_type=quality_focus,
                    verbose=True
                )
                analysis_results['quality'] = quality_result
            
            # Phase 4: Architectural Analysis
            if 'analyze_code' in engines_used:
                code_result = await self.execute_engine(
                    'analyze_code',
                    paths=files,
                    analysis_type="refactor_prep",
                    question=f"What might be causing: {problem}"
                )
                analysis_results['architecture'] = code_result
            
            # Phase 5: Dependency Analysis
            if 'map_dependencies' in engines_used:
                dep_result = await self.execute_engine(
                    'map_dependencies',
                    project_paths=files,
                    analysis_depth="transitive"
                )
                analysis_results['dependencies'] = dep_result
            
            # Synthesize investigation results
            investigation_report = self._synthesize_investigation(
                problem, problem_type, analysis_results, routing_strategy
            )
            
            # Apply executive synthesis for better consolidated response
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'problem': problem,
                    **kwargs
                }
                investigation_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=investigation_report,
                    original_request=original_request
                )
            
            return SmartToolResult(
                tool_name="investigate",
                success=True,
                result=investigation_report,
                engines_used=engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "problem": problem,
                    "problem_type": problem_type,
                    "phases_completed": len(analysis_results)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="investigate",
                success=False,
                result=f"Investigation failed: {str(e)}",
                engines_used=engines_used if 'engines_used' in locals() else [],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    def _extract_search_keywords(self, problem: str) -> str:
        """Extract relevant search keywords from problem description"""
        # Remove common words and extract meaningful terms
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 
                       'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 
                       'could', 'may', 'might', 'must', 'can', 'not', 'no', 'and', 'or', 'but'}
        
        words = problem.lower().split()
        keywords = [word.strip('.,!?();:') for word in words if word not in common_words and len(word) > 2]
        
        # Return top keywords
        return ' '.join(keywords[:5])
    
    def _map_problem_to_quality_focus(self, problem_type: str) -> str:
        """Map problem type to quality check focus"""
        mapping = {
            'performance': 'performance',
            'error': 'all',
            'security': 'security', 
            'integration': 'all',
            'database': 'all',
            'general': 'all'
        }
        return mapping.get(problem_type, 'all')
    
    def _synthesize_investigation(self, problem: str, problem_type: str, 
                                 analysis_results: Dict[str, Any], routing_strategy: Dict[str, Any]) -> str:
        """Synthesize investigation results into a comprehensive report"""
        
        report_sections = [
            "# 🔍 Investigation Results",
            f"**Problem**: {problem}",
            f"**Problem Type**: {problem_type.title()}",
            f"**Analysis Strategy**: {routing_strategy['explanation']}",
            ""
        ]
        
        # Add each analysis phase
        if 'code_search' in analysis_results:
            report_sections.extend([
                "## 🎯 Code Search Results",
                f"Located relevant code areas for the reported problem:",
                str(analysis_results['code_search']),
                ""
            ])
        
        if 'performance' in analysis_results:
            report_sections.extend([
                "## ⚡ Performance Analysis",
                "Identified performance bottlenecks and optimization opportunities:",
                str(analysis_results['performance']),
                ""
            ])
        
        if 'logs' in analysis_results:
            report_sections.extend([
                "## 📊 Log Analysis",
                "Error patterns and issues found in logs:",
                str(analysis_results['logs']),
                ""
            ])
        
        if 'security_config' in analysis_results:
            report_sections.extend([
                "## 🔒 Security Configuration",
                "Security issues and configuration problems:",
                str(analysis_results['security_config']),
                ""
            ])
        
        if 'api_contracts' in analysis_results:
            report_sections.extend([
                "## 🔌 API Contract Analysis",
                "API specification validation and compatibility issues:",
                str(analysis_results['api_contracts']),
                ""
            ])
        
        if 'database' in analysis_results:
            report_sections.extend([
                "## 🗃️ Database Analysis",
                "Database schema issues and relationship problems:",
                str(analysis_results['database']),
                ""
            ])
        
        if 'quality' in analysis_results:
            report_sections.extend([
                "## 📋 Quality Analysis",
                "Code quality issues and potential problems:",
                str(analysis_results['quality']),
                ""
            ])
        
        if 'architecture' in analysis_results:
            report_sections.extend([
                "## 🏗️ Architectural Analysis",
                "Code structure and potential architectural causes:",
                str(analysis_results['architecture']),
                ""
            ])
        
        if 'dependencies' in analysis_results:
            report_sections.extend([
                "## 🔗 Dependency Analysis", 
                "Dependency relationships and potential coupling issues:",
                str(analysis_results['dependencies']),
                ""
            ])
        
        # Add investigation summary
        report_sections.extend([
            "## 💡 Investigation Summary",
            f"- **Problem Classification**: {problem_type.title()} issue requiring multi-phase analysis",
            f"- **Analysis Phases**: {len(analysis_results)} specialized tools used",
            f"- **Key Areas Examined**: {', '.join(analysis_results.keys())}",
            f"- **Recommendation**: Review the above analyses to identify root cause and implement fixes",
            ""
        ])
        
        return "\n".join(report_sections)