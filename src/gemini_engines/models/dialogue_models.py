"""
Dialogue system data models for the ComprehensiveReview multi-turn conversation system.

These models provide type-safe, validated data structures for managing dialogue state,
tool execution results, and intent parsing - addressing Gemini's architectural recommendations
for standardized schemas and structured data flow.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from enum import Enum


class ErrorType(str, Enum):
    """Classification of tool execution errors for intelligent retry logic"""
    TRANSIENT = "transient"        # Network timeouts, rate limits - retryable
    USER_INPUT = "user_input"      # Invalid file paths, parameters - needs user fix
    INTERNAL = "internal"          # Code bugs, unexpected errors - may be retryable
    PERMANENT = "permanent"        # Missing dependencies, permissions - not retryable


class ToolStatus(str, Enum):
    """Standardized tool execution status"""
    SUCCESS = "success"
    FAILURE = "failure"  
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class IntentAction(str, Enum):
    """Supported user intent actions in dialogue system"""
    RUN_TOOL = "run_tool"
    SYNTHESIZE = "synthesize"
    RETRY_FAILED = "retry_failed"
    SPECIFY_FILES = "specify_files"
    EXPLAIN = "explain"
    HELP = "help"
    END_SESSION = "end_session"
    CONTINUE = "continue"
    CONTINUE_DIALOGUE = "continue_dialogue"  # For technical response continuation
    UNKNOWN = "unknown"


class SessionStatus(str, Enum):
    """Session status states for type safety"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationSeverity(str, Enum):
    """File validation error severity levels"""
    ERROR = "error"           # Critical issue - blocks execution
    WARNING = "warning"       # Non-critical issue - execution can continue
    INFO = "info"            # Informational message


class ValidationIssue(BaseModel):
    """Individual file validation issue"""
    path: str = Field(..., description="File path that has the issue")
    severity: ValidationSeverity = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable error message")
    suggested_action: Optional[str] = Field(None, description="Suggested fix for the issue")


class ValidationResult(BaseModel):
    """
    Structured result from file validation operations.
    
    This provides detailed information about file validation outcomes,
    enabling intelligent error handling and user-friendly messaging.
    """
    valid_files: List[str] = Field(default_factory=list, description="Files that passed validation")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues found")
    total_files_requested: int = Field(0, description="Total number of files requested for validation")
    validation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level issues"""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues"""
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)
    
    @property
    def is_blocking(self) -> bool:
        """Check if validation issues should block execution"""
        return self.has_errors or len(self.valid_files) == 0
    
    @property
    def can_proceed_with_partial(self) -> bool:
        """Check if execution can proceed with partial file set"""
        return len(self.valid_files) > 0 and not self.has_errors
    
    @property
    def success_rate(self) -> float:
        """Calculate percentage of files that passed validation"""
        if self.total_files_requested == 0:
            return 0.0
        return len(self.valid_files) / self.total_files_requested
    
    def get_user_friendly_message(self) -> str:
        """Generate user-friendly validation summary message"""
        if not self.issues:
            return f"✅ All {len(self.valid_files)} files validated successfully."
        
        messages = []
        
        # Success summary
        if self.valid_files:
            messages.append(f"✅ {len(self.valid_files)} files validated successfully")
        
        # Error summary
        errors = [issue for issue in self.issues if issue.severity == ValidationSeverity.ERROR]
        if errors:
            messages.append(f"❌ {len(errors)} critical issues found")
            
        # Warning summary
        warnings = [issue for issue in self.issues if issue.severity == ValidationSeverity.WARNING]
        if warnings:
            messages.append(f"⚠️ {len(warnings)} warnings")
        
        # Detailed error messages
        if errors:
            messages.append("\n**Critical Issues:**")
            for error in errors[:3]:  # Limit to first 3 for readability
                suggestion = f" → {error.suggested_action}" if error.suggested_action else ""
                messages.append(f"  • {error.path}: {error.message}{suggestion}")
            if len(errors) > 3:
                messages.append(f"  ... and {len(errors) - 3} more errors")
        
        # Recommendation
        if self.can_proceed_with_partial:
            messages.append(f"\n**Recommendation**: Proceed with {len(self.valid_files)} valid files, or fix issues and retry.")
        elif self.is_blocking:
            messages.append(f"\n**Action Required**: Fix critical issues before proceeding.")
        
        return "\n".join(messages)


