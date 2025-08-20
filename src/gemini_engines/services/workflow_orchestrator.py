"""
WorkflowOrchestrator - Cross-tool integration using session context
Enables tools to share state and build upon each other's results
"""
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..persistence.sqlite_session_store import SqliteSessionStore
from .complexity_scorer import ComplexityScorer, ToolAssessment
from .error_handler_service import ErrorHandlerService
from .project_context_service import ProjectContextService
from .query_parser_service import QueryParserService
from ..exceptions import ToolingError, AnalysisError


class WorkflowStep(Enum):
    """Standard workflow steps for cross-tool integration"""
    DISCOVERY = "discovery"        # Initial analysis/search to find issues
    ANALYSIS = "analysis"         # Detailed analysis of discovered issues
    VALIDATION = "validation"     # Validate findings with additional tools
    DOCUMENTATION = "documentation"  # Generate reports/documentation


@dataclass
class ToolResult:
    """Standardized tool result for workflow integration"""
    tool_name: str
    session_id: str
    step: WorkflowStep
    success: bool
    result_data: Dict[str, Any]
    recommendations: List[str]
    follow_up_actions: List[Dict[str, Any]]
    execution_time_ms: int
    error_message: Optional[str] = None


@dataclass
class WorkflowContext:
    """Context shared across tools in a workflow"""
    session_id: str
    initiated_by: str
    current_step: WorkflowStep
    discovered_issues: List[Dict[str, Any]]
    analyzed_patterns: List[str]
    validated_findings: List[Dict[str, Any]]
    project_context: Dict[str, Any]
    user_preferences: Dict[str, Any]


