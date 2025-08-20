"""
Core interfaces for the refactored comprehensive review system.
These interfaces define the contracts for decoupled, testable components.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Any, Optional
from datetime import datetime


class ToolStatus(Enum):
    """Status of a tool execution"""
    SUCCESS = auto()
    FAILURE = auto()
    SKIPPED = auto()


@dataclass
class AnalysisResult:
    """
    Standardized result structure for all analysis tools.
    Provides uniform interface for tool outputs with status tracking.
    """
    tool_name: str
    status: ToolStatus
    output: Optional[Any] = None  # The actual result data on success
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def is_success(self) -> bool:
        """Check if the analysis was successful"""
        return self.status == ToolStatus.SUCCESS
    
    @property
    def is_failure(self) -> bool:
        """Check if the analysis failed"""
        return self.status == ToolStatus.FAILURE
    
    @property
    def is_skipped(self) -> bool:
        """Check if the analysis was skipped"""
        return self.status == ToolStatus.SKIPPED


class IAnalysisTool(ABC):
    """
    Abstract interface for all analysis tools.
    Ensures uniform behavior and testability across different tool types.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool"""
        pass
    
    @abstractmethod
    async def execute(self, 
                     file_paths: List[str], 
                     context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute the tool's analysis asynchronously.
        
        Args:
            file_paths: List of file paths to analyze
            context: Context dictionary containing:
                - review_focus: Focus area (security, performance, etc.)
                - detail_level: Level of detail required
                - session_id: Session identifier for state tracking
                - user_intent: Parsed intent from current dialogue turn
                - dry_run: Whether this is a dry run (mock execution)
        
        Returns:
            AnalysisResult with status, output, and metadata
        """
        pass


class ISessionManager(ABC):
    """Interface for session state management and persistence"""
    
    @abstractmethod
    async def create_session(self, 
                           task_id: str, 
                           review_type: str, 
                           focus: str, 
                           context: str = "") -> Dict[str, Any]:
        """Create a new review session"""
        pass
    
    @abstractmethod
    async def get_session(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session by task ID"""
        pass
    
    @abstractmethod
    async def save_tool_results(self, 
                               task_id: str, 
                               round_number: int,
                               results: Dict[str, AnalysisResult]) -> None:
        """Save tool execution results for a round"""
        pass
    
    @abstractmethod
    async def get_tool_results(self, task_id: str) -> Dict[int, Dict[str, AnalysisResult]]:
        """Get all tool results for a session, organized by round"""
        pass
    
    @abstractmethod
    async def save_failed_tools(self, task_id: str, failed_tools: List[str]) -> None:
        """Save list of tools that failed in the current round"""
        pass
    
    @abstractmethod
    async def get_failed_tools(self, task_id: str) -> List[str]:
        """Get list of tools that failed and can be retried"""
        pass
    
    @abstractmethod
    async def add_dialogue_turn(self, 
                               task_id: str, 
                               round_number: int,
                               user_input: str, 
                               ai_response: str,
                               metadata: Dict[str, Any] = None) -> None:
        """Add a dialogue turn to the session"""
        pass


class IToolExecutor(ABC):
    """Interface for executing analysis tools with parallelism and error handling"""
    
    @abstractmethod
    async def execute_single_tool(self, 
                                 tool: IAnalysisTool, 
                                 file_paths: List[str],
                                 context: Dict[str, Any]) -> AnalysisResult:
        """Execute a single tool"""
        pass
    
    @abstractmethod
    async def execute_tool_batch(self, 
                                tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Execute multiple tools in parallel with error handling"""
        pass
    
    @abstractmethod
    async def retry_failed_tools(self, 
                                failed_tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Retry execution of previously failed tools"""
        pass


class IIntentParser(ABC):
    """Interface for parsing user intent from natural language input"""
    
    @abstractmethod
    async def parse_user_intent(self, user_response: str) -> 'IntentResult':
        """
        Parse user's natural language response into structured intent.
        
        Returns:
            IntentResult with structured intent data, confidence, and metadata
        """
        pass


class IToolSelector(ABC):
    """Interface for selecting appropriate tools based on context"""
    
    @abstractmethod
    def determine_priority_tools(self, 
                                file_paths: List[str], 
                                focus: str = "all") -> List[str]:
        """
        Select priority tools based on file types and focus area.
        
        Args:
            file_paths: Files to be analyzed
            focus: Review focus area
            
        Returns:
            List of tool names in priority order
        """
        pass
    
    @abstractmethod
    def get_tools_for_focus(self, focus: str) -> List[str]:
        """Get all tools relevant for a specific focus area"""
        pass


class IResultSynthesizer(ABC):
    """Interface for synthesizing results from multiple tools"""
    
    @abstractmethod
    async def synthesize_report(self, 
                               tool_results: Dict[str, AnalysisResult],
                               context: Optional[str] = None,
                               focus: str = "all") -> str:
        """
        Generate comprehensive synthesis report from tool results.
        
        Args:
            tool_results: Results from all executed tools
            context: Additional context for synthesis
            focus: Focus area for the review
            
        Returns:
            Formatted comprehensive report as Markdown string
        """
        pass
    
    @abstractmethod
    def select_synthesis_model(self, 
                              tool_results: Dict[str, AnalysisResult],
                              focus: str) -> str:
        """
        Select appropriate model for synthesis based on complexity.
        
        Args:
            tool_results: Results to be synthesized
            focus: Review focus area
            
        Returns:
            Model name (pro, flash, flash-lite)
        """
        pass


class IReviewOrchestrator(ABC):
    """Interface for the main review orchestration logic"""
    
    @abstractmethod
    async def start_or_continue_review(self,
                                      task_id: Optional[str] = None,
                                      files: Optional[List[str]] = None,
                                      focus: str = "all",
                                      user_response: Optional[str] = None,
                                      context: Optional[str] = None,
                                      dry_run: bool = False) -> str:
        """
        Main entry point for starting or continuing a comprehensive review.
        
        Args:
            task_id: Session ID (None for new session)
            files: Files to analyze
            focus: Review focus area
            user_response: User's response in dialogue
            context: Additional context
            dry_run: Whether to run in dry-run mode
            
        Returns:
            Formatted response for the user
        """
        pass


# Configuration dataclasses for dependency injection

@dataclass
class ToolExecutorConfig:
    """Configuration for ToolExecutor"""
    max_concurrency: int = 4
    retry_attempts: int = 2
    timeout_seconds: int = 300


@dataclass
class IntentParserConfig:
    """Configuration for IntentParser"""
    model_name: str = "flash"
    timeout_seconds: int = 30
    confidence_threshold: float = 0.7


@dataclass
class ResultSynthesizerConfig:
    """Configuration for ResultSynthesizer"""
    default_model: str = "flash"
    pro_model_threshold_chars: int = 8000
    pro_model_focus_areas: List[str] = None
    timeout_seconds: int = 120
    
    def __post_init__(self):
        if self.pro_model_focus_areas is None:
            self.pro_model_focus_areas = ["architecture", "security"]


@dataclass
class ReviewOrchestratorConfig:
    """Configuration for ReviewOrchestrator"""
    max_dialogue_rounds: int = 15
    default_focus: str = "all"
    enable_dry_run: bool = True
    session_timeout_hours: int = 24