class SessionContext(BaseModel):
    """
    Structured context for dialogue sessions, preserving conversation state
    and technical context across multiple turns.
    """
    # Conversation history (limited to recent turns for efficiency)
    recent_turns: List[str] = Field(default_factory=list, description="Recent dialogue turns for context")
    
    # File and analysis context
    mentioned_files: List[str] = Field(default_factory=list, description="Files mentioned in conversation")
    current_focus: str = Field("all", description="Current analysis focus area")
    last_validation_result: Optional["ValidationResult"] = Field(None, description="Most recent file validation result")
    
    # Technical context
    detected_topics: List[str] = Field(default_factory=list, description="Technical topics detected in conversation")
    last_intent_action: Optional[IntentAction] = Field(None, description="Most recent intent action")
    last_intent_confidence: float = Field(0.0, description="Confidence of last intent detection")
    
    # Tool execution context
    recent_tool_results: Dict[str, str] = Field(default_factory=dict, description="Brief summaries of recent tool results")
    failed_tools_context: Dict[str, str] = Field(default_factory=dict, description="Context about failed tools")
    
    # Session metadata
    total_turns: int = Field(0, description="Total turns in this session")
    session_start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_technical_topics(self, topics: List[str]) -> None:
        """Add detected technical topics, avoiding duplicates"""
        for topic in topics:
            if topic not in self.detected_topics:
                self.detected_topics.append(topic)
        self.last_updated = datetime.now(timezone.utc)
    
    def add_mentioned_files(self, files: List[str]) -> None:
        """Add mentioned files, avoiding duplicates"""
        for file in files:
            if file not in self.mentioned_files:
                self.mentioned_files.append(file)
        self.last_updated = datetime.now(timezone.utc)
    
    def update_tool_result_summary(self, tool_name: str, summary: str) -> None:
        """Update recent tool results with brief summaries"""
        self.recent_tool_results[tool_name] = summary[:200]  # Limit summary length
        self.last_updated = datetime.now(timezone.utc)
    
    def add_recent_turn(self, turn_summary: str, max_turns: int = 5) -> None:
        """Add a recent turn summary, maintaining a sliding window"""
        self.recent_turns.append(turn_summary[:150])  # Limit turn summary length
        if len(self.recent_turns) > max_turns:
            self.recent_turns = self.recent_turns[-max_turns:]  # Keep only recent turns
        self.total_turns += 1
        self.last_updated = datetime.now(timezone.utc)
    
    def get_context_summary(self) -> str:
        """Generate a concise context summary for AI prompts"""
        summary_parts = []
        
        if self.current_focus != "all":
            summary_parts.append(f"Focus: {self.current_focus}")
        
        if self.mentioned_files:
            files_preview = ", ".join(self.mentioned_files[:3])
            if len(self.mentioned_files) > 3:
                files_preview += f" (and {len(self.mentioned_files) - 3} more)"
            summary_parts.append(f"Files: {files_preview}")
        
        if self.detected_topics:
            topics_preview = ", ".join(self.detected_topics[:5])
            summary_parts.append(f"Topics: {topics_preview}")
        
        if self.recent_tool_results:
            tools_preview = ", ".join(list(self.recent_tool_results.keys())[:3])
            summary_parts.append(f"Recent tools: {tools_preview}")
        
        return " | ".join(summary_parts) if summary_parts else "New session"


