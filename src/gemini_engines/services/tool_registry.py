"""
Tool Registry - Single Source of Truth for Available Gemini MCP Tools
Implements centralized tool metadata management following Gemini's architectural recommendations
"""
import logging
from typing import Dict, List, Any, NamedTuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Structured tool metadata for consistent management"""
    name: str
    description: str
    category: str
    focus_areas: List[str]  # When this tool should be recommended
    key_parameters: Dict[str, str]  # Important parameters with descriptions
    priority: int = 1  # 1=high, 2=medium, 3=low recommendation priority


class ToolRegistry:
    """
    Central registry for all Gemini MCP tools
    
    This is the single source of truth for tool metadata, eliminating
    the need for hardcoded tool lists in prompts and ensuring consistency.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tools: Dict[str, ToolMetadata] = {}
        self._initialize_core_tools()
    
    def _initialize_core_tools(self):
        """Initialize the 13 essential tools with their metadata"""
        
        # Original 7 Core Tools
        self.register_tool(ToolMetadata(
            name="search_code",
            description="Enhanced semantic code search with contextual understanding",
            category="core",
            focus_areas=["implementation_gaps", "pattern_finding", "code_discovery", "debugging"],
            key_parameters={
                "query": "Search query with boolean operators support",
                "context_question": "What you want to understand about results",
                "search_type": "text|regex|word"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="analyze_code",
            description="Enhanced code analysis with architectural insights and intelligent path detection",
            category="core", 
            focus_areas=["architecture", "code_structure", "refactoring", "design_patterns"],
            key_parameters={
                "analysis_type": "overview|dependencies|refactor_prep|architecture|research",
                "paths": "Code paths to analyze (auto-detects if empty)",
                "question": "Specific question about the code"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="check_quality",
            description="Enhanced quality analysis with comprehensive test coverage, security scanning, and performance assessment",
            category="core",
            focus_areas=["security", "performance", "code_quality", "testing", "best_practices"],
            key_parameters={
                "check_type": "all|tests|security|performance",
                "paths": "Paths to check (auto-detects if empty)"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="analyze_docs",
            description="Analyze and synthesize documentation from multiple sources using Gemini's large context",
            category="core",
            focus_areas=["documentation", "requirements", "api_understanding"],
            key_parameters={
                "sources": "Documentation sources (file paths or URLs)",
                "synthesis_type": "summary|comparison|implementation_guide|api_reference"
            },
            priority=2
        ))
        
        self.register_tool(ToolMetadata(
            name="analyze_logs",
            description="Analyze log files to identify patterns, errors, and performance issues",
            category="core",
            focus_areas=["debugging", "performance", "error_analysis", "monitoring"],
            key_parameters={
                "log_paths": "Log file or directory paths",
                "focus": "errors|performance|patterns|timeline|all"
            },
            priority=2
        ))
        
        self.register_tool(ToolMetadata(
            name="analyze_database",
            description="Analyze database schemas, migrations, and relationships for architectural understanding",
            category="core",
            focus_areas=["database", "data_modeling", "migrations", "relationships"],
            key_parameters={
                "schema_paths": "Schema, migration, or model file paths",
                "analysis_type": "schema|migrations|relationships|optimization"
            },
            priority=2
        ))
        
        # Phase 1 Enhanced Tools
        self.register_tool(ToolMetadata(
            name="performance_profiler",
            description="Runtime performance analysis with AI interpretation and bottleneck identification",
            category="phase1",
            focus_areas=["performance", "bottlenecks", "optimization", "profiling"],
            key_parameters={
                "target_operation": "Operation or script to profile",
                "profile_type": "cpu|memory|io|comprehensive"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="config_validator",
            description="Configuration validation with File Freshness Guardian integration and AI-powered fix suggestions",
            category="phase1",
            focus_areas=["configuration", "security", "deployment", "environment_setup"],
            key_parameters={
                "config_paths": "Configuration file paths to validate",
                "validation_type": "security|completeness|syntax|all"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="api_contract_checker", 
            description="API contract validation with impact analysis and breaking change detection",
            category="phase1",
            focus_areas=["api_design", "breaking_changes", "integration", "contracts"],
            key_parameters={
                "spec_paths": "OpenAPI/Swagger specification file paths",
                "comparison_mode": "standalone|compare_versions|breaking_changes"
            },
            priority=1
        ))
        
        # Phase 2 Enhanced Tools
        self.register_tool(ToolMetadata(
            name="analyze_test_coverage",
            description="AST-based test coverage analysis with gap identification and strategic recommendations",
            category="phase2",
            focus_areas=["testing", "code_coverage", "quality_assurance", "test_strategy"],
            key_parameters={
                "source_paths": "Source code paths to analyze",
                "mapping_strategy": "convention|directory|docstring"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="map_dependencies",
            description="Comprehensive dependency analysis with architectural insights and circular dependency detection",
            category="phase2",
            focus_areas=["architecture", "dependencies", "circular_dependencies", "coupling"],
            key_parameters={
                "project_paths": "Project directories to analyze",
                "analysis_depth": "immediate|transitive|full"
            },
            priority=1
        ))
        
        self.register_tool(ToolMetadata(
            name="interface_inconsistency_detector",
            description="Interface consistency checking via AST analysis and naming pattern detection",
            category="phase2",
            focus_areas=["code_consistency", "naming_patterns", "interfaces", "refactoring"],
            key_parameters={
                "source_paths": "Source code paths to analyze for inconsistencies",
                "pattern_types": "naming|parameters|return_types|documentation"
            },
            priority=2
        ))
        
        self.logger.info(f"Initialized ToolRegistry with {len(self._tools)} tools")
    
    def register_tool(self, tool_metadata: ToolMetadata):
        """Register a tool with the registry"""
        self._tools[tool_metadata.name] = tool_metadata
        self.logger.debug(f"Registered tool: {tool_metadata.name}")
    
    def get_tool(self, name: str) -> ToolMetadata:
        """Get tool metadata by name"""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]
    
    def get_all_tools(self) -> Dict[str, ToolMetadata]:
        """Get all registered tools"""
        return self._tools.copy()
    
    def get_tools_for_focus_area(self, focus_area: str) -> List[ToolMetadata]:
        """Get tools that are relevant for a specific focus area"""
        matching_tools = []
        for tool in self._tools.values():
            if focus_area in tool.focus_areas:
                matching_tools.append(tool)
        
        # Sort by priority (1=high priority first)
        return sorted(matching_tools, key=lambda t: t.priority)
    
    def get_tools_by_category(self, category: str) -> List[ToolMetadata]:
        """Get tools by category (core, phase1, phase2)"""
        return [tool for tool in self._tools.values() if tool.category == category]
    
    def get_tool_summary_for_prompt(self) -> List[str]:
        """Get formatted tool list for AI prompts"""
        summaries = []
        for tool in self._tools.values():
            summaries.append(f"{tool.name} - {tool.description}")
        return summaries
    
    def get_recommendation_context(self, focus_areas: List[str] = None) -> Dict[str, Any]:
        """
        Get structured tool information optimized for recommendation prompts
        
        Args:
            focus_areas: Optional list of focus areas to filter tools
            
        Returns:
            Dict with tools organized by relevance for AI recommendation
        """
        if focus_areas:
            relevant_tools = []
            for focus_area in focus_areas:
                relevant_tools.extend(self.get_tools_for_focus_area(focus_area))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_tools = []
            for tool in relevant_tools:
                if tool.name not in seen:
                    unique_tools.append(tool)
                    seen.add(tool.name)
            
            tools_to_use = unique_tools
        else:
            tools_to_use = list(self._tools.values())
        
        return {
            "total_tools": len(tools_to_use),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "focus_areas": tool.focus_areas,
                    "key_parameters": tool.key_parameters,
                    "priority": tool.priority
                }
                for tool in sorted(tools_to_use, key=lambda t: t.priority)
            ]
        }


# Global registry instance
tool_registry = ToolRegistry()