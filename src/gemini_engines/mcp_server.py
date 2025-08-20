"""
Working MCP server with all 14 functional tools
Based on the working mcp__gemini-review__ tool implementations
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as e:
    print(f"Error importing MCP: {e}", file=sys.stderr)
    print("Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import all the existing working implementations
from .services.review_service import ReviewService
from .services.resilience_layer import ResilientReviewService
from .services.streaming_orchestrator import StreamingOrchestrator
from .persistence.sqlite_session_store import SqliteSessionStore
from .config import config, LOG_LEVEL_VALUE
from .constants.tool_names import *

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> str:
    """
    Serialize any object to JSON string, handling datetime and Pydantic models.
    """
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'model_dump'):  # Pydantic v2 model
            return obj.model_dump(mode="json")
        elif hasattr(obj, 'dict') and callable(obj.dict):  # Pydantic v1 model
            return json_serializer(obj.dict())
        elif hasattr(obj, '__dict__'):  # Other objects with __dict__
            return {k: json_serializer(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: json_serializer(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [json_serializer(item) for item in obj]
        else:
            return obj
    
    try:
        # First try to serialize the cleaned object
        cleaned = json_serializer(obj)
        return json.dumps(cleaned, indent=2)
    except Exception as e:
        # If that fails, just convert to string
        logger.warning(f"JSON serialization failed: {e}, falling back to str()")
        return str(obj)

class WorkingGeminiMcpServer:
    """Working MCP server with all 14 functional tools"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = Server("gemini-review-server")
        
        # Create session store for review_output
        session_store = SqliteSessionStore()
        base_review_service = ReviewService(
            session_repo=session_store,
            analytics_repo=session_store,
            config=config
        )
        
        # Create streaming orchestrator with 4GB memory limit
        streaming_orchestrator = StreamingOrchestrator(config)
        
        # Wrap with resilient service (will enforce memory limit)
        self.review_service = ResilientReviewService(
            core_review_service=base_review_service,
            streaming_orchestrator=streaming_orchestrator,
            config=config
        )
        
        self.setup_handlers()
        
        logger.info("Working Gemini MCP Server initialized with all 13 tools + 4GB memory protection")
    
    def setup_handlers(self):
        """Setup MCP protocol handlers with all 13 working tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                # Core collaborative review tool (our unique contribution)
                Tool(
                    name="review_output",
                    description="Collaborative review using multi-round dialogue between Claude and Gemini for comprehensive technical analysis.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output": {"type": "string", "description": "Code or plan to review"},
                            "file_path": {"type": "string", "description": "Path to file containing content to review"},
                            "is_plan": {"type": "boolean", "default": True, "description": "Whether content is a plan (true) or code (false)"},
                            "focus": {"type": "string", "enum": ["all", "security", "performance", "architecture"], "default": "all"},
                            "context": {"type": "string", "description": "Additional context"},
                            "detail_level": {"type": "string", "enum": ["summary", "detailed", "comprehensive"], "default": "detailed"},
                            "response_style": {"type": "string", "enum": ["concise", "detailed", "executive"], "default": "detailed", "description": "Response verbosity style"},
                            "task_id": {"type": "string", "description": "Optional task identifier"},
                            "claude_response": {"type": "string", "description": "Claude's responses to previous questions"}
                        }
                    }
                ),
                
                # Original 7 working tools (recreated based on working mcp__gemini-review__ versions)
                Tool(
                    name="analyze_code",
                    description="Comprehensive code analysis with 1M token context. Combines file reading, codebase analysis, dependency mapping, and refactoring preparation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paths": {"type": "array", "items": {"type": "string"}, "description": "File or directory paths to analyze"},
                            "analysis_type": {"type": "string", "enum": ["overview", "dependencies", "refactor_prep", "architecture", "research"], "default": "overview"},
                            "output_format": {"type": "string", "enum": ["text", "markdown"], "default": "text"},
                            "question": {"type": "string", "description": "Specific question to answer about the code"},
                            "verbose": {"type": "boolean", "default": True}
                        },
                        "required": ["paths"]
                    }
                ),
                
                Tool(
                    name="search_code", 
                    description="Semantic code search with contextual understanding. Finds patterns and explains their usage across the codebase.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "What to search for (text, regex pattern, or word)"},
                            "paths": {"type": "array", "items": {"type": "string"}, "description": "Paths to search within"},
                            "search_type": {"type": "string", "enum": ["text", "regex", "word"], "default": "text"},
                            "case_sensitive": {"type": "boolean", "default": False},
                            "context_question": {"type": "string", "description": "What you want to understand about the results"},
                            "output_format": {"type": "string", "enum": ["text", "markdown"], "default": "text"}
                        },
                        "required": ["query"]
                    }
                ),
                
                Tool(
                    name="check_quality",
                    description="Comprehensive quality analysis including test coverage, security vulnerabilities, and performance issues.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paths": {"type": "array", "items": {"type": "string"}, "description": "Code paths to analyze"},
                            "check_type": {"type": "string", "enum": ["all", "tests", "security", "performance"], "default": "all"},
                            "test_paths": {"type": "array", "items": {"type": "string"}, "description": "Test file paths"},
                            "verbose": {"type": "boolean", "default": True},
                            "output_format": {"type": "string", "enum": ["text", "markdown"], "default": "text"}
                        },
                        "required": ["paths"]
                    }
                ),
                
                Tool(
                    name="analyze_docs",
                    description="Analyze and synthesize documentation from multiple sources including local files and web pages using Gemini's large context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sources": {"type": "array", "items": {"type": "string"}, "description": "Local file paths or URLs to analyze"},
                            "questions": {"type": "array", "items": {"type": "string"}, "description": "Specific questions to answer from the documentation"},
                            "synthesis_type": {"type": "string", "enum": ["summary", "comparison", "implementation_guide", "api_reference"], "default": "summary"}
                        },
                        "required": ["sources"]
                    }
                ),
                
                Tool(
                    name="analyze_logs",
                    description="Analyze log files to identify patterns, errors, and performance issues across multiple files.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "log_paths": {"type": "array", "items": {"type": "string"}, "description": "Log file or directory paths"},
                            "focus": {"type": "string", "enum": ["errors", "performance", "patterns", "timeline", "all"], "default": "all"},
                            "time_range": {"type": "string", "description": "Optional time range to focus on"}
                        },
                        "required": ["log_paths"]
                    }
                ),
                
                Tool(
                    name="analyze_database",
                    description="Analyze database schemas, migrations, and cross-repository relationships for architectural understanding.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema_paths": {"type": "array", "items": {"type": "string"}, "description": "Schema, migration, or model file paths"},
                            "analysis_type": {"type": "string", "enum": ["schema", "migrations", "relationships", "optimization"], "default": "schema"},
                            "repo_paths": {"type": "array", "items": {"type": "string"}, "description": "Repository paths for cross-repo analysis"}
                        },
                        "required": ["schema_paths"]
                    }
                ),
                
                # Phase 1 Enhanced Tools (6 additional tools)
                Tool(
                    name="performance_profiler",
                    description="Runtime performance analysis with timing metrics, memory usage, and bottleneck identification.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target_operation": {"type": "string", "description": "Operation or script to profile"},
                            "profile_type": {"type": "string", "enum": ["cpu", "memory", "io", "comprehensive"], "default": "comprehensive"}
                        },
                        "required": ["target_operation"]
                    }
                ),
                
                Tool(
                    name="config_validator",
                    description="Configuration file validation with security analysis and deprecated pattern detection.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "config_paths": {"type": "array", "items": {"type": "string"}, "description": "Configuration file paths to validate"},
                            "validation_type": {"type": "string", "enum": ["security", "completeness", "syntax", "all"], "default": "all"}
                        },
                        "required": ["config_paths"]
                    }
                ),
                
                Tool(
                    name="api_contract_checker",
                    description="OpenAPI/Swagger specification validation with breaking change detection.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spec_paths": {"type": "array", "items": {"type": "string"}, "description": "OpenAPI/Swagger specification file paths"},
                            "comparison_mode": {"type": "string", "enum": ["standalone", "compare_versions", "breaking_changes"], "default": "standalone"}
                        },
                        "required": ["spec_paths"]
                    }
                ),
                
                Tool(
                    name="analyze_test_coverage",
                    description="AST-based test coverage analysis with gap identification and priority scoring.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_paths": {"type": "array", "items": {"type": "string"}, "description": "Source code paths to analyze for test coverage"},
                            "mapping_strategy": {"type": "string", "enum": ["convention", "directory", "docstring"], "default": "convention"}
                        },
                        "required": ["source_paths"]
                    }
                ),
                
                Tool(
                    name="map_dependencies",
                    description="Dependency graph analysis with circular detection and architectural insights.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_paths": {"type": "array", "items": {"type": "string"}, "description": "Project directories to analyze for dependencies"},
                            "analysis_depth": {"type": "string", "enum": ["immediate", "transitive", "full"], "default": "transitive"}
                        },
                        "required": ["project_paths"]
                    }
                ),
                
                Tool(
                    name="interface_inconsistency_detector",
                    description="AST-based analysis for code naming pattern mismatches and interface inconsistencies.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_paths": {"type": "array", "items": {"type": "string"}, "description": "Source code paths to analyze for inconsistencies"},
                            "pattern_types": {"type": "array", "items": {"type": "string"}, "enum": ["naming", "parameters", "return_types", "documentation"], "default": ["naming", "parameters"]}
                        },
                        "required": ["source_paths"]
                    }
                ),
                
                # New comprehensive review tool
                Tool(
                    name="full_analysis",
                    description="Orchestrates multiple analysis tools for comprehensive AI code reviews with multi-turn dialogue. Covers 8 review types: functional, security, maintainability, performance, debugging, compliance, architecture, usability.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Session task ID (None for new session)"},
                            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to analyze"},
                            "focus": {"type": "string", "enum": ["all", "functional", "security", "maintainability", "performance", "debugging", "compliance", "architecture", "usability"], "default": "all"},
                            "claude_response": {"type": "string", "description": "Claude's response in ongoing dialogue"},
                            "context": {"type": "string", "description": "Additional context for review"},
                            "autonomous": {"type": "boolean", "description": "Run in autonomous mode (true) or dialogue mode (false). Default is false for interactive dialogue.", "default": False}
                        }
                    }
                ),
                
                # Flow tools for common analysis patterns
                Tool(
                    name="security_audit_flow",
                    description="Complete security audit flow: check_quality(security) → config_validator → review_output. Can output as review dialogue, JSON, report, or tasks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to analyze for security"},
                            "output_format": {"type": "string", "enum": ["review", "json", "report", "tasks"], "default": "review", "description": "Output format"},
                            "interactive": {"type": "boolean", "default": False, "description": "Enable interactive dialogue"}
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="architecture_review_flow",
                    description="Architecture analysis flow: analyze_code → map_dependencies → review_output/report. Comprehensive architecture assessment.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to analyze for architecture"},
                            "output_format": {"type": "string", "enum": ["review", "json", "report"], "default": "review", "description": "Output format"},
                            "focus": {"type": "string", "enum": ["structure", "patterns", "dependencies"], "default": "structure", "description": "Architecture focus area"}
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="test_strategy_flow",
                    description="Test strategy flow: analyze_test_coverage → check_quality(untested) → generate tasks. Produces prioritized testing tasks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string"}, "description": "Source files to analyze for test coverage"},
                            "output_format": {"type": "string", "enum": ["tasks", "json", "report", "review"], "default": "tasks", "description": "Output format"}
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="performance_audit_flow",
                    description="Performance analysis flow: performance_profiler → analyze_logs → review_output/metrics. Identifies bottlenecks and optimization opportunities.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to analyze (for finding logs)"},
                            "target_operation": {"type": "string", "description": "Specific operation to profile"},
                            "output_format": {"type": "string", "enum": ["report", "json", "review"], "default": "report", "description": "Output format"}
                        },
                        "required": ["files"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                if name == "review_output":
                    return await self._handle_review_output(arguments)
                elif name == "full_analysis":
                    return await self._handle_full_analysis(arguments)
                elif name in ["security_audit_flow", "architecture_review_flow", 
                              "test_strategy_flow", "performance_audit_flow"]:
                    return await self._handle_flow_tool(name, arguments)
                else:
                    # For all other tools, delegate to the working mcp__gemini-review__ implementations
                    return await self._delegate_to_working_tool(name, arguments)
                    
            except Exception as e:
                logger.error(f"Tool execution failed for {name}: {e}")
                return [TextContent(type="text", text=f"Tool execution failed: {str(e)}")]
    
    async def _handle_review_output(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle the collaborative review tool using our ReviewService"""
        try:
            # Import ReviewRequest model
            from .models.review_request import ReviewRequest
            
            # Create ReviewRequest object from arguments
            review_request = ReviewRequest(
                output=arguments.get("output"),
                file_path=arguments.get("file_path"),
                is_plan=arguments.get("is_plan", True),
                focus=arguments.get("focus", "all"),
                context=arguments.get("context"),
                detail_level=arguments.get("detail_level", "detailed"),
                response_style=arguments.get("response_style", "detailed"),
                task_id=arguments.get("task_id"),
                claude_response=arguments.get("claude_response")
            )
            
            # Pass the ReviewRequest object to the service
            result = await self.review_service.process_review_request(review_request)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            logger.error(f"Review workflow failed: {e}")
            return [TextContent(type="text", text=f"Review failed: {str(e)}")]
    
    async def _handle_flow_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle flow tools that orchestrate multiple tools"""
        try:
            # Import flow tools and dependencies
            from .tools.flow_tools import FlowTools, OutputFormat
            
            # Initialize flow tools if not already done
            if not hasattr(self, '_flow_tools'):
                # Get existing tool implementations
                from .tools.gemini_tool_wrapper import GeminiToolWrapper
                from .services.gemini_tool_implementations import GeminiToolImplementations
                from .clients.gemini_client import GeminiClient
                
                tool_impl = GeminiToolImplementations()
                gemini_client = GeminiClient()
                
                # Create wrapped sub-tools for flow tools
                sub_tools = {
                    'check_quality': GeminiToolWrapper(
                        'check_quality', tool_impl.check_quality, gemini_client
                    ),
                    'config_validator': GeminiToolWrapper(
                        'config_validator', tool_impl.config_validator, gemini_client
                    ),
                    'analyze_code': GeminiToolWrapper(
                        'analyze_code', tool_impl.analyze_code, gemini_client
                    ),
                    'map_dependencies': GeminiToolWrapper(
                        'map_dependencies', tool_impl.map_dependencies, gemini_client
                    ),
                    'analyze_test_coverage': GeminiToolWrapper(
                        'analyze_test_coverage', tool_impl.analyze_test_coverage, gemini_client
                    ),
                    'performance_profiler': GeminiToolWrapper(
                        'performance_profiler', tool_impl.performance_profiler, gemini_client
                    ),
                    'analyze_logs': GeminiToolWrapper(
                        'analyze_logs', tool_impl.analyze_logs, gemini_client
                    ),
                    'review_output': self.review_service  # Use existing review service
                }
                
                self._flow_tools = FlowTools(sub_tools)
            
            # Convert output_format string to enum
            output_format_str = arguments.get('output_format', 'review')
            output_format = OutputFormat(output_format_str)
            
            # Call the appropriate flow
            if name == "security_audit_flow":
                result = await self._flow_tools.security_audit_flow(
                    files=arguments['files'],
                    output_format=output_format,
                    interactive=arguments.get('interactive', False)
                )
            elif name == "architecture_review_flow":
                result = await self._flow_tools.architecture_review_flow(
                    files=arguments['files'],
                    output_format=output_format,
                    focus=arguments.get('focus', 'structure')
                )
            elif name == "test_strategy_flow":
                result = await self._flow_tools.test_strategy_flow(
                    files=arguments['files'],
                    output_format=output_format
                )
            elif name == "performance_audit_flow":
                result = await self._flow_tools.performance_audit_flow(
                    files=arguments['files'],
                    target_operation=arguments.get('target_operation'),
                    output_format=output_format
                )
            else:
                return [TextContent(type="text", text=f"Unknown flow tool: {name}")]
            
            return [TextContent(type="text", text=str(result))]
            
        except Exception as e:
            logger.error(f"Flow tool {name} failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [TextContent(type="text", text=f"Flow tool execution failed: {str(e)}")]
    
    async def _handle_full_analysis(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle the full analysis tool with Pydantic validation"""
        try:
            # Import and validate input arguments
            from .models.tool_requests import FullAnalysisRequest
            
            try:
                validated_request = FullAnalysisRequest(**arguments)
            except ValueError as validation_error:
                logger.warning(f"Input validation failed for full_analysis: {validation_error}")
                return [TextContent(type="text", text=f"Input validation failed: {validation_error}")]
            
            # Import and create full analysis tool
            from .tools.full_analysis_tool import FullAnalysisTool
            from .tools.accessibility_checker import AccessibilityChecker
            from .tools.gemini_tool_wrapper import GeminiToolWrapper
            from .clients.gemini_client import GeminiClient
            
            # Initialize tool instances if not already done
            if not hasattr(self, '_full_analysis_tool'):
                # Get existing tool implementations
                from .services.gemini_tool_implementations import GeminiToolImplementations
                tool_impl = GeminiToolImplementations()
                gemini_client = GeminiClient()
                
                # Create wrapped sub-tools dictionary using standardized tool names
                sub_tools = {
                    # Core analysis tools
                    ANALYZE_CODE: GeminiToolWrapper(
                        ANALYZE_CODE,
                        tool_impl.analyze_code,
                        gemini_client
                    ),
                    SEARCH_CODE: GeminiToolWrapper(
                        SEARCH_CODE,
                        tool_impl.search_code,
                        gemini_client
                    ),
                    CHECK_QUALITY: GeminiToolWrapper(
                        CHECK_QUALITY,
                        tool_impl.check_quality,
                        gemini_client
                    ),
                    ANALYZE_DOCS: GeminiToolWrapper(
                        ANALYZE_DOCS,
                        tool_impl.analyze_docs,
                        gemini_client
                    ),
                    ANALYZE_LOGS: GeminiToolWrapper(
                        ANALYZE_LOGS,
                        tool_impl.analyze_logs,
                        gemini_client
                    ),
                    ANALYZE_DATABASE: GeminiToolWrapper(
                        ANALYZE_DATABASE,
                        tool_impl.analyze_database,
                        gemini_client
                    ),
                    # Enhanced tools
                    TEST_COVERAGE_ANALYZER: GeminiToolWrapper(
                        TEST_COVERAGE_ANALYZER, 
                        tool_impl.analyze_test_coverage,
                        gemini_client
                    ),
                    CONFIG_VALIDATOR: GeminiToolWrapper(
                        CONFIG_VALIDATOR,
                        tool_impl.config_validator,
                        gemini_client
                    ),
                    DEPENDENCY_MAPPER: GeminiToolWrapper(
                        DEPENDENCY_MAPPER,
                        tool_impl.map_dependencies,
                        gemini_client
                    ),
                    API_CONTRACT_CHECKER: GeminiToolWrapper(
                        API_CONTRACT_CHECKER,
                        tool_impl.api_contract_checker,
                        gemini_client
                    ),
                    INTERFACE_INCONSISTENCY_DETECTOR: GeminiToolWrapper(
                        INTERFACE_INCONSISTENCY_DETECTOR,
                        tool_impl.interface_inconsistency_detector,
                        gemini_client
                    ),
                    PERFORMANCE_PROFILER: GeminiToolWrapper(
                        PERFORMANCE_PROFILER,
                        tool_impl.performance_profiler,
                        gemini_client
                    )
                    # Temporarily disabled: ACCESSIBILITY_CHECKER: AccessibilityChecker()
                }
                
                # Create comprehensive tool
                session_store = SqliteSessionStore()
                
                self._full_analysis_tool = FullAnalysisTool(
                    gemini_client=gemini_client,
                    session_repo=session_store,
                    settings=config,
                    sub_tools=sub_tools
                )
            
            # Execute comprehensive review using validated data
            # Use the autonomous parameter from the request, defaulting to False (dialogue mode)
            autonomous = getattr(validated_request, 'autonomous', False)
            
            result = await self._full_analysis_tool.execute_full_analysis(
                task_id=validated_request.task_id,
                files=validated_request.files,
                focus=validated_request.focus,
                claude_response=validated_request.claude_response,
                context=validated_request.context,
                autonomous=autonomous
            )
            
            # Return the result directly as formatted text (it's already a markdown string)
            # Don't JSON-serialize it as that would escape all the newlines
            return [TextContent(type="text", text=str(result))]
            
        except Exception as e:
            logger.error(f"Comprehensive review failed: {e}")
            return [TextContent(type="text", text=f"Comprehensive review failed: {str(e)}")]
    
    async def _delegate_to_working_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Delegate to the REAL working Gemini tool implementations with Pydantic validation"""
        try:
            # Import validation utilities
            from .models.tool_requests import validate_tool_request
            from .services.gemini_tool_implementations import GeminiToolImplementations
            
            # Validate input arguments using Pydantic models
            try:
                validated_request = validate_tool_request(name, arguments)
                # Convert back to dict for compatibility with existing tool implementations
                validated_args = validated_request.model_dump(exclude_unset=True)
            except ValueError as validation_error:
                logger.warning(f"Input validation failed for {name}: {validation_error}")
                return [TextContent(type="text", text=f"Input validation failed: {validation_error}")]
            
            # Create instance if not exists
            if not hasattr(self, '_tool_impl'):
                self._tool_impl = GeminiToolImplementations()
            
            # Call the appropriate tool with validated arguments
            if name == "analyze_code":
                result = await self._tool_impl.analyze_code(**validated_args)
            elif name == "search_code":
                result = await self._tool_impl.search_code(**validated_args)
            elif name == "check_quality":
                result = await self._tool_impl.check_quality(**validated_args)
            elif name == "analyze_docs":
                result = await self._tool_impl.analyze_docs(**validated_args)
            elif name == "analyze_logs":
                result = await self._tool_impl.analyze_logs(**validated_args)
            elif name == "analyze_database":
                result = await self._tool_impl.analyze_database(**validated_args)
            elif name == "performance_profiler":
                result = await self._tool_impl.performance_profiler(**validated_args)
            elif name == "config_validator":
                result = await self._tool_impl.config_validator(**validated_args)
            elif name == "api_contract_checker":
                result = await self._tool_impl.api_contract_checker(**validated_args)
            elif name == "analyze_test_coverage":
                result = await self._tool_impl.analyze_test_coverage(**validated_args)
            elif name == "map_dependencies":
                result = await self._tool_impl.map_dependencies(**validated_args)
            elif name == "interface_inconsistency_detector":
                result = await self._tool_impl.interface_inconsistency_detector(**validated_args)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            return [TextContent(type="text", text=str(result))]
            
        except Exception as e:
            logger.error(f"Tool execution failed for {name}: {e}")
            return [TextContent(type="text", text=f"Tool execution failed: {str(e)}. Please check logs for details.")]
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

# For backward compatibility
GeminiMcpServer = WorkingGeminiMcpServer