class ToolOutput(BaseModel):
    """
    Standardized schema for all tool execution results.
    
    This replaces the varied tool output formats with a consistent structure
    that enables reliable synthesis and error handling.
    """
    tool_name: str = Field(..., description="Name of the executed tool")
    status: ToolStatus = Field(..., description="Execution status")
    
    # Core results
    summary: str = Field("", description="Brief summary of findings")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Structured findings/data")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    
    # Execution metadata
    execution_time_seconds: float = Field(0.0, description="Tool execution time")
    files_analyzed: int = Field(0, description="Number of files processed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error details if status is failure")
    error_type: Optional[ErrorType] = Field(None, description="Classification of error for retry logic")
    
    # Raw output (for backward compatibility)
    raw_output: Optional[Dict[str, Any]] = Field(None, description="Original tool output")
    
    @property
    def is_success(self) -> bool:
        """Check if tool executed successfully"""
        return self.status == ToolStatus.SUCCESS
    
    @property
    def is_failure(self) -> bool:
        """Check if tool failed"""
        return self.status in (ToolStatus.FAILURE, ToolStatus.TIMEOUT, ToolStatus.CANCELLED)
    
    @property
    def is_retryable(self) -> bool:
        """Check if a failed tool can be retried based on error type"""
        if not self.is_failure:
            return False
        return self.error_type in (ErrorType.TRANSIENT, ErrorType.INTERNAL)


