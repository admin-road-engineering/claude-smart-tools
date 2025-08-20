"""
Smart Tools MCP Server
Consolidated 7-tool interface with intelligent routing
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

# Import smart tools - use absolute imports for MCP execution
import sys
import os

# Add the src directory to Python path for proper imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Direct absolute imports (no relative imports to avoid MCP execution issues)
from smart_tools.understand_tool import UnderstandTool
from smart_tools.investigate_tool import InvestigateTool
from smart_tools.validate_tool import ValidateTool  
from smart_tools.collaborate_tool import CollaborateTool
from smart_tools.full_analysis_tool import FullAnalysisTool
from smart_tools.propose_tests_tool import ProposeTestsTool
from smart_tools.deploy_tool import DeployTool
from smart_tools.base_smart_tool import SmartToolResult
from engines.original_tool_adapter import OriginalToolAdapter
from routing.intent_analyzer import IntentAnalyzer, ToolIntent
from services.cpu_throttler import CPUThrottler
from config import config

logger = logging.getLogger(__name__)


class SmartToolsMcpServer:
    """MCP server with 7 intelligent tools"""
    
    def __init__(self):
        self.server = Server("claude-smart-tools")
        self.engines = {}
        self.smart_tools = {}
        
        # Initialize CPU throttler singleton early
        try:
            self.cpu_throttler = CPUThrottler.get_instance(config)
            logger.info("CPU throttler initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize CPU throttler: {e}")
            self.cpu_throttler = None
        
        self.setup_handlers()
        
        logger.info("Smart Tools MCP Server initialized with 7 intelligent tools and CPU throttling")
    
    async def initialize_engines(self):
        """Initialize engine wrappers from local gemini_engines - self-contained approach"""
        try:
            import os
            
            # Environment diagnostics for debugging  
            logger.info("=== Engine Initialization Diagnostics ===")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Python executable: {sys.executable}")
            
            # Enhanced virtual environment detection for Claude Code + VENV troubleshooting
            in_venv = (hasattr(sys, 'real_prefix') or 
                      (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
            logger.info(f"Virtual environment detected: {in_venv}")
            if in_venv:
                logger.info(f"Python prefix: {sys.prefix}")
                logger.info(f"Base prefix: {getattr(sys, 'base_prefix', 'N/A')}")
                logger.info(f"VENV Mode: Running in virtual environment - enhanced compatibility enabled")
            else:
                logger.info(f"Python prefix: {sys.prefix}")
                logger.info(f"Standard Mode: Running in base Python installation")
            
            # Environment variable diagnostics and fallback detection
            api_key = os.environ.get('GOOGLE_API_KEY')
            api_key2 = os.environ.get('GOOGLE_API_KEY2')
            logger.info(f"GOOGLE_API_KEY available: {'YES' if api_key else 'NO'}")
            logger.info(f"GOOGLE_API_KEY2 available: {'YES' if api_key2 else 'NO'}")
            
            # Enhanced fallback for Claude Desktop + VENV environment variable issues
            if not api_key and not api_key2:
                logger.warning("⚠️ No API keys found - attempting fallback detection")
                
                # Check if variables show as unexpanded (Claude Desktop VENV bug symptom)
                raw_key1 = os.environ.get('GOOGLE_API_KEY', '')
                raw_key2 = os.environ.get('GOOGLE_API_KEY2', '')
                if raw_key1.startswith('%') or raw_key2.startswith('%'):
                    logger.error(f"🚨 CRITICAL: Environment variables appear unexpanded: KEY1='{raw_key1}', KEY2='{raw_key2}'")
                    logger.error("This indicates Claude Desktop + VENV compatibility issue")
                    logger.error("SOLUTION: Update claude_desktop_config.json to use actual API key values instead of %VARIABLE% syntax")
                
                # Try to load from system environment as fallback
                try:
                    import subprocess
                    result = subprocess.run(['echo', '%GOOGLE_API_KEY%'], shell=True, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip() != '%GOOGLE_API_KEY%':
                        api_key = result.stdout.strip()
                        logger.info("✅ Recovered API key via fallback method")
                    else:
                        logger.error("💥 FALLBACK FAILED: Cannot access API keys - Smart Tools will not function")
                except Exception as e:
                    logger.error(f"Fallback environment variable detection failed: {e}")
            elif api_key and api_key2:
                logger.info("🔑 API Key Configuration: Dual key setup detected - optimal for rate limit handling")
            
            # Final API key status
            has_api_key = bool(api_key or api_key2)
            logger.info(f"Final API key status: {'AVAILABLE' if has_api_key else 'MISSING'}")
            
            # Import from local gemini_engines - self-contained approach like gemini-review
            logger.info("Attempting imports from local gemini_engines...")
            try:
                from gemini_engines.services.gemini_tool_implementations import GeminiToolImplementations
                logger.info("✅ Successfully imported GeminiToolImplementations")
            except Exception as e:
                logger.error(f"❌ Failed to import GeminiToolImplementations: {e}")
                raise
                
            try:
                from gemini_engines.clients.gemini_client import GeminiClient
                logger.info("✅ Successfully imported GeminiClient")
            except Exception as e:
                logger.error(f"❌ Failed to import GeminiClient: {e}")
                raise
                
            try:
                import google.generativeai as genai
                logger.info("✅ Successfully imported google.generativeai")
            except Exception as e:
                logger.error(f"❌ Failed to import google.generativeai: {e}")
                raise
            
            # Create instances
            logger.info("Creating GeminiToolImplementations instance...")
            try:
                tool_impl = GeminiToolImplementations()
                logger.info("✅ Successfully created GeminiToolImplementations")
            except Exception as e:
                logger.error(f"❌ Failed to create GeminiToolImplementations: {e}")
                raise
                
            logger.info("Creating GeminiClient instance...")
            try:
                gemini_client = GeminiClient(config)
                logger.info("✅ Successfully created GeminiClient")
            except Exception as e:
                logger.error(f"❌ Failed to create GeminiClient: {e}")
                raise
            
            # Configure Gemini API
            if api_key:
                genai.configure(api_key=api_key)
                logger.info(f"✅ Configured Gemini API with key: {api_key[:10]}...")
            else:
                logger.warning("⚠️ No GOOGLE_API_KEY found in environment")
            
            # Self-contained imports - no path manipulation needed
            
            # Create engine wrappers using the factory with monkey patch
            logger.info("Importing EngineFactory...")
            try:
                from engines.engine_wrapper import EngineFactory
                logger.info("✅ Successfully imported EngineFactory")
            except Exception as e:
                logger.error(f"❌ Failed to import EngineFactory: {e}")
                raise
            
            # Use factory method to create engines with WindowsPath monkey patch applied
            logger.info("Creating engines from original tool implementations...")
            try:
                self.engines = EngineFactory.create_engines_from_original(tool_impl)
                logger.info(f"✅ Successfully created {len(self.engines)} engines via factory")
            except Exception as e:
                logger.error(f"❌ Failed to create engines via factory: {e}")
                raise
            
            # Add the missing engines that aren't in the factory method
            from engines.engine_wrapper import EngineWrapper
            additional_engines = {
                'review_output': tool_impl.review_output,
                'full_analysis': tool_impl.full_analysis
            }
            for engine_name, method in additional_engines.items():
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
                'collaborate': CollaborateTool(self.engines),
                'propose_tests': ProposeTestsTool(self.engines),
                'deploy': DeployTool(self.engines)
            }
            
            # Initialize full_analysis tool with both engines and other smart tools
            self.smart_tools['full_analysis'] = FullAnalysisTool(self.engines, self.smart_tools)
            
            logger.info(f"Initialized {len(self.engines)} engines and {len(self.smart_tools)} smart tools")
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize engines: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Enhanced fallback to at least provide all 7 tools with empty engines
            logger.warning("⚠️ Falling back to empty engines - tools will have limited functionality")
            self.engines = {}
            self.smart_tools = {
                'understand': UnderstandTool({}),
                'investigate': InvestigateTool({}),
                'validate': ValidateTool({}),
                'collaborate': CollaborateTool({}),
                'propose_tests': ProposeTestsTool({}),
                'deploy': DeployTool({}),
                'full_analysis': FullAnalysisTool({}, {})
            }
    
    def setup_handlers(self):
        """Setup MCP protocol handlers for the 7 smart tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="understand",
                    description="Deep comprehension tool for unfamiliar codebases, architectures, and patterns. Routes to analyze_code + search_code + analyze_docs + map_dependencies.",
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
                    description="Problem-solving tool for debugging issues, finding root causes, and tracing problems. Routes to search_code + check_quality + analyze_logs + performance_profiler + analyze_database + map_dependencies.",
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
                    description="Quality assurance tool for checking security, performance, standards, and consistency. Routes to check_quality + config_validator + interface_inconsistency_detector + analyze_test_coverage + api_contract_checker + analyze_database + map_dependencies.",
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
                    name="propose_tests",
                    description="Test coverage analysis and test generation tool. Routes to analyze_code + analyze_test_coverage + search_code + check_quality to identify untested areas and generate prioritized test proposals.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files to analyze for test coverage"
                            },
                            "test_type": {
                                "type": "string",
                                "enum": ["unit", "integration", "security", "performance", "all"],
                                "default": "all",
                                "description": "Type of tests to focus on"
                            },
                            "coverage_threshold": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "default": 0.8,
                                "description": "Target coverage threshold (0.0-1.0)"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "default": "high",
                                "description": "Priority level for test proposals"
                            }
                        },
                        "required": ["files"]
                    }
                ),
                
                Tool(
                    name="deploy",
                    description="Pre-deployment validation and readiness assessment tool. Routes to config_validator + api_contract_checker + check_quality + analyze_database + performance_profiler for comprehensive deployment safety checks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files to validate for deployment"
                            },
                            "deployment_stage": {
                                "type": "string",
                                "enum": ["development", "staging", "production"],
                                "default": "production",
                                "description": "Target deployment stage"
                            },
                            "validation_level": {
                                "type": "string",
                                "enum": ["essential", "standard", "comprehensive"],
                                "default": "comprehensive",
                                "description": "Level of validation to perform"
                            },
                            "environment": {
                                "type": "string",
                                "description": "Target deployment environment (optional)"
                            }
                        },
                        "required": ["files"]
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
        elif tool_name == "propose_tests":
            return await self._handle_propose_tests(arguments)
        elif tool_name == "deploy":
            return await self._handle_deploy(arguments)
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
    
    async def _handle_propose_tests(self, arguments: Dict[str, Any]) -> str:
        """Handle propose_tests tool calls"""
        try:
            propose_tests_tool = self.smart_tools.get('propose_tests')
            if not propose_tests_tool:
                return "Propose tests tool not available"
            
            result = await propose_tests_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Test proposal generation failed: {str(e)}"
    
    async def _handle_deploy(self, arguments: Dict[str, Any]) -> str:
        """Handle deploy tool calls"""
        try:
            deploy_tool = self.smart_tools.get('deploy')
            if not deploy_tool:
                return "Deploy tool not available"
            
            result = await deploy_tool.execute(**arguments)
            return self._format_smart_tool_result(result)
            
        except Exception as e:
            return f"Deployment validation failed: {str(e)}"
    
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
        """Run the MCP server with CPU throttling"""
        # Initialize engines before starting server
        await self.initialize_engines()
        
        # Log CPU throttling status
        if self.cpu_throttler:
            stats = self.cpu_throttler.get_throttling_stats()
            logger.info(f"CPU throttling active: max_cpu={stats['max_cpu_percent']}%, "
                       f"yield_interval={stats['yield_interval_ms']}ms")
        else:
            logger.warning("CPU throttling not available - system may experience freezing under heavy load")
        
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