class WorkflowOrchestrator:
    """Orchestrates cross-tool workflows for enhanced analysis"""
    
    def __init__(self, 
                 session_store: SqliteSessionStore,
                 complexity_scorer: ComplexityScorer,
                 error_handler: ErrorHandlerService,
                 project_service: ProjectContextService,
                 query_parser: QueryParserService):
        self.logger = logging.getLogger(__name__)
        self.session_store = session_store
        self.complexity_scorer = complexity_scorer
        self.error_handler = error_handler
        self.project_service = project_service
        self.query_parser = query_parser
        
        # Registry of available tool functions
        self.tool_registry: Dict[str, Callable] = {}
        
        # Workflow templates for common analysis patterns
        self.workflow_templates = {
            "security_audit": [
                {"tool": "check_quality", "step": WorkflowStep.DISCOVERY, "params": {"check_type": "security"}},
                {"tool": "search_code", "step": WorkflowStep.ANALYSIS, "params": {"context_question": "security vulnerabilities"}},
                {"tool": "analyze_code", "step": WorkflowStep.VALIDATION, "params": {"analysis_type": "architecture"}}
            ],
            "performance_analysis": [
                {"tool": "check_quality", "step": WorkflowStep.DISCOVERY, "params": {"check_type": "performance"}},
                {"tool": "search_code", "step": WorkflowStep.ANALYSIS, "params": {"context_question": "performance bottlenecks"}},
                {"tool": "analyze_code", "step": WorkflowStep.VALIDATION, "params": {"analysis_type": "refactor_prep"}}
            ],
            "architecture_review": [
                {"tool": "analyze_code", "step": WorkflowStep.DISCOVERY, "params": {"analysis_type": "architecture"}},
                {"tool": "check_quality", "step": WorkflowStep.ANALYSIS, "params": {"check_type": "all"}},
                {"tool": "search_code", "step": WorkflowStep.VALIDATION, "params": {"context_question": "design patterns"}}
            ]
        }
    
    def register_tool(self, tool_name: str, tool_function: Callable):
        """Register a tool function for workflow orchestration"""
        self.tool_registry[tool_name] = tool_function
        self.logger.debug(f"Registered tool: {tool_name}")
    
    def start_workflow(self, workflow_type: str, initial_params: Dict[str, Any]) -> str:
        """Start a new cross-tool workflow"""
        session_id = f"workflow_{uuid.uuid4().hex[:8]}"
        
        # Get project context for workflow
        project_context = self.project_service.get_project_context()
        
        # Initialize workflow context
        workflow_context = WorkflowContext(
            session_id=session_id,
            initiated_by=workflow_type,
            current_step=WorkflowStep.DISCOVERY,
            discovered_issues=[],
            analyzed_patterns=[],
            validated_findings=[],
            project_context={
                "type": project_context.project_type.value,
                "source_dirs": project_context.primary_source_dirs,
                "test_dirs": project_context.test_dirs
            },
            user_preferences=initial_params.get("preferences", {})
        )
        
        # Save initial workflow context
        self.session_store.save_workflow_context(
            session_id=session_id,
            tool_name="workflow_orchestrator",
            step_number=0,
            context_data=workflow_context.__dict__
        )
        
        self.logger.info(f"Started workflow '{workflow_type}' with session {session_id}")
        return session_id
    
    async def execute_workflow_step(self, session_id: str, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a single workflow step with context awareness"""
        start_time = datetime.now()
        
        try:
            # Get current workflow context
            workflow_context = self._get_workflow_context(session_id)
            
            # Enhance parameters with workflow context
            enhanced_params = self._enhance_parameters_with_context(
                tool_name, params, workflow_context
            )
            
            # Get tool assessment for timeout/complexity
            assessment = self.complexity_scorer.assess_tool_complexity(tool_name, enhanced_params)
            
            # Execute the tool
            if tool_name not in self.tool_registry:
                raise ToolingError(f"Tool '{tool_name}' not registered in workflow orchestrator")
            
            tool_function = self.tool_registry[tool_name]
            
            # Handle both sync and async tool functions
            import asyncio
            if asyncio.iscoroutinefunction(tool_function):
                result = await tool_function(**enhanced_params)
            else:
                result = tool_function(**enhanced_params)
            
            # Calculate execution time
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Process tool result and extract workflow-relevant information
            tool_result = self._process_tool_result(
                tool_name=tool_name,
                session_id=session_id,
                raw_result=result,
                workflow_context=workflow_context,
                execution_time_ms=execution_time
            )
            
            # Save tool metrics
            self.session_store.save_tool_metrics(
                session_id=session_id,
                tool_name=tool_name,
                execution_time_ms=execution_time,
                success=tool_result.success,
                result_count=len(tool_result.result_data.get('results', [])),
                complexity_level=assessment.complexity.name,
                parameters=enhanced_params
            )
            
            # Update workflow context with results
            self._update_workflow_context(session_id, tool_result)
            
            return tool_result
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Save failed metrics
            self.session_store.save_tool_metrics(
                session_id=session_id,
                tool_name=tool_name,
                execution_time_ms=execution_time,
                success=False,
                error_code=type(e).__name__,
                parameters=params
            )
            
            # Format error with context
            error_message = self.error_handler.format_error(e, {"tool": tool_name, "session": session_id})
            
            return ToolResult(
                tool_name=tool_name,
                session_id=session_id,
                step=WorkflowStep.DISCOVERY,  # Default step
                success=False,
                result_data={},
                recommendations=[],
                follow_up_actions=[],
                execution_time_ms=execution_time,
                error_message=error_message
            )
    
    def get_workflow_recommendations(self, session_id: str) -> List[Dict[str, Any]]:
        """Get intelligent recommendations for next workflow steps"""
        workflow_context = self._get_workflow_context(session_id)
        recommendations = []
        
        # Analyze current state and suggest next steps
        if workflow_context.current_step == WorkflowStep.DISCOVERY:
            if workflow_context.discovered_issues:
                recommendations.append({
                    "tool": "search_code",
                    "step": WorkflowStep.ANALYSIS,
                    "reason": "Analyze discovered issues in detail",
                    "params": {
                        "query": self._extract_search_terms_from_issues(workflow_context.discovered_issues),
                        "context_question": "detailed implementation analysis"
                    }
                })
        
        elif workflow_context.current_step == WorkflowStep.ANALYSIS:
            if workflow_context.analyzed_patterns:
                recommendations.append({
                    "tool": "check_quality",
                    "step": WorkflowStep.VALIDATION,
                    "reason": "Validate analyzed patterns for quality issues",
                    "params": {
                        "check_type": "all",
                        "verbose": True
                    }
                })
        
        elif workflow_context.current_step == WorkflowStep.VALIDATION:
            recommendations.append({
                "tool": "analyze_docs",
                "step": WorkflowStep.DOCUMENTATION,
                "reason": "Generate comprehensive documentation",
                "params": {
                    "synthesis_type": "implementation_guide"
                }
            })
        
        return recommendations
    
    async def execute_workflow_template(self, template_name: str, initial_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a predefined workflow template"""
        if template_name not in self.workflow_templates:
            raise AnalysisError(f"Unknown workflow template: {template_name}")
        
        template = self.workflow_templates[template_name]
        session_id = self.start_workflow(template_name, initial_params)
        
        results = {"session_id": session_id, "steps": []}
        
        for step_config in template:
            tool_name = step_config["tool"]
            step_params = {**initial_params, **step_config["params"]}
            
            result = await self.execute_workflow_step(session_id, tool_name, step_params)
            results["steps"].append({
                "tool": tool_name,
                "step": step_config["step"].value,
                "success": result.success,
                "recommendations": result.recommendations,
                "execution_time_ms": result.execution_time_ms
            })
            
            # Stop if a step fails
            if not result.success:
                results["status"] = "failed"
                results["error"] = result.error_message
                break
        else:
            results["status"] = "completed"
        
        return results
    
    def _get_workflow_context(self, session_id: str) -> WorkflowContext:
        """Get current workflow context from session store"""
        contexts = self.session_store.get_workflow_context(session_id, "workflow_orchestrator")
        
        if not contexts:
            raise AnalysisError(f"No workflow context found for session {session_id}")
        
        # Get the latest context
        latest_context = contexts[-1]
        context_data = latest_context['context_data']
        
        return WorkflowContext(**context_data)
    
    def _enhance_parameters_with_context(self, tool_name: str, params: Dict[str, Any], 
                                       workflow_context: WorkflowContext) -> Dict[str, Any]:
        """Enhance tool parameters with workflow context"""
        enhanced = params.copy()
        
        # Add smart path defaults if not specified
        if tool_name in ["search_code", "analyze_code", "check_quality"] and not enhanced.get("paths"):
            enhanced["paths"] = self.project_service.get_default_paths()
        
        # Add context from previous steps
        if tool_name == "search_code":
            # If we have discovered issues, focus search on those patterns
            if workflow_context.discovered_issues:
                search_terms = self._extract_search_terms_from_issues(workflow_context.discovered_issues)
                if search_terms and not enhanced.get("query"):
                    enhanced["query"] = search_terms
            
            # Enhance context question with workflow information
            if not enhanced.get("context_question"):
                enhanced["context_question"] = f"Analysis for {workflow_context.initiated_by} workflow"
        
        elif tool_name == "analyze_code":
            # Focus analysis on areas where issues were found
            if workflow_context.analyzed_patterns:
                if not enhanced.get("question"):
                    enhanced["question"] = f"Analyze patterns: {', '.join(workflow_context.analyzed_patterns[:3])}"
        
        elif tool_name == "check_quality":
            # Include test paths if available
            if workflow_context.project_context.get("test_dirs") and not enhanced.get("test_paths"):
                enhanced["test_paths"] = workflow_context.project_context["test_dirs"]
        
        return enhanced
    
    def _process_tool_result(self, tool_name: str, session_id: str, raw_result: Any,
                           workflow_context: WorkflowContext, execution_time_ms: int) -> ToolResult:
        """Process raw tool result into standardized format"""
        
        # Extract relevant information based on tool type
        if tool_name == "check_quality":
            issues = self._extract_quality_issues(raw_result)
            recommendations = self._extract_quality_recommendations(raw_result)
            
            return ToolResult(
                tool_name=tool_name,
                session_id=session_id,
                step=WorkflowStep.DISCOVERY,
                success=True,
                result_data={"issues": issues, "raw_result": str(raw_result)[:1000]},
                recommendations=recommendations,
                follow_up_actions=self._suggest_follow_up_actions("quality_check", issues),
                execution_time_ms=execution_time_ms
            )
        
        elif tool_name == "search_code":
            matches = self._extract_search_matches(raw_result)
            patterns = self._extract_code_patterns(raw_result)
            
            return ToolResult(
                tool_name=tool_name,
                session_id=session_id,
                step=WorkflowStep.ANALYSIS,
                success=True,
                result_data={"matches": matches, "patterns": patterns, "raw_result": str(raw_result)[:1000]},
                recommendations=self._extract_search_recommendations(raw_result),
                follow_up_actions=self._suggest_follow_up_actions("search", matches),
                execution_time_ms=execution_time_ms
            )
        
        elif tool_name == "analyze_code":
            architecture = self._extract_architecture_info(raw_result)
            
            return ToolResult(
                tool_name=tool_name,
                session_id=session_id,
                step=WorkflowStep.VALIDATION,
                success=True,
                result_data={"architecture": architecture, "raw_result": str(raw_result)[:1000]},
                recommendations=self._extract_analysis_recommendations(raw_result),
                follow_up_actions=self._suggest_follow_up_actions("analysis", architecture),
                execution_time_ms=execution_time_ms
            )
        
        else:
            # Generic processing
            return ToolResult(
                tool_name=tool_name,
                session_id=session_id,
                step=WorkflowStep.DISCOVERY,
                success=True,
                result_data={"raw_result": str(raw_result)[:1000]},
                recommendations=[],
                follow_up_actions=[],
                execution_time_ms=execution_time_ms
            )
    
    def _update_workflow_context(self, session_id: str, tool_result: ToolResult):
        """Update workflow context with tool results"""
        workflow_context = self._get_workflow_context(session_id)
        
        # Update based on tool results
        if tool_result.tool_name == "check_quality":
            issues = tool_result.result_data.get("issues", [])
            workflow_context.discovered_issues.extend(issues)
            if issues:
                workflow_context.current_step = WorkflowStep.ANALYSIS
        
        elif tool_result.tool_name == "search_code":
            patterns = tool_result.result_data.get("patterns", [])
            workflow_context.analyzed_patterns.extend(patterns)
            if patterns:
                workflow_context.current_step = WorkflowStep.VALIDATION
        
        elif tool_result.tool_name == "analyze_code":
            architecture = tool_result.result_data.get("architecture", {})
            if architecture:
                workflow_context.validated_findings.append(architecture)
                workflow_context.current_step = WorkflowStep.DOCUMENTATION
        
        # Save updated context
        step_number = len(self.session_store.get_workflow_context(session_id)) + 1
        self.session_store.save_workflow_context(
            session_id=session_id,
            tool_name="workflow_orchestrator",
            step_number=step_number,
            context_data=workflow_context.__dict__
        )
    
    def _extract_search_terms_from_issues(self, issues: List[Dict[str, Any]]) -> str:
        """Extract search terms from discovered issues"""
        terms = []
        for issue in issues[:3]:  # Limit to first 3 issues
            if "pattern" in issue:
                terms.append(issue["pattern"])
            elif "keyword" in issue:
                terms.append(issue["keyword"])
            elif "type" in issue:
                terms.append(issue["type"])
        
        return " OR ".join(terms) if terms else "TODO OR FIXME OR BUG"
    
    # Helper methods for extracting information from tool results
    def _extract_quality_issues(self, result: Any) -> List[Dict[str, Any]]:
        """Extract issues from quality check results"""
        # This would parse the actual result format
        # For now, return mock structure
        result_str = str(result).lower()
        issues = []
        
        if "security" in result_str:
            issues.append({"type": "security", "pattern": "authentication", "severity": "high"})
        if "performance" in result_str:
            issues.append({"type": "performance", "pattern": "optimization", "severity": "medium"})
        
        return issues
    
    def _extract_quality_recommendations(self, result: Any) -> List[str]:
        """Extract recommendations from quality check"""
        return ["Review security patterns", "Optimize performance bottlenecks"]
    
    def _extract_search_matches(self, result: Any) -> List[Dict[str, Any]]:
        """Extract matches from search results"""
        return [{"file": "example.py", "line": 42, "match": "sample code"}]
    
    def _extract_code_patterns(self, result: Any) -> List[str]:
        """Extract code patterns from search results"""
        return ["authentication", "validation", "error_handling"]
    
    def _extract_search_recommendations(self, result: Any) -> List[str]:
        """Extract recommendations from search results"""
        return ["Consider refactoring repeated patterns"]
    
    def _extract_architecture_info(self, result: Any) -> Dict[str, Any]:
        """Extract architecture information from analysis"""
        return {"components": ["service", "controller"], "patterns": ["MVC", "dependency_injection"]}
    
    def _extract_analysis_recommendations(self, result: Any) -> List[str]:
        """Extract recommendations from code analysis"""
        return ["Improve code organization", "Add documentation"]
    
    def _suggest_follow_up_actions(self, result_type: str, data: Any) -> List[Dict[str, Any]]:
        """Suggest follow-up actions based on results"""
        if result_type == "quality_check" and data:
            return [{"tool": "search_code", "focus": "security issues"}]
        elif result_type == "search" and data:
            return [{"tool": "analyze_code", "focus": "found patterns"}]
        elif result_type == "analysis" and data:
            return [{"tool": "check_quality", "focus": "validate findings"}]
        
        return []