class IntentResult(BaseModel):
    """
    Structured result from intent parsing with confidence and fallback actions.
    """
    action: IntentAction = Field(..., description="Detected user intent")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in intent detection")
    
    # Extracted parameters
    tool_name: Optional[str] = Field(None, description="Specific tool requested")
    files: List[str] = Field(default_factory=list, description="Files specified by user")
    directories: List[str] = Field(default_factory=list, description="Directories specified by user")
    
    # Parser metadata
    parsing_method: str = Field("unknown", description="Method used for parsing (regex/llm/hybrid)")
    raw_user_input: str = Field("", description="Original user input")
    extracted_entities: Dict[str, Any] = Field(default_factory=dict, description="Additional extracted entities")
    
    # Fallback guidance
    suggested_actions: List[str] = Field(default_factory=list, description="Suggested actions if confidence is low")
    clarification_needed: bool = Field(False, description="Whether user input needs clarification")
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if intent was detected with high confidence"""
        return self.confidence >= 0.8
    
    @property
    def needs_clarification(self) -> bool:
        """Check if user input requires clarification"""
        return self.confidence < 0.5 or self.clarification_needed


class DialogueTurn(BaseModel):
    """
    Single turn in a dialogue session with user input and system response.
    """
    round_number: int = Field(..., ge=1, description="Turn number in dialogue")
    user_input: str = Field(..., description="User's input for this turn")
    ai_response: str = Field(..., description="System's response")
    
    # Intent and execution
    parsed_intent: Optional[IntentResult] = Field(None, description="Parsed user intent")
    tools_executed: List[str] = Field(default_factory=list, description="Tools executed in this turn")
    execution_results: Dict[str, ToolOutput] = Field(default_factory=dict, description="Results from tool execution")
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_seconds: float = Field(0.0, description="Total turn execution time")
    
    @property
    def successful_tools(self) -> List[str]:
        """Get list of tools that executed successfully"""
        return [
            tool_name for tool_name, result in self.execution_results.items()
            if result.is_success
        ]
    
    @property
    def failed_tools(self) -> List[str]:
        """Get list of tools that failed"""
        return [
            tool_name for tool_name, result in self.execution_results.items()
            if result.is_failure
        ]


class DialogueState(BaseModel):
    """
    Complete state of a dialogue session - the central data structure
    passed between all services in the orchestration system.
    
    This addresses Gemini's recommendation for a single, explicit,
    type-safe representation of conversation state.
    """
    # Session identification
    session_id: str = Field(..., description="Unique session identifier")
    task_id: Optional[str] = Field(None, description="Optional task identifier")
    
    # Session metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_round: int = Field(0, ge=0, description="Current dialogue round")
    max_rounds: int = Field(15, description="Maximum allowed rounds")
    
    # Review configuration
    focus: str = Field("all", description="Review focus area")
    file_paths: List[str] = Field(default_factory=list, description="Files being analyzed")
    context: Optional[str] = Field(None, description="Additional context")
    
    # Dialogue history
    turns: List[DialogueTurn] = Field(default_factory=list, description="Complete dialogue history")
    
    # Tool execution state
    executed_tools: Dict[str, ToolOutput] = Field(default_factory=dict, description="All tool results in session")
    failed_tools: Dict[str, ErrorType] = Field(default_factory=dict, description="Failed tools with their error types for intelligent retry")
    
    # Session state
    status: SessionStatus = Field(SessionStatus.ACTIVE, description="Session status with type safety")
    next_suggested_action: Optional[str] = Field(None, description="Suggested next action for user")
    synthesis_available: bool = Field(False, description="Whether synthesis can be generated")
    
    class Config:
        """Pydantic configuration"""
        validate_assignment = True
        
    def add_turn(self, turn: DialogueTurn) -> None:
        """Add a new dialogue turn and update session state"""
        self.turns.append(turn)
        self.current_round = len(self.turns)
        self.updated_at = datetime.now(timezone.utc)
        
        # Update executed tools and failed tools
        for tool_name, result in turn.execution_results.items():
            self.executed_tools[tool_name] = result
            if result.is_failure and result.is_retryable:
                # Store with error type for intelligent retry decisions
                self.failed_tools[tool_name] = result.error_type
            elif result.is_success and tool_name in self.failed_tools:
                # Remove from failed dict if now successful
                del self.failed_tools[tool_name]
        
        # Update synthesis availability
        successful_count = sum(1 for result in self.executed_tools.values() if result.is_success)
        self.synthesis_available = successful_count >= 1
    
    def get_recent_context(self, max_turns: int = 3) -> List[DialogueTurn]:
        """Get recent dialogue turns for context (not full history)"""
        return self.turns[-max_turns:] if self.turns else []
    
    def get_successful_tools(self) -> Dict[str, ToolOutput]:
        """Get all successfully executed tools"""
        return {
            name: result for name, result in self.executed_tools.items()
            if result.is_success
        }
    
    @property
    def can_continue(self) -> bool:
        """Check if dialogue can continue"""
        return self.current_round < self.max_rounds and self.status == SessionStatus.ACTIVE
    
    @property
    def summary(self) -> str:
        """Get brief session summary"""
        successful_tools = len(self.get_successful_tools())
        failed_tools = len(self.failed_tools)
        return (
            f"Session {self.session_id}: Round {self.current_round}/{self.max_rounds}, "
            f"Tools: {successful_tools} successful, {failed_tools} failed, "
            f"Focus: {self.focus}, Status: {self.status}"
        )


class DialogueCommand(BaseModel):
    """
    Command structure for common dialogue operations.
    Used internally by services for consistent command handling.
    """
    action: IntentAction = Field(..., description="Command action")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    session_id: str = Field(..., description="Target session")
    requested_by: str = Field("user", description="Who requested the command")
    
    @classmethod
    def run_tool(cls, session_id: str, tool_name: str, files: List[str] = None) -> "DialogueCommand":
        """Create a run_tool command"""
        return cls(
            action=IntentAction.RUN_TOOL,
            session_id=session_id,
            parameters={
                "tool_name": tool_name,
                "files": files or []
            }
        )
    
    @classmethod
    def synthesize(cls, session_id: str) -> "DialogueCommand":
        """Create a synthesize command"""
        return cls(
            action=IntentAction.SYNTHESIZE,
            session_id=session_id
        )
    
    @classmethod
    def retry_failed(cls, session_id: str, tool_names: List[str] = None) -> "DialogueCommand":
        """Create a retry_failed command"""
        return cls(
            action=IntentAction.RETRY_FAILED,
            session_id=session_id,
            parameters={"tool_names": tool_names}
        )


# Export main classes for easy importing
__all__ = [
    "ErrorType",
    "ToolStatus", 
    "IntentAction",
    "SessionStatus",
    "ValidationSeverity",
    "ValidationIssue", 
    "ValidationResult",
    "SessionContext",
    "ToolOutput",
    "IntentResult",
    "DialogueTurn",
    "DialogueState",
    "DialogueCommand"
]