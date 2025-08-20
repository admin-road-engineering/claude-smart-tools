"""
Factory for creating properly configured ReviewOrchestrator instances.
Handles dependency injection and configuration of all required services.
"""
import logging
from typing import Dict, Optional

from ..tools.interfaces import IAnalysisTool
from ..services.session_manager import SessionManager
from ..services.tool_executor import ToolExecutor, DryRunToolExecutor
from ..services.intent_parser import IntentParser
from ..services.tool_selector import ToolSelector
from ..services.result_synthesizer import ResultSynthesizer
from ..services.file_integrity_validator import FileIntegrityValidator
from ..services.file_content_provider import FileContentProvider
from ..tools.base_sub_tool import BaseSubToolAdapter, GeminiToolImplementationAdapter
from ..clients.gemini_client import GeminiClient
from ..persistence.sqlite_session_store import SqliteSessionStore
from ..config import config
from .review_orchestrator import ReviewOrchestrator

logger = logging.getLogger(__name__)


class ReviewOrchestratorFactory:
    """
    Factory for creating ReviewOrchestrator instances with proper dependency injection.
    
    Handles:
    - Service instantiation with configuration
    - Tool registration and adaptation
    - Dependency wiring
    - Different execution modes (normal, dry-run, testing)
    """
    
    def __init__(self, gemini_client: GeminiClient = None):
        """
        Initialize factory with optional Gemini client.
        
        Args:
            gemini_client: Pre-configured Gemini client (will create if None)
        """
        self.gemini_client = gemini_client or GeminiClient()
    
    def create_orchestrator(self, 
                          available_tools: Dict[str, IAnalysisTool],
                          dry_run: bool = False,
                          session_store: SqliteSessionStore = None) -> ReviewOrchestrator:
        """
        Create fully configured ReviewOrchestrator with all dependencies.
        
        Args:
            available_tools: Dictionary mapping tool names to tool instances
            dry_run: Whether to use dry-run executor for testing
            session_store: Pre-configured session store (will create if None)
            
        Returns:
            Configured ReviewOrchestrator instance
        """
        try:
            logger.info(f"Creating ReviewOrchestrator with {len(available_tools)} tools (dry_run={dry_run})")
            
            # Create storage layer
            if session_store is None:
                session_store = SqliteSessionStore()
            
            # Create services with dependency injection
            session_manager = SessionManager(session_store)
            
            # Create file validation services
            file_content_provider = FileContentProvider()
            file_validator = FileIntegrityValidator(
                content_provider=file_content_provider,
                enable_filtering=True
            )
            
            tool_executor = self._create_tool_executor(dry_run, file_validator)
            
            intent_parser = IntentParser(
                gemini_client=self.gemini_client,
                config=None  # Uses default config
            )
            
            tool_selector = ToolSelector()
            
            result_synthesizer = ResultSynthesizer(
                gemini_client=self.gemini_client,
                config=None  # Uses default config
            )
            
            # Create orchestrator with injected dependencies
            orchestrator = ReviewOrchestrator(
                session_manager=session_manager,
                tool_executor=tool_executor,
                intent_parser=intent_parser,
                tool_selector=tool_selector,
                result_synthesizer=result_synthesizer,
                available_tools=available_tools,
                file_validator=file_validator
            )
            
            logger.info("ReviewOrchestrator created successfully")
            return orchestrator
            
        except Exception as e:
            logger.error(f"Failed to create ReviewOrchestrator: {e}")
            raise
    
    def create_with_gemini_tools(self, 
                               gemini_tool_implementations: Dict[str, any],
                               dry_run: bool = False) -> ReviewOrchestrator:
        """
        Create orchestrator with Gemini MCP tool implementations.
        
        Args:
            gemini_tool_implementations: Dictionary of Gemini tool implementations
            dry_run: Whether to use dry-run mode
            
        Returns:
            Configured ReviewOrchestrator with adapted tools
        """
        try:
            # Adapt Gemini tools to IAnalysisTool interface
            adapted_tools = {}
            
            for tool_name, implementation in gemini_tool_implementations.items():
                adapted_tool = GeminiToolImplementationAdapter(
                    name=tool_name,
                    implementation=implementation,
                    description=f"Gemini-powered {tool_name} analysis"
                )
                adapted_tools[tool_name] = adapted_tool
            
            logger.info(f"Adapted {len(adapted_tools)} Gemini tools")
            return self.create_orchestrator(adapted_tools, dry_run)
            
        except Exception as e:
            logger.error(f"Failed to create orchestrator with Gemini tools: {e}")
            raise
    
    def create_with_base_tools(self, 
                             base_tools: Dict[str, any],
                             dry_run: bool = False) -> ReviewOrchestrator:
        """
        Create orchestrator with existing BaseTool implementations.
        
        Args:
            base_tools: Dictionary of BaseTool instances
            dry_run: Whether to use dry-run mode
            
        Returns:
            Configured ReviewOrchestrator with adapted tools
        """
        try:
            # Adapt BaseTool instances to IAnalysisTool interface
            adapted_tools = {}
            
            for tool_name, base_tool in base_tools.items():
                adapted_tool = BaseSubToolAdapter(base_tool)
                adapted_tools[tool_name] = adapted_tool
            
            logger.info(f"Adapted {len(adapted_tools)} BaseTool instances")
            return self.create_orchestrator(adapted_tools, dry_run)
            
        except Exception as e:
            logger.error(f"Failed to create orchestrator with base tools: {e}")
            raise
    
    def create_mixed_orchestrator(self,
                                base_tools: Dict[str, any] = None,
                                gemini_tools: Dict[str, any] = None,
                                dry_run: bool = False) -> ReviewOrchestrator:
        """
        Create orchestrator with mixed tool types (BaseTool + Gemini implementations).
        
        Args:
            base_tools: Dictionary of BaseTool instances
            gemini_tools: Dictionary of Gemini tool implementations  
            dry_run: Whether to use dry-run mode
            
        Returns:
            Configured ReviewOrchestrator with all adapted tools
        """
        try:
            all_adapted_tools = {}
            
            # Adapt BaseTool instances
            if base_tools:
                for tool_name, base_tool in base_tools.items():
                    adapted_tool = BaseSubToolAdapter(base_tool)
                    all_adapted_tools[tool_name] = adapted_tool
                logger.info(f"Adapted {len(base_tools)} BaseTool instances")
            
            # Adapt Gemini tool implementations
            if gemini_tools:
                for tool_name, implementation in gemini_tools.items():
                    adapted_tool = GeminiToolImplementationAdapter(
                        name=tool_name,
                        implementation=implementation,
                        description=f"Gemini-powered {tool_name} analysis"
                    )
                    all_adapted_tools[tool_name] = adapted_tool
                logger.info(f"Adapted {len(gemini_tools)} Gemini tools")
            
            if not all_adapted_tools:
                raise ValueError("No tools provided for orchestrator creation")
            
            return self.create_orchestrator(all_adapted_tools, dry_run)
            
        except Exception as e:
            logger.error(f"Failed to create mixed orchestrator: {e}")
            raise
    
    def _create_tool_executor(self, dry_run: bool, file_validator: FileIntegrityValidator = None):
        """Create appropriate tool executor based on execution mode"""
        
        if dry_run:
            return DryRunToolExecutor(mock_execution_time=0.1)
        else:
            from ..tools.interfaces import ToolExecutorConfig
            
            config_obj = ToolExecutorConfig(
                max_concurrency=getattr(config, 'comprehensive_tool_parallelism', 4),
                timeout_seconds=getattr(config, 'comprehensive_review_timeout', 300),
                retry_attempts=getattr(config, 'tool_retry_attempts', 2)
            )
            
            return ToolExecutor(config_obj, file_validator)
    
    @staticmethod
    def get_default_tool_registry() -> Dict[str, str]:
        """
        Get registry of default tool names and their purposes.
        
        Returns:
            Dictionary mapping tool names to descriptions
        """
        return {
            'config_validator': 'Validates configuration files for security and best practices',
            'accessibility_checker': 'Checks HTML/UI components for accessibility compliance',
            'test_coverage_analyzer': 'Analyzes test coverage and identifies testing gaps',
            'dependency_mapper': 'Maps dependencies and identifies architectural issues',
            'interface_inconsistency_detector': 'Finds naming pattern inconsistencies in code',
            'api_contract_checker': 'Validates API specifications and contracts',
            'performance_profiler': 'Profiles runtime performance and identifies bottlenecks'
        }
    
    def create_test_orchestrator(self) -> ReviewOrchestrator:
        """
        Create orchestrator configured for testing with mock tools.
        
        Returns:
            Test-configured ReviewOrchestrator with mock tools
        """
        # Create mock tools for testing
        mock_tools = {}
        
        for tool_name in self.get_default_tool_registry():
            mock_tool = self._create_mock_tool(tool_name)
            mock_tools[tool_name] = mock_tool
        
        return self.create_orchestrator(mock_tools, dry_run=True)
    
    def _create_mock_tool(self, tool_name: str) -> IAnalysisTool:
        """Create a mock tool implementation for testing"""
        
        class MockTool:
            def __init__(self, name: str):
                self.name = name
            
            async def execute(self, file_paths, context):
                from ..tools.interfaces import AnalysisResult, ToolStatus
                import asyncio
                
                await asyncio.sleep(0.05)  # Simulate work
                
                return AnalysisResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output={
                        'mock': True,
                        'files_analyzed': len(file_paths),
                        'recommendations': [f'Mock recommendation from {self.name}']
                    },
                    execution_time_seconds=0.05
                )
        
        return MockTool(tool_name)