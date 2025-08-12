"""
Smart Tools MCP Server
Consolidated 5-tool interface with intelligent routing
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List
from datetime import datetime

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as e:
    print(f"Error importing MCP: {e}", file=sys.stderr)
    print("Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import smart tools
try:
    # Try relative imports first (when run as module)
    from .smart_tools.understand_tool import UnderstandTool
    from .smart_tools.investigate_tool import InvestigateTool
    from .smart_tools.validate_tool import ValidateTool
    from .smart_tools.collaborate_tool import CollaborateTool
    from .smart_tools.full_analysis_tool import FullAnalysisTool
    from .smart_tools.base_smart_tool import SmartToolResult
    from .engines.original_tool_adapter import OriginalToolAdapter
    from .routing.intent_analyzer import IntentAnalyzer, ToolIntent
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from smart_tools.understand_tool import UnderstandTool
    from smart_tools.investigate_tool import InvestigateTool
    from smart_tools.validate_tool import ValidateTool
    from smart_tools.collaborate_tool import CollaborateTool
    from smart_tools.full_analysis_tool import FullAnalysisTool
    from smart_tools.base_smart_tool import SmartToolResult
    from engines.original_tool_adapter import OriginalToolAdapter
    from routing.intent_analyzer import IntentAnalyzer, ToolIntent

logger = logging.getLogger(__name__)


class SmartToolsMcpServer:
    """MCP server with 5 intelligent tools"""
    
    def __init__(self):
        self.server = Server("claude-smart-tools")
        self.engines = {}
        self.smart_tools = {}
        self.setup_handlers()
        
        logger.info("Smart Tools MCP Server initialized with 5 intelligent tools")
    
    async def initialize_engines(self):
        """Initialize engine wrappers from original tool implementations"""
        try:
            # Change to gemini-engines directory for proper imports
            import os
            current_dir = os.getcwd()
            gemini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gemini-engines")
            
            logger.info(f"Initializing engines from {gemini_path}...")
            
            # Change directory and add to path for imports
            os.chdir(gemini_path)
            if gemini_path not in sys.path:
                sys.path.insert(0, gemini_path)
            
            # Now import the Gemini implementations directly
            from src.services.gemini_tool_implementations import GeminiToolImplementations
            from src.clients.gemini_client import GeminiClient
            
            # Create instances
            tool_impl = GeminiToolImplementations()
            gemini_client = GeminiClient()
            
            # Configure Gemini API
            import google.generativeai as genai
            api_key = os.environ.get('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                logger.info(f"Configured Gemini API with key: {api_key[:10]}...")
            
            # Restore to smart tools directory to import EngineWrapper
            os.chdir(current_dir)
            
            # Add smart tools src to path for imports
            smart_tools_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
            if smart_tools_src not in sys.path:
                sys.path.insert(0, smart_tools_src)
            
            # Create engine wrappers using the adapter
            from engines.engine_wrapper import EngineWrapper
            
            # Map of engine names to their methods
            engine_configs = {
                'analyze_code': tool_impl.analyze_code,
                'search_code': tool_impl.search_code,
                'check_quality': tool_impl.check_quality,
                'analyze_docs': tool_impl.analyze_docs,
                'analyze_logs': tool_impl.analyze_logs,
                'analyze_database': tool_impl.analyze_database,
                'performance_profiler': tool_impl.performance_profiler,
                'config_validator': tool_impl.config_validator,
                'api_contract_checker': tool_impl.api_contract_checker,
                'analyze_test_coverage': tool_impl.analyze_test_coverage,
                'map_dependencies': tool_impl.map_dependencies,
                'interface_inconsistency_detector': tool_impl.interface_inconsistency_detector,
                'review_output': tool_impl.review_output,
                'full_analysis': tool_impl.full_analysis
            }
            
            # Create wrappers
            self.engines = {}
            for engine_name, method in engine_configs.items():
                self.engines[engine_name] = EngineWrapper(
                    engine_name=engine_name,
                    original_function=method,
                    description=f'{engine_name} engine',
                    gemini_client=gemini_client
                )
            
            logger.info(f"Successfully initialized {len(self.engines)} engines: {list(self.engines.keys())}")
            
            # Initialize smart tools with engines
            self.smart_tools = {
                'understand': UnderstandTool(self.engines),
                'investigate': InvestigateTool(self.engines),
                'validate': ValidateTool(self.engines),
                'collaborate': CollaborateTool(self.engines)
            }
            
            # Initialize full_analysis tool with both engines and other smart tools
            self.smart_tools['full_analysis'] = FullAnalysisTool(self.engines, self.smart_tools)
            
            logger.info(f"Initialized {len(self.engines)} engines and {len(self.smart_tools)} smart tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize engines: {e}")
            # Fallback to empty engines for development
            self.engines = {}
            self.smart_tools = {'understand': UnderstandTool({})}
    
    def setup_handlers(self):
        """Setup MCP protocol handlers for the 5 smart tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="understand",
                    description="Deep comprehension tool for unfamiliar codebases, architectures, and patterns. Routes to analyze_code + search_code + analyze_docs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "File or directory paths to analyze"
                            },
                            "question": {
                                "type": "string", 
                                "description": "Specific question about the codebase (optional)"
                            },
                            "focus": {
                                "type": "string",
                                "enum": ["architecture", "patterns", "documentation", "overview"],
                                "default": "overview",
                                "description": "Focus area for understanding"
                            }
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="investigate",
                    description="Problem-solving tool for debugging issues, finding root causes, and tracing problems. Routes to search_code + check_quality + analyze_logs + performance_profiler.",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files to investigate"
                            },
                            "problem": {
                                "type": "string",
                                "description": "Description of the problem or issue"
                            },
                            "focus": {
                                "type": "string", 
                                "enum": ["debug", "performance", "errors", "root_cause"],
                                "default": "debug",
                                "description": "Investigation focus area"
                            }
                        },
                        "required": ["files", "problem"]
                    }
                ),
                
                Tool(
                    name="validate",
                    description="Quality assurance tool for checking security, performance, standards, and consistency. Routes to check_quality + config_validator + interface_inconsistency_detector.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array", 
                                "items": {"type": "string"},
                                "description": "Files to validate"
                            },
                            "validation_type": {
                                "type": "string",
                                "enum": ["security", "quality", "performance", "consistency", "all"],
                                "default": "all",
                                "description": "Type of validation to perform"
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "default": "medium", 
                                "description": "Minimum severity level to report"
                            }
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="collaborate",
                    description="Technical dialogue tool for reviews, discussions, and clarifying questions. Direct wrapper around review_output.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Code, plan, or content to discuss"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Path to file containing content"
                            },
                            "discussion_type": {
                                "type": "string",
                                "enum": ["review", "feedback", "brainstorm", "clarification"],
                                "default": "review",
                                "description": "Type of collaboration desired"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context for the discussion"
                            }
                        }
                    }
                ),
                
                Tool(
                    name="full_analysis",
                    description="Comprehensive orchestration tool for complex scenarios. Enhanced version that uses smart tools for better coordination.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"}, 
                                "description": "Files to analyze comprehensively"
                            },
                            "focus": {
                                "type": "string",
                                "enum": ["all", "security", "architecture", "performance", "quality"],
                                "default": "all",
                                "description": "Focus area for comprehensive analysis"
                            },
                            "autonomous": {
                                "type": "boolean",
                                "default": False,
                                "description": "Run autonomously or in dialogue mode"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context for analysis"
                            }
                        },
                        "required": ["files"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                # Initialize engines if not done yet
                if not self.engines:
                    await self.initialize_engines()
                
                result = await self._route_tool_call(name, arguments)
                return [TextContent(type="text", text=result)]
                
            except Exception as e:
                logger.error(f"Tool execution failed for {name}: {e}")
                return [TextContent(type="text", text=f"Tool execution failed: {str(e)}")]
    
    async def _route_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Route tool calls to appropriate smart tools"""
        
        if tool_name == "understand":
            return await self._handle_understand(arguments)
        elif tool_name == "investigate":
            return await self._handle_investigate(arguments)
        elif tool_name == "validate":
            return await self._handle_validate(arguments)
        elif tool_name == "collaborate":
            return await self._handle_collaborate(arguments)
        elif tool_name == "full_analysis":
            return await self._handle_full_analysis(arguments)
        else:
            return f"Unknown tool: {tool_name}"
    
    async def _handle_understand(self, arguments: Dict[str, Any]) -> str:
        """Handle understand tool calls"""
        try:
            understand_tool = self.smart_tools.get('understand')
            if not understand_tool:
                return "Understand tool not available"
            
            result = await understand_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Understanding analysis failed: {str(e)}"
    
    async def _handle_investigate(self, arguments: Dict[str, Any]) -> str:
        """Handle investigate tool calls"""
        try:
            investigate_tool = self.smart_tools.get('investigate')
            if not investigate_tool:
                return "Investigate tool not available"
            
            result = await investigate_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Investigation failed: {str(e)}"
    
    async def _handle_validate(self, arguments: Dict[str, Any]) -> str:
        """Handle validate tool calls"""
        try:
            validate_tool = self.smart_tools.get('validate')
            if not validate_tool:
                return "Validate tool not available"
            
            result = await validate_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Validation failed: {str(e)}"
    
    async def _handle_collaborate(self, arguments: Dict[str, Any]) -> str:
        """Handle collaborate tool calls"""
        try:
            collaborate_tool = self.smart_tools.get('collaborate')
            if not collaborate_tool:
                return "Collaborate tool not available"
            
            result = await collaborate_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Collaboration failed: {str(e)}"
    
    async def _handle_full_analysis(self, arguments: Dict[str, Any]) -> str:
        """Handle full analysis tool calls"""
        try:
            full_analysis_tool = self.smart_tools.get('full_analysis')
            if not full_analysis_tool:
                return "Full analysis tool not available"
            
            result = await full_analysis_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Full analysis failed: {str(e)}"
    
    def _format_smart_tool_result(self, result: SmartToolResult) -> str:
        """Format smart tool results for MCP response"""
        if not result.success:
            return f"❌ {result.tool_name.title()} Tool Failed\n{result.result}"
        
        formatted = [
            f"# ✅ {result.tool_name.title()} Tool Results",
            f"**Engines Used**: {', '.join(result.engines_used)}",
            f"**Routing Decision**: {result.routing_decision}",
            "",
            result.result
        ]
        
        if result.metadata:
            formatted.extend([
                "",
                "## 📊 Analysis Metadata",
                json.dumps(result.metadata, indent=2)
            ])
        
        return '\n'.join(formatted)
    
    async def run(self):
        """Run the MCP server"""
        # Initialize engines before starting server
        await self.initialize_engines()
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream, 
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    logging.basicConfig(level=logging.INFO)
    
    # Debug: Check environment variables at startup
    import os
    logger.info("=" * 60)
    logger.info("Smart Tools MCP Server Starting")
    logger.info(f"GOOGLE_API_KEY present: {'YES' if os.environ.get('GOOGLE_API_KEY') else 'NO'}")
    logger.info(f"GOOGLE_API_KEY2 present: {'YES' if os.environ.get('GOOGLE_API_KEY2') else 'NO'}")
    if os.environ.get('GOOGLE_API_KEY'):
        logger.info(f"API Key 1 prefix: {os.environ.get('GOOGLE_API_KEY')[:10]}")
    if os.environ.get('GOOGLE_API_KEY2'):
        logger.info(f"API Key 2 prefix: {os.environ.get('GOOGLE_API_KEY2')[:10]}")
    logger.info("=" * 60)
    
    server = SmartToolsMcpServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())