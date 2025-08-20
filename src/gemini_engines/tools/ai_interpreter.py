"""
AI Interpreter abstraction layer for Enhanced Tool Suite
Implements formal Stage 3 of the 4-stage Tool-as-a-Service pipeline
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json


class BaseAIInterpreter(ABC):
    """
    Abstract base class for AI interpretation layer (Stage 3 of Tool-as-a-Service pipeline)
    
    Transforms raw analysis results from core utilities into actionable insights
    """
    
    def __init__(self, gemini_client=None):
        """
        Initialize AI interpreter
        
        Args:
            gemini_client: Optional Gemini client for real AI integration
        """
        self.client = gemini_client
    
    @abstractmethod
    async def interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Transform raw analysis data into AI-powered insights
        
        Args:
            core_results: Raw data from tool's _core_utility method
            context: Optional context about the analysis request
            
        Returns:
            Dict containing AI insights and recommendations
        """
        pass
    
    def _format_insights(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Format insights into standardized structure"""
        return {
            "ai_insights": insights.get("insights", []),
            "recommendations": insights.get("recommendations", []),
            "priority_items": insights.get("priority_items", []),
            "confidence_score": insights.get("confidence", 0.8),
            "generated_by": self.__class__.__name__
        }


class MockAIInterpreter(BaseAIInterpreter):
    """
    Mock implementation for testing and development
    Generates structured insights without actual AI calls
    """
    
    async def interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate mock insights based on core results structure"""
        mock_insights = self._generate_mock_insights(core_results, context)
        return self._format_insights(mock_insights)
    
    def _generate_mock_insights(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate contextually relevant mock insights"""
        insights = []
        recommendations = []
        priority_items = []
        
        # Test Coverage specific insights
        if "uncovered_functions" in core_results:
            uncovered_count = len(core_results.get("uncovered_functions", []))
            if uncovered_count > 0:
                insights.append(f"Found {uncovered_count} uncovered functions requiring test coverage")
                recommendations.append("Prioritize testing critical business logic functions first")
                if uncovered_count > 10:
                    priority_items.append("High number of uncovered functions indicates systematic testing gaps")
        
        if "coverage_summary" in core_results:
            coverage = core_results["coverage_summary"].get("coverage_percentage", 0)
            if coverage < 80:
                insights.append(f"Test coverage at {coverage:.1f}% is below recommended 80% threshold")
                recommendations.append("Implement incremental testing strategy to improve coverage")
        
        # Dependency Mapper specific insights
        if "circular_dependencies" in core_results:
            circular_count = len(core_results.get("circular_dependencies", []))
            if circular_count > 0:
                insights.append(f"Detected {circular_count} circular dependencies affecting maintainability")
                recommendations.append("Refactor circular dependencies by introducing interface abstractions")
                priority_items.append("Circular dependencies increase coupling and testing complexity")
        
        if "coupling_metrics" in core_results:
            high_coupling = [
                module for module, metrics in core_results["coupling_metrics"].items() 
                if metrics.get("coupling_score", 0) > 0.7
            ]
            if high_coupling:
                insights.append(f"High coupling detected in {len(high_coupling)} modules")
                recommendations.append("Consider dependency injection to reduce tight coupling")
        
        # General insights
        parsing_errors = core_results.get("parsing_errors", [])
        if parsing_errors:
            insights.append(f"Found {len(parsing_errors)} files with syntax errors")
            recommendations.append("Fix syntax errors to enable complete analysis")
        
        return {
            "insights": insights,
            "recommendations": recommendations,
            "priority_items": priority_items,
            "confidence": 0.85
        }


class TestCoverageAIInterpreter(BaseAIInterpreter):
    """
    AI interpreter specialized for test coverage analysis
    Generates testing strategy recommendations
    """
    
    async def interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate test coverage insights and recommendations"""
        if self.client:
            # Future: Implement actual Gemini API call
            return await self._gemini_interpret(core_results, context)
        else:
            # Fallback to enhanced mock implementation
            return await self._enhanced_mock_interpret(core_results, context)
    
    async def _enhanced_mock_interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced mock implementation for test coverage"""
        insights = []
        recommendations = []
        priority_items = []
        
        # Analyze uncovered functions
        uncovered = core_results.get("uncovered_functions", [])
        if uncovered:
            # Group by complexity
            critical_functions = [f for f in uncovered if f.get("complexity") == "high"]
            medium_functions = [f for f in uncovered if f.get("complexity") == "medium"]
            
            if critical_functions:
                insights.append(f"Found {len(critical_functions)} high-complexity uncovered functions")
                priority_items.extend([f"Test {f['function']}" + (f" in {f['file']}" if 'file' in f else "") for f in critical_functions[:3]])
            
            if medium_functions:
                insights.append(f"Found {len(medium_functions)} medium-complexity functions needing tests")
                recommendations.append("Focus on edge cases and error handling for medium complexity functions")
        
        # Analyze test quality
        quality_issues = core_results.get("test_quality_issues", [])
        if quality_issues:
            assertion_issues = [q for q in quality_issues if q.get("issue") == "no_assertions"]
            if assertion_issues:
                insights.append(f"Found {len(assertion_issues)} tests without assertions")
                recommendations.append("Add meaningful assertions to validate expected behavior")
        
        return self._format_insights({
            "insights": insights,
            "recommendations": recommendations,
            "priority_items": priority_items,
            "confidence": 0.9
        })
    
    async def _gemini_interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Future implementation for actual Gemini API integration"""
        prompt = self._build_coverage_prompt(core_results, context)
        # TODO: Implement Gemini API call
        # response = await self.client.generate_content(prompt)
        # return self._parse_gemini_response(response)
        return await self._enhanced_mock_interpret(core_results, context)
    
    def _build_coverage_prompt(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for Gemini test coverage analysis"""
        return f"""
        Analyze this test coverage report and provide actionable testing recommendations:
        
        Coverage Summary: {json.dumps(core_results.get("coverage_summary", {}), indent=2)}
        Uncovered Functions: {len(core_results.get("uncovered_functions", []))}
        Test Quality Issues: {len(core_results.get("test_quality_issues", []))}
        
        Provide specific, actionable recommendations for improving test coverage and quality.
        """


class DependencyAIInterpreter(BaseAIInterpreter):
    """
    AI interpreter specialized for dependency analysis
    Generates architectural insights and refactoring recommendations
    """
    
    async def interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate dependency analysis insights"""
        if self.client:
            return await self._gemini_interpret(core_results, context)
        else:
            return await self._enhanced_mock_interpret(core_results, context)
    
    async def _enhanced_mock_interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced mock implementation for dependency analysis"""
        insights = []
        recommendations = []
        priority_items = []
        
        # Analyze dependency graph
        graph = core_results.get("dependency_graph", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        if nodes and edges:
            insights.append(f"Analyzed {len(nodes)} modules with {len(edges)} dependencies")
            
            # Check for large modules (high fan-in/fan-out)
            coupling_metrics = core_results.get("coupling_metrics", {})
            high_coupling_modules = [
                module for module, metrics in coupling_metrics.items()
                if metrics.get("coupling_score", 0) > 0.8
            ]
            
            if high_coupling_modules:
                insights.append(f"Identified {len(high_coupling_modules)} highly coupled modules")
                recommendations.append("Consider breaking down highly coupled modules using Single Responsibility Principle")
                priority_items.extend([f"Refactor {module}" for module in high_coupling_modules[:3]])
        
        # Analyze circular dependencies
        circular_deps = core_results.get("circular_dependencies", [])
        if circular_deps:
            high_severity = [c for c in circular_deps if c.get("severity") == "high"]
            if high_severity:
                insights.append(f"Found {len(high_severity)} high-severity circular dependencies")
                priority_items.extend([f"Break cycle: {' -> '.join(c['cycle'])}" for c in high_severity[:2]])
                recommendations.append("Introduce interface abstractions to break circular dependencies")
        
        # Analyze refactoring impact
        impact_analysis = core_results.get("refactoring_impacts", {})
        high_risk_modules = [
            module for module, impact in impact_analysis.items()
            if impact.get("risk_score", 0) > 0.8
        ]
        
        if high_risk_modules:
            insights.append(f"Identified {len(high_risk_modules)} high-risk refactoring targets")
            recommendations.append("Plan refactoring of high-risk modules carefully with comprehensive testing")
        
        return self._format_insights({
            "insights": insights,
            "recommendations": recommendations,
            "priority_items": priority_items,
            "confidence": 0.88
        })
    
    async def _gemini_interpret(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Future implementation for actual Gemini API integration"""
        prompt = self._build_dependency_prompt(core_results, context)
        # TODO: Implement Gemini API call
        return await self._enhanced_mock_interpret(core_results, context)
    
    def _build_dependency_prompt(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for Gemini dependency analysis"""
        graph_summary = core_results.get("dependency_graph", {})
        return f"""
        Analyze this dependency graph and provide architectural recommendations:
        
        Modules: {len(graph_summary.get("nodes", []))}
        Dependencies: {len(graph_summary.get("edges", []))}
        Circular Dependencies: {len(core_results.get("circular_dependencies", []))}
        High Coupling Modules: {len([m for m, metrics in core_results.get("coupling_metrics", {}).items() if metrics.get("coupling_score", 0) > 0.7])}
        
        Provide specific architectural improvement recommendations and refactoring strategies.
        """