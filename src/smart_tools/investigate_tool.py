"""
Investigate Tool - Smart tool for debugging issues with parallel execution
Routes to search_code + check_quality + analyze_logs + performance_profiler based on problem type
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
    Smart tool for investigating and debugging problems in code
    Intelligently routes to multiple engines based on problem characteristics
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], problem: str, **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use based on the problem description
        """
        engines_to_use = []
        routing_explanation = []
        problem_lower = problem.lower()
        
        # Always use search_code to find relevant areas
        engines_to_use.append('search_code')
        routing_explanation.append("Code search to locate relevant areas")
        
        # Performance-related problems
        if any(keyword in problem_lower for keyword in ['slow', 'performance', 'timeout', 'lag', 'bottleneck']):
            engines_to_use.extend(['performance_profiler', 'check_quality'])
            routing_explanation.append("Performance analysis for speed issues")
        
        # Error/crash-related problems
        if any(keyword in problem_lower for keyword in ['error', 'exception', 'crash', 'fail', 'bug']):
            engines_to_use.extend(['analyze_logs', 'check_quality'])
            routing_explanation.append("Log analysis and quality check for errors")
        
        # Security-related problems
        if any(keyword in problem_lower for keyword in ['security', 'vulnerability', 'exploit', 'attack']):
            engines_to_use.extend(['config_validator', 'check_quality'])
            routing_explanation.append("Security configuration validation")
        
        # Database-related problems
        if any(keyword in problem_lower for keyword in ['database', 'sql', 'query', 'schema']):
            engines_to_use.append('analyze_database')
            routing_explanation.append("Database analysis for data issues")
        
        # API/Integration problems
        if any(keyword in problem_lower for keyword in ['api', 'integration', 'endpoint', 'contract']):
            engines_to_use.append('api_contract_checker')
            routing_explanation.append("API contract validation")
        
        # Always add architectural analysis for context
        engines_to_use.append('analyze_code')
        routing_explanation.append("Architectural analysis for context")
        
        # Add dependency analysis for multi-file issues
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
        Execute investigation using parallel multi-engine analysis with memory safeguards
        """
        try:
            # Memory safeguard: Check available memory before parallel execution
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                logger.warning(f"High memory usage detected: {memory.percent}%. Using reduced parallelism.")
                max_parallel = 2
            else:
                max_parallel = 5
            
            # Track execution errors
            execution_errors = []
            
            routing_strategy = self.get_routing_strategy(files=files, problem=problem, **kwargs)
            engines_used = routing_strategy['engines']
            problem_type = routing_strategy['problem_type']
            
            analysis_results = {}
            search_keywords = self._extract_search_keywords(problem)
            quality_focus = self._map_problem_to_quality_focus(problem_type)
            
            # Group engines into parallel batches
            # Batch 1: Independent analysis engines
            parallel_tasks = []
            
            if 'search_code' in engines_used:
                parallel_tasks.append(self._run_code_search(files, search_keywords, problem))
            
            if 'check_quality' in engines_used:
                parallel_tasks.append(self._run_quality_analysis(files, quality_focus))
            
            if 'analyze_code' in engines_used:
                parallel_tasks.append(self._run_architectural_analysis(files, problem))
            
            # Batch 2: Problem-specific specialized engines
            specialized_tasks = []
            
            if problem_type == 'performance' and 'performance_profiler' in engines_used:
                specialized_tasks.append(self._run_performance_analysis(problem))
            
            if problem_type == 'error' and 'analyze_logs' in engines_used:
                specialized_tasks.append(self._run_log_analysis(files))
            
            if problem_type == 'security' and 'config_validator' in engines_used:
                specialized_tasks.append(self._run_security_analysis(files))
            
            if problem_type == 'integration' and 'api_contract_checker' in engines_used:
                specialized_tasks.append(self._run_api_analysis(files))
            
            if problem_type == 'database' and 'analyze_database' in engines_used:
                specialized_tasks.append(self._run_database_analysis(files))
            
            if 'map_dependencies' in engines_used:
                specialized_tasks.append(self._run_dependency_analysis(files))
            
            # Execute parallel batch 1 with memory safeguards
            if parallel_tasks:
                semaphore = asyncio.Semaphore(max_parallel)
                
                async def run_with_semaphore(task):
                    async with semaphore:
                        return await task
                
                limited_tasks = [run_with_semaphore(task) for task in parallel_tasks]
                parallel_results = await asyncio.gather(*limited_tasks, return_exceptions=True)
                
                # Process results with error tracking
                for i, result in enumerate(parallel_results):
                    if isinstance(result, Exception):
                        error_msg = f"Parallel task {i} failed: {type(result).__name__}: {str(result)}"
                        logger.error(error_msg)
                        execution_errors.append(error_msg)
                    elif isinstance(result, dict):
                        analysis_results.update(result)
            
            # Execute specialized batch with same safeguards
            if specialized_tasks:
                limited_specialized = [run_with_semaphore(task) for task in specialized_tasks]
                specialized_results = await asyncio.gather(*limited_specialized, return_exceptions=True)
                
                for i, result in enumerate(specialized_results):
                    if isinstance(result, Exception):
                        error_msg = f"Specialized task {i} failed: {type(result).__name__}: {str(result)}"
                        logger.error(error_msg)
                        execution_errors.append(error_msg)
                    elif isinstance(result, dict):
                        analysis_results.update(result)
            
            # Synthesize investigation results with error reporting
            investigation_report = self._synthesize_investigation(
                problem, problem_type, analysis_results, routing_strategy, execution_errors
            )
            
            # Apply executive synthesis
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'problem': problem,
                    'focus': focus,
                    **kwargs
                }
                investigation_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=investigation_report,
                    original_request=original_request
                )
            
            # Determine success based on findings
            investigation_success = len(analysis_results) > 0 and len(execution_errors) < len(engines_used)
            
            return SmartToolResult(
                tool_name="investigate",
                success=investigation_success,
                result=investigation_report,
                engines_used=engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "problem": problem,
                    "problem_type": problem_type,
                    "focus": focus,
                    "phases_completed": len(analysis_results),
                    "performance_mode": "parallel",
                    "parallel_batches": 2,
                    "max_parallel_tasks": max_parallel,
                    "memory_usage_percent": memory.percent,
                    "execution_errors": len(execution_errors),
                    "error_details": execution_errors[:5] if execution_errors else []
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
    
    # Parallel execution helper methods
    async def _run_code_search(self, files: List[str], keywords: str, problem: str) -> Dict[str, Any]:
        """Run code search in parallel"""
        try:
            result = await self.execute_engine(
                'search_code',
                query=keywords,
                paths=files,
                context_question=f"Find code related to: {problem}",
                output_format="text"
            )
            return {'code_search': result}
        except Exception as e:
            return {'code_search': f"Code search failed: {str(e)}"}
    
    async def _run_quality_analysis(self, files: List[str], quality_focus: str) -> Dict[str, Any]:
        """Run quality analysis in parallel"""
        try:
            result = await self.execute_engine(
                'check_quality',
                paths=files,
                check_type=quality_focus,
                verbose=True
            )
            return {'quality': result}
        except Exception as e:
            return {'quality': f"Quality analysis failed: {str(e)}"}
    
    async def _run_architectural_analysis(self, files: List[str], problem: str) -> Dict[str, Any]:
        """Run architectural analysis in parallel"""
        try:
            result = await self.execute_engine(
                'analyze_code',
                paths=files,
                analysis_type="refactor_prep",
                question=f"What might be causing: {problem}"
            )
            return {'architecture': result}
        except Exception as e:
            return {'architecture': f"Architectural analysis failed: {str(e)}"}
    
    async def _run_performance_analysis(self, problem: str) -> Dict[str, Any]:
        """Run performance analysis"""
        try:
            result = await self.execute_engine(
                'performance_profiler',
                target_operation=problem
            )
            return {'performance': result}
        except Exception as e:
            return {'performance': f"Performance analysis failed: {str(e)}"}
    
    async def _run_log_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run log analysis"""
        try:
            result = await self.execute_engine(
                'analyze_logs',
                log_paths=files,
                focus="errors"
            )
            return {'logs': result}
        except Exception as e:
            return {'logs': f"Log analysis failed: {str(e)}"}
    
    async def _run_security_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run security analysis"""
        try:
            result = await self.execute_engine(
                'config_validator',
                config_paths=files,
                validation_type="security"
            )
            return {'security_config': result}
        except Exception as e:
            return {'security_config': f"Security analysis failed: {str(e)}"}
    
    async def _run_api_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run API analysis"""
        try:
            result = await self.execute_engine(
                'api_contract_checker',
                spec_paths=files
            )
            return {'api_contracts': result}
        except Exception as e:
            return {'api_contracts': f"API analysis failed: {str(e)}"}
    
    async def _run_database_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run database analysis"""
        try:
            result = await self.execute_engine(
                'analyze_database',
                schema_paths=files,
                analysis_type="relationships"
            )
            return {'database': result}
        except Exception as e:
            return {'database': f"Database analysis failed: {str(e)}"}
    
    async def _run_dependency_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run dependency analysis"""
        try:
            result = await self.execute_engine(
                'map_dependencies',
                project_paths=files,
                analysis_depth="transitive"
            )
            return {'dependencies': result}
        except Exception as e:
            return {'dependencies': f"Dependency analysis failed: {str(e)}"}
    
    def _extract_search_keywords(self, problem: str) -> str:
        """Extract relevant keywords from problem description for search"""
        # Simple keyword extraction - could be enhanced with NLP
        keywords = []
        problem_words = problem.split()
        
        # Filter out common words and keep technical terms
        common_words = {'the', 'is', 'at', 'in', 'on', 'and', 'or', 'a', 'an', 'to', 'for', 'of', 'with', 'by'}
        for word in problem_words:
            if word.lower() not in common_words and len(word) > 2:
                keywords.append(word)
        
        return ' '.join(keywords[:5])  # Limit to 5 keywords
    
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
                                 analysis_results: Dict[str, Any], 
                                 routing_strategy: Dict[str, Any],
                                 execution_errors: List[str] = None) -> str:
        """Synthesize investigation results into a comprehensive report"""
        if execution_errors is None:
            execution_errors = []
        
        report_sections = [
            "# 🔍 Investigation Results",
            f"**Problem**: {problem}",
            f"**Problem Type**: {problem_type.title()}",
            f"**Analysis Strategy**: {routing_strategy['explanation']}",
            ""
        ]
        
        # Add error reporting if any failures occurred
        if execution_errors:
            report_sections.extend([
                "## ⚠️ Partial Analysis - Some Engines Failed",
                f"**{len(execution_errors)} engine(s) encountered errors:**",
                "",
                *[f"- {error}" for error in execution_errors[:5]],
                "",
                "**Note**: Results may be incomplete.",
                ""
            ])
        
        # Code Search Results
        if 'code_search' in analysis_results:
            report_sections.extend([
                "## 📝 Code Search Findings",
                str(analysis_results['code_search']),
                ""
            ])
        
        # Problem-Specific Analysis
        if 'performance' in analysis_results:
            report_sections.extend([
                "## ⚡ Performance Analysis",
                str(analysis_results['performance']),
                ""
            ])
        
        if 'logs' in analysis_results:
            report_sections.extend([
                "## 📊 Log Analysis",
                str(analysis_results['logs']),
                ""
            ])
        
        if 'security_config' in analysis_results:
            report_sections.extend([
                "## 🔒 Security Configuration",
                str(analysis_results['security_config']),
                ""
            ])
        
        if 'api_contracts' in analysis_results:
            report_sections.extend([
                "## 🔌 API Contract Analysis",
                str(analysis_results['api_contracts']),
                ""
            ])
        
        if 'database' in analysis_results:
            report_sections.extend([
                "## 🗃️ Database Analysis",
                str(analysis_results['database']),
                ""
            ])
        
        # General Analysis
        if 'quality' in analysis_results:
            report_sections.extend([
                "## 🔍 Quality Analysis",
                str(analysis_results['quality']),
                ""
            ])
        
        if 'architecture' in analysis_results:
            report_sections.extend([
                "## 🏗️ Architectural Analysis", 
                str(analysis_results['architecture']),
                ""
            ])
        
        if 'dependencies' in analysis_results:
            report_sections.extend([
                "## 🔗 Dependency Analysis",
                str(analysis_results['dependencies']),
                ""
            ])
        
        # Summary and Recommendations
        report_sections.extend([
            "## 💡 Investigation Summary",
            self._generate_investigation_summary(problem_type, analysis_results)
        ])
        
        return '\n'.join(report_sections)
    
    def _generate_investigation_summary(self, problem_type: str, results: Dict[str, Any]) -> str:
        """Generate a summary of investigation findings"""
        summary_points = []
        
        # Count successful analyses
        successful_analyses = len([r for r in results.values() if not str(r).startswith("Analysis failed")])
        summary_points.append(f"- **Analyses Completed**: {successful_analyses}/{len(results)}")
        
        # Problem-specific insights
        if problem_type == 'performance' and 'performance' in results:
            summary_points.append("- **Performance Issues**: Bottlenecks identified - see performance analysis above")
        
        if problem_type == 'error' and 'logs' in results:
            summary_points.append("- **Error Patterns**: Error traces found - see log analysis above")
        
        if problem_type == 'security' and 'security_config' in results:
            summary_points.append("- **Security Concerns**: Configuration issues detected - see security analysis above")
        
        # General insights
        if 'architecture' in results:
            summary_points.append("- **Architectural Insights**: Potential design issues identified")
        
        if 'dependencies' in results:
            summary_points.append("- **Dependency Issues**: Coupling or circular dependencies may be contributing")
        
        if not summary_points:
            summary_points.append("- Investigation completed - review detailed results above")
        
        return '\n'.join(summary_points)