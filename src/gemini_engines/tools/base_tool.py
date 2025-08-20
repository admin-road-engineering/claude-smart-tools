"""
Base Tool Infrastructure for Tool-as-a-Service Pattern
Provides common structure for all enhanced tools in the Gemini MCP system
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ToolResult:
    """Standard result format for all tools"""
    success: bool
    tool_name: str
    timestamp: datetime
    core_results: Dict[str, Any]  # Raw analysis results from core utility
    ai_interpretation: Optional[str] = None  # Gemini's interpretation
    recommendations: List[str] = None  # Actionable recommendations
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

class BaseTool(ABC):
    """
    Abstract base class for Tool-as-a-Service pattern implementation
    
    Architecture:
    1. Core Utility: Pure analysis logic (no AI, no file I/O)
    2. File Validation: File Freshness Guardian integration
    3. AI Interpretation: Gemini provides intelligent insights
    4. Context Sharing: Tools can consume and produce context for other tools
    """
    
    def __init__(self, tool_name: str):
        """
        Initialize base tool with common properties
        
        Args:
            tool_name: Name of the tool for logging and identification
        """
        self.tool_name = tool_name
        self.logger = logging.getLogger(f"tools.{tool_name}")
        self.metrics = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_duration_ms": 0
        }
        
        # Context requirements - subclasses should override
        self._context_requirements = None
        self._context_contributions = None
        
    @abstractmethod
    def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Core utility function - pure analysis logic
        
        This method must:
        - Perform analysis without AI or external dependencies
        - Return structured, JSON-serializable results
        - Be independently testable and scriptable
        - Handle errors gracefully
        
        Args:
            files: List of file paths to analyze
            **kwargs: Tool-specific parameters
            
        Returns:
            Dictionary with analysis results
        """
        pass
    
    @abstractmethod
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get AI interpretation of core analysis results
        
        This method should:
        - Format core results for Gemini
        - Create appropriate prompts for interpretation
        - Return actionable insights and recommendations
        
        Args:
            core_results: Results from _core_utility
            context: Optional additional context for AI
            
        Returns:
            AI interpretation as formatted string
        """
        pass
    
    def validate_inputs(self, files: List[str], **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate inputs before processing
        
        Args:
            files: File paths to validate
            **kwargs: Additional parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not files:
            return False, "No files provided for analysis"
        
        # Check if files list is reasonable size
        if len(files) > 100:
            return False, f"Too many files ({len(files)}). Maximum 100 files allowed."
        
        # Tool-specific validation can be added in subclasses
        return True, None
    
    def format_results(self, result: ToolResult) -> str:
        """
        Format tool results for display
        
        Args:
            result: ToolResult to format
            
        Returns:
            Formatted string for display
        """
        if not result.success:
            return f"❌ {self.tool_name} failed: {result.error}"
        
        sections = [f"# {self.tool_name} Results\n"]
        sections.append(f"**Timestamp**: {result.timestamp.isoformat()}")
        sections.append(f"**Status**: ✅ Success\n")
        
        # Core results summary
        if result.core_results:
            sections.append("## Analysis Summary")
            for key, value in result.core_results.items():
                if isinstance(value, list):
                    sections.append(f"- **{key}**: {len(value)} items")
                elif isinstance(value, dict):
                    sections.append(f"- **{key}**: {len(value)} entries")
                else:
                    sections.append(f"- **{key}**: {value}")
            sections.append("")
        
        # AI interpretation
        if result.ai_interpretation:
            sections.append("## AI Analysis")
            sections.append(result.ai_interpretation)
            sections.append("")
        
        # Recommendations
        if result.recommendations:
            sections.append("## Recommendations")
            for i, rec in enumerate(result.recommendations, 1):
                sections.append(f"{i}. {rec}")
        
        return "\n".join(sections)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get tool usage metrics"""
        success_rate = 0
        if self.metrics["total_runs"] > 0:
            success_rate = (self.metrics["successful_runs"] / self.metrics["total_runs"]) * 100
        
        avg_duration = 0
        if self.metrics["total_runs"] > 0:
            avg_duration = self.metrics["total_duration_ms"] / self.metrics["total_runs"]
        
        return {
            "tool_name": self.tool_name,
            "total_runs": self.metrics["total_runs"],
            "success_rate": f"{success_rate:.1f}%",
            "average_duration_ms": f"{avg_duration:.0f}",
            "failed_runs": self.metrics["failed_runs"]
        }
    
    # Context sharing methods
    def get_context_requirements(self) -> Optional['ToolContextRequirements']:
        """
        Get this tool's context requirements.
        
        Subclasses should override _context_requirements to specify what context they need.
        
        Returns:
            ToolContextRequirements or None if not specified
        """
        if self._context_requirements is None:
            # Try to build default requirements
            from ..models.context_models import ToolContextRequirements
            return ToolContextRequirements(tool_name=self.tool_name)
        return self._context_requirements
    
    def set_context_requirements(self, requirements: 'ToolContextRequirements') -> None:
        """
        Set this tool's context requirements.
        
        Args:
            requirements: ToolContextRequirements specification
        """
        self._context_requirements = requirements
    
    def process_with_context(self, 
                            files: List[str],
                            shared_context: List['ContextEntry'],
                            **kwargs) -> Dict[str, Any]:
        """
        Process files with shared context from other tools.
        
        This method can be overridden by subclasses to use context in their analysis.
        
        Args:
            files: Files to analyze
            shared_context: Context entries from other tools
            **kwargs: Tool-specific parameters
            
        Returns:
            Analysis results that may be influenced by context
        """
        # Default implementation just calls core utility
        # Subclasses can override to use context
        return self._core_utility(files, **kwargs)
    
    def extract_context_contributions(self, 
                                     result: ToolResult) -> List['ContextEntry']:
        """
        Extract context entries that this tool wants to share.
        
        Subclasses should override this to extract shareable insights from their results.
        
        Args:
            result: ToolResult from this tool's execution
            
        Returns:
            List of ContextEntry objects to share with other tools
        """
        # Default implementation returns empty list
        # Subclasses should override to provide context
        return []
    
    async def execute(self, 
                     files: List[str],
                     with_ai: bool = True,
                     context: Optional[str] = None,
                     shared_context: Optional[List['ContextEntry']] = None,
                     **kwargs) -> ToolResult:
        """
        Execute the tool with standard workflow
        
        Args:
            files: Files to analyze
            with_ai: Whether to include AI interpretation
            context: Optional context string for AI
            shared_context: Optional context from other tools
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with analysis and recommendations
        """
        import time
        start_time = time.time()
        self.metrics["total_runs"] += 1
        
        # Validate inputs
        is_valid, error_msg = self.validate_inputs(files, **kwargs)
        if not is_valid:
            self.metrics["failed_runs"] += 1
            return ToolResult(
                success=False,
                tool_name=self.tool_name,
                timestamp=datetime.now(),
                core_results={},
                error=error_msg
            )
        
        try:
            # Run core utility (with context if available)
            self.logger.info(f"Running {self.tool_name} on {len(files)} files")
            if shared_context:
                self.logger.info(f"Using {len(shared_context)} context entries from other tools")
                core_results = self.process_with_context(files, shared_context, **kwargs)
            else:
                core_results = self._core_utility(files, **kwargs)
            
            # Get AI interpretation if requested
            ai_interpretation = None
            recommendations = []
            if with_ai:
                try:
                    ai_interpretation = await self._get_ai_interpretation(core_results, context)
                    # Extract recommendations from AI response (simplified - could be enhanced)
                    if "recommend" in ai_interpretation.lower():
                        # Basic extraction - could be improved with better parsing
                        lines = ai_interpretation.split('\n')
                        for line in lines:
                            if any(marker in line for marker in ['•', '-', '*', '1.', '2.', '3.']):
                                recommendations.append(line.strip(' •-*123.'))
                except Exception as e:
                    self.logger.warning(f"AI interpretation failed: {e}")
                    ai_interpretation = "AI interpretation unavailable"
            
            # Record success
            self.metrics["successful_runs"] += 1
            duration_ms = (time.time() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms
            
            return ToolResult(
                success=True,
                tool_name=self.tool_name,
                timestamp=datetime.now(),
                core_results=core_results,
                ai_interpretation=ai_interpretation,
                recommendations=recommendations,
                metadata={"duration_ms": duration_ms, "file_count": len(files)}
            )
            
        except Exception as e:
            self.logger.error(f"{self.tool_name} execution failed: {e}")
            self.metrics["failed_runs"] += 1
            return ToolResult(
                success=False,
                tool_name=self.tool_name,
                timestamp=datetime.now(),
                core_results={},
                error=str(e)
            )

class FileAnalysisTool(BaseTool):
    """
    Base class for tools that analyze files
    Provides common file reading and parsing utilities
    """
    
    def read_file_safe(self, file_path: str, encoding: str = 'utf-8') -> Optional[str]:
        """
        Safely read a file with error handling
        
        Args:
            file_path: Path to file
            encoding: File encoding
            
        Returns:
            File content or None if error
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            self.logger.warning(f"Could not read {file_path}: {e}")
            return None
    
    def get_file_extension(self, file_path: str) -> str:
        """Get file extension from path"""
        import os
        return os.path.splitext(file_path)[1].lower()
    
    def is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file"""
        config_extensions = ['.env', '.ini', '.yaml', '.yml', '.json', '.toml', '.cfg', '.conf']
        return self.get_file_extension(file_path) in config_extensions
    
    def is_api_spec_file(self, file_path: str) -> bool:
        """Check if file is an API specification"""
        api_patterns = ['openapi', 'swagger', 'api.yaml', 'api.json', '.proto']
        file_lower = file_path.lower()
        return any(pattern in file_lower for pattern in api_patterns)
    
    def is_source_code(self, file_path: str) -> bool:
        """Check if file is source code"""
        code_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.h']
        return self.get_file_extension(file_path) in code_extensions