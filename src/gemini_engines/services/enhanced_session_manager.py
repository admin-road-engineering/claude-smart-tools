"""
Enhanced SessionManager implementation using DialogueState models.

This enhanced version implements Gemini's architectural recommendations:
- Uses DialogueState as the central data structure
- Provides type-safe operations with Pydantic validation
- Implements proper error classification for intelligent retry logic
- Supports structured dialogue turn management
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..models.dialogue_models import (
    DialogueState, DialogueTurn, ToolOutput, IntentResult,
    ErrorType, ToolStatus, IntentAction, SessionStatus
)
from ..tools.interfaces import ISessionManager, AnalysisResult
from ..persistence.sqlite_session_store import SqliteSessionStore

logger = logging.getLogger(__name__)


class EnhancedSessionManager(ISessionManager):
    """
    Enhanced session management using DialogueState models.
    
    Provides type-safe, validated session operations with comprehensive
    state management and error handling following Gemini's recommendations.
    """
    
    def __init__(self, session_store: SqliteSessionStore = None):
        """
        Initialize EnhancedSessionManager with storage backend.
        
        Args:
            session_store: SQLite storage instance (will create if None)
        """
        self.session_store = session_store or SqliteSessionStore()
        self._active_sessions: Dict[str, DialogueState] = {}
        self._session_lock = asyncio.Lock()
    
    async def create_session(self, 
                           task_id: str, 
                           review_type: str = "comprehensive_review", 
                           focus: str = "all", 
                           context: str = "",
                           file_paths: List[str] = None,
                           max_rounds: int = 15) -> Dict[str, Any]:
        """
        Create a new dialogue session with structured state.
        
        Args:
            task_id: Unique session identifier
            review_type: Type of review session
            focus: Focus area for the review
            context: Additional context information
            file_paths: Files to be analyzed
            max_rounds: Maximum dialogue rounds allowed
            
        Returns:
            Session creation result dictionary
        """
        async with self._session_lock:
            try:
                # Create DialogueState instance
                dialogue_state = DialogueState(
                    session_id=task_id,
                    task_id=task_id,
                    focus=focus,
                    file_paths=file_paths or [],
                    context=context,
                    max_rounds=max_rounds,
                    status=SessionStatus.ACTIVE
                )
                
                # Persist to storage first
                self.session_store.create_session(
                    task_id=task_id,
                    output_type=review_type,
                    focus=focus,
                    context=context
                )
                
                # Save initial state
                await self._persist_dialogue_state(dialogue_state)
                
                # Store in active sessions cache only after successful persistence
                self._active_sessions[task_id] = dialogue_state
                
                logger.info(f"Created enhanced session: {task_id} with {len(file_paths or [])} files")
                
                return {
                    'session_id': task_id,
                    'status': 'created',
                    'dialogue_state': dialogue_state.model_dump(mode="json"),
                    'message': f'Session created successfully with focus: {focus}'
                }
                
            except Exception as e:
                logger.error(f"Failed to create enhanced session {task_id}: {e}")
                raise
    
    async def get_session(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session as legacy dictionary format for backward compatibility.
        
        Args:
            task_id: Session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        dialogue_state = await self.get_dialogue_state(task_id)
        if not dialogue_state:
            return None
        
        # Convert to legacy format for compatibility
        return {
            'task_id': task_id,
            'review_type': 'comprehensive_review',
            'focus': dialogue_state.focus,
            'context': dialogue_state.context,
            'file_paths': dialogue_state.file_paths,
            'total_rounds': dialogue_state.current_round,
            'created_at': dialogue_state.created_at,
            'updated_at': dialogue_state.updated_at,
            'status': dialogue_state.status,
            'failed_tools': dialogue_state.failed_tools,
            'completed_tools': list(dialogue_state.get_successful_tools().keys()),
            'synthesis_available': dialogue_state.synthesis_available
        }
    
    async def get_dialogue_state(self, task_id: str) -> Optional[DialogueState]:
        """
        Get complete DialogueState for a session.
        
        Args:
            task_id: Session identifier
            
        Returns:
            DialogueState instance or None if not found
        """
        # Check active sessions cache first
        if task_id in self._active_sessions:
            return self._active_sessions[task_id]
        
        try:
            # Load from storage
            dialogue_state = await self._load_dialogue_state(task_id)
            if dialogue_state:
                # Cache for future access
                async with self._session_lock:
                    self._active_sessions[task_id] = dialogue_state
                return dialogue_state
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to get dialogue state for {task_id}: {e}")
            return None
    
    async def save_dialogue_state(self, dialogue_state: DialogueState) -> None:
        """
        Save complete DialogueState to persistent storage.
        
        Args:
            dialogue_state: DialogueState to save
        """
        async with self._session_lock:
            try:
                # Update in cache
                self._active_sessions[dialogue_state.session_id] = dialogue_state
                
                # Persist to storage
                await self._persist_dialogue_state(dialogue_state)
                
                logger.debug(f"Saved dialogue state for session {dialogue_state.session_id}")
                
            except Exception as e:
                logger.error(f"Failed to save dialogue state for {dialogue_state.session_id}: {e}")
                raise
    
    async def add_dialogue_turn(self, 
                               task_id: str, 
                               round_number: int,
                               user_input: str, 
                               ai_response: str,
                               parsed_intent: Optional[IntentResult] = None,
                               tools_executed: List[str] = None,
                               execution_results: Dict[str, ToolOutput] = None,
                               metadata: Dict[str, Any] = None) -> None:
        """
        Add a structured dialogue turn to the session.
        
        Args:
            task_id: Session identifier
            round_number: Current dialogue round
            user_input: User's input for this turn
            ai_response: AI's response for this turn
            parsed_intent: Parsed user intent
            tools_executed: List of tools executed in this turn
            execution_results: Results from tool execution
            metadata: Additional metadata for this turn
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                raise ValueError(f"Session {task_id} not found")
            
            # Create DialogueTurn
            dialogue_turn = DialogueTurn(
                round_number=round_number,
                user_input=user_input,
                ai_response=ai_response,
                parsed_intent=parsed_intent,
                tools_executed=tools_executed or [],
                execution_results=execution_results or {},
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add turn to dialogue state
            dialogue_state.add_turn(dialogue_turn)
            
            # Save updated state
            await self.save_dialogue_state(dialogue_state)
            
            # Also save to legacy storage for compatibility
            self.session_store.add_dialogue_turn(
                task_id=task_id,
                round_number=round_number,
                model_used="enhanced_orchestrator",
                attempts=1,
                user_input=user_input[:1000],  # Truncate for storage
                ai_response=ai_response[:1000],  # Truncate for storage
                metadata={
                    'intent_action': parsed_intent.action if parsed_intent else None,
                    'tools_executed': tools_executed or [],
                    'execution_success_count': len([r for r in (execution_results or {}).values() if r.is_success]),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Added dialogue turn {round_number} to session {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to add dialogue turn to session {task_id}: {e}")
            raise
    
    async def save_tool_results(self, 
                               task_id: str, 
                               round_number: int,
                               results: Dict[str, AnalysisResult]) -> None:
        """
        Save tool execution results (legacy format conversion).
        
        Args:
            task_id: Session identifier
            round_number: Current dialogue round
            results: Dictionary of tool results by tool name
        """
        try:
            # Convert AnalysisResult to ToolOutput
            tool_outputs = {}
            for tool_name, analysis_result in results.items():
                # Map AnalysisResult to ToolOutput
                tool_output = self._convert_analysis_result_to_tool_output(analysis_result)
                tool_outputs[tool_name] = tool_output
            
            # Get dialogue state and update with results
            dialogue_state = await self.get_dialogue_state(task_id)
            if dialogue_state and dialogue_state.turns:
                # Update the latest turn with execution results
                latest_turn = dialogue_state.turns[-1]
                if latest_turn.round_number == round_number:
                    latest_turn.execution_results.update(tool_outputs)
                    # Update dialogue state's executed_tools
                    for tool_name, tool_output in tool_outputs.items():
                        dialogue_state.executed_tools[tool_name] = tool_output
                        if tool_output.is_failure and tool_output.is_retryable:
                            # Store as dictionary with ErrorType
                            dialogue_state.failed_tools[tool_name] = tool_output.error_type or ErrorType.INTERNAL
                    
                    await self.save_dialogue_state(dialogue_state)
            
            # Also save to legacy storage for compatibility
            await self._save_legacy_tool_results(task_id, round_number, results)
            
            logger.info(f"Saved tool results for {len(results)} tools in session {task_id}, round {round_number}")
            
        except Exception as e:
            logger.error(f"Failed to save tool results for session {task_id}: {e}")
            raise
    
    async def get_tool_results(self, task_id: str) -> Dict[int, Dict[str, AnalysisResult]]:
        """
        Get all tool results for a session, organized by dialogue round.
        
        Args:
            task_id: Session identifier
            
        Returns:
            Dictionary mapping round number to tool results
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                return {}
            
            results_by_round = {}
            
            # Extract results from dialogue turns
            for turn in dialogue_state.turns:
                if turn.execution_results:
                    analysis_results = {}
                    for tool_name, tool_output in turn.execution_results.items():
                        # Convert ToolOutput back to AnalysisResult for compatibility
                        analysis_result = self._convert_tool_output_to_analysis_result(tool_output)
                        analysis_results[tool_name] = analysis_result
                    
                    results_by_round[turn.round_number] = analysis_results
            
            return results_by_round
            
        except Exception as e:
            logger.error(f"Failed to get tool results for session {task_id}: {e}")
            return {}
    
    async def save_failed_tools(self, task_id: str, failed_tools: List[str]) -> None:
        """
        Save list of tools that failed and can be retried.
        
        Args:
            task_id: Session identifier
            failed_tools: List of tool names that failed
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                raise ValueError(f"Session {task_id} not found")
            
            # Add new failed tools to the dictionary with error types
            for tool_name in failed_tools:
                if tool_name not in dialogue_state.failed_tools:
                    # Default to INTERNAL error type if not specified
                    dialogue_state.failed_tools[tool_name] = ErrorType.INTERNAL
            
            # Update timestamp
            dialogue_state.updated_at = datetime.now(timezone.utc)
            
            await self.save_dialogue_state(dialogue_state)
            
            logger.info(f"Saved failed tools for session {task_id}: {failed_tools}")
            
        except Exception as e:
            logger.error(f"Failed to save failed tools for session {task_id}: {e}")
            raise
    
    async def get_failed_tools(self, task_id: str) -> List[str]:
        """
        Get list of tools that failed and can be retried.
        
        Args:
            task_id: Session identifier
            
        Returns:
            List of failed tool names
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                return []
            
            # Return list of tool names (keys from the dictionary)
            return list(dialogue_state.failed_tools.keys())
            
        except Exception as e:
            logger.error(f"Failed to get failed tools for session {task_id}: {e}")
            return []
    
    async def clear_failed_tools(self, task_id: str, cleared_tools: List[str] = None) -> None:
        """
        Clear failed tools (after successful retry or user choice to skip).
        
        Args:
            task_id: Session identifier
            cleared_tools: Specific tools to clear (None = clear all)
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                raise ValueError(f"Session {task_id} not found")
            
            if cleared_tools:
                # Remove specific tools from dictionary
                for tool in cleared_tools:
                    dialogue_state.failed_tools.pop(tool, None)
            else:
                # Clear all failed tools
                dialogue_state.failed_tools.clear()
            
            # Update timestamp
            dialogue_state.updated_at = datetime.now(timezone.utc)
            
            await self.save_dialogue_state(dialogue_state)
            
            logger.info(f"Cleared failed tools for session {task_id}: {cleared_tools or 'all'}")
            
        except Exception as e:
            logger.error(f"Failed to clear failed tools for session {task_id}: {e}")
            raise
    
    async def is_session_recoverable(self, task_id: str) -> bool:
        """
        Check if a session can be recovered after interruption.
        
        Args:
            task_id: Session identifier
            
        Returns:
            True if session can be continued
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                return False
            
            return dialogue_state.status == SessionStatus.ACTIVE and dialogue_state.can_continue
            
        except Exception as e:
            logger.error(f"Failed to check session recoverability {task_id}: {e}")
            return False
    
    async def get_dialogue_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get complete dialogue history for a session.
        
        Args:
            task_id: Session identifier
            
        Returns:
            List of dialogue turns with metadata
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                return []
            
            dialogue_history = []
            for turn in dialogue_state.turns:
                dialogue_history.append({
                    'round_number': turn.round_number,
                    'user_input': turn.user_input,
                    'ai_response': turn.ai_response,
                    'timestamp': turn.timestamp,
                    'parsed_intent': turn.parsed_intent.model_dump(mode="json") if turn.parsed_intent else None,
                    'tools_executed': turn.tools_executed,
                    'successful_tools': turn.successful_tools,
                    'failed_tools': turn.failed_tools,
                    'execution_time_seconds': turn.execution_time_seconds
                })
            
            return dialogue_history
            
        except Exception as e:
            logger.error(f"Failed to get dialogue history for session {task_id}: {e}")
            return []
    
    async def update_session_status(self, task_id: str, status: str) -> None:
        """
        Update session status (active, completed, failed).
        
        Args:
            task_id: Session identifier
            status: New session status
        """
        try:
            dialogue_state = await self.get_dialogue_state(task_id)
            if not dialogue_state:
                raise ValueError(f"Session {task_id} not found")
            
            # Convert string status to enum if needed
            if isinstance(status, str):
                try:
                    dialogue_state.status = SessionStatus(status)
                except ValueError:
                    logger.warning(f"Invalid status string '{status}' encountered. Defaulting to ACTIVE.")
                    dialogue_state.status = SessionStatus.ACTIVE
            else:
                dialogue_state.status = status
            dialogue_state.updated_at = datetime.now(timezone.utc)
            
            await self.save_dialogue_state(dialogue_state)
            
            logger.info(f"Updated session {task_id} status to: {status}")
            
        except Exception as e:
            logger.error(f"Failed to update session status for {task_id}: {e}")
            raise
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions in cache"""
        return len(self._active_sessions)
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions from cache.
        
        Args:
            max_age_hours: Maximum age in hours for keeping sessions in cache
            
        Returns:
            Number of sessions cleaned up
        """
        async with self._session_lock:
            current_time = datetime.now(timezone.utc)
            sessions_to_remove = []
            
            for session_id, dialogue_state in self._active_sessions.items():
                age_hours = (current_time - dialogue_state.updated_at).total_seconds() / 3600
                if age_hours > max_age_hours or dialogue_state.status != SessionStatus.ACTIVE:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self._active_sessions[session_id]
            
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions from cache")
            
            return len(sessions_to_remove)
    
    # Private helper methods
    
    async def _persist_dialogue_state(self, dialogue_state: DialogueState) -> None:
        """Persist DialogueState to storage"""
        # Save as workflow context
        self.session_store.save_workflow_context(
            session_id=dialogue_state.session_id,
            tool_name="enhanced_dialogue_state",
            step_number=0,  # Use step 0 for dialogue state
            context_data=dialogue_state.model_dump(mode="json")
        )
    
    async def _load_dialogue_state(self, task_id: str) -> Optional[DialogueState]:
        """Load DialogueState from storage"""
        try:
            contexts = self.session_store.get_workflow_context(
                session_id=task_id, 
                tool_name="enhanced_dialogue_state"
            )
            
            if contexts:
                state_data = contexts[0].get('context_data', {})
                return DialogueState(**state_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load dialogue state for {task_id}: {e}")
            return None
    
    def _convert_analysis_result_to_tool_output(self, analysis_result: AnalysisResult) -> ToolOutput:
        """Convert AnalysisResult to ToolOutput"""
        from ..tools.interfaces import ToolStatus as LegacyToolStatus
        
        # Determine error type for failed results
        error_type = None
        if analysis_result.status == LegacyToolStatus.FAILURE:
            error_msg = analysis_result.error_message or ""
            if any(word in error_msg.lower() for word in ["timeout", "rate limit", "connection"]):
                error_type = ErrorType.TRANSIENT
            elif any(word in error_msg.lower() for word in ["file not found", "invalid path", "permission"]):
                error_type = ErrorType.USER_INPUT
            else:
                error_type = ErrorType.INTERNAL
        
        # Extract summary from output
        summary = ""
        artifacts = []
        recommendations = []
        
        if isinstance(analysis_result.output, dict):
            summary = str(analysis_result.output.get('summary', ''))[:200]
            artifacts = analysis_result.output.get('artifacts', [])
            recommendations = analysis_result.output.get('recommendations', [])
            if not summary and 'analysis' in analysis_result.output:
                summary = str(analysis_result.output['analysis'])[:200]
        elif isinstance(analysis_result.output, str):
            summary = analysis_result.output[:200]
        
        return ToolOutput(
            tool_name=analysis_result.tool_name,
            status=ToolStatus(analysis_result.status.name.lower()),
            summary=summary,
            artifacts=artifacts if isinstance(artifacts, list) else [],
            recommendations=recommendations if isinstance(recommendations, list) else [],
            execution_time_seconds=analysis_result.execution_time_seconds,
            files_analyzed=0,  # Could be extracted from analysis_result if available
            timestamp=analysis_result.timestamp or datetime.now(timezone.utc),
            error_message=analysis_result.error_message,
            error_type=error_type,
            raw_output=analysis_result.output if isinstance(analysis_result.output, dict) else None
        )
    
    def _convert_tool_output_to_analysis_result(self, tool_output: ToolOutput) -> AnalysisResult:
        """Convert ToolOutput back to AnalysisResult for compatibility"""
        from ..tools.interfaces import ToolStatus as LegacyToolStatus
        
        # Map ToolStatus to legacy ToolStatus
        status_mapping = {
            ToolStatus.SUCCESS: LegacyToolStatus.SUCCESS,
            ToolStatus.FAILURE: LegacyToolStatus.FAILURE,
            ToolStatus.TIMEOUT: LegacyToolStatus.FAILURE,  # Map timeout to failure
            ToolStatus.CANCELLED: LegacyToolStatus.FAILURE   # Map cancelled to failure
        }
        
        # Reconstruct output
        output = tool_output.raw_output or {
            'summary': tool_output.summary,
            'artifacts': tool_output.artifacts,
            'recommendations': tool_output.recommendations
        }
        
        return AnalysisResult(
            tool_name=tool_output.tool_name,
            status=status_mapping.get(tool_output.status, LegacyToolStatus.FAILURE),
            output=output,
            error_message=tool_output.error_message,
            execution_time_seconds=tool_output.execution_time_seconds,
            timestamp=tool_output.timestamp
        )
    
    async def _save_legacy_tool_results(self, 
                                       task_id: str, 
                                       round_number: int,
                                       results: Dict[str, AnalysisResult]) -> None:
        """Save tool results in legacy format for compatibility"""
        # Convert to legacy format
        serializable_results = {}
        failed_tools = []
        completed_tools = []
        
        for tool_name, result in results.items():
            serializable_results[tool_name] = {
                'tool_name': result.tool_name,
                'status': result.status.name,
                'output': result.output,
                'error_message': result.error_message,
                'execution_time_seconds': result.execution_time_seconds,
                'timestamp': result.timestamp.isoformat() if result.timestamp else None
            }
            
            # Track tool status
            if result.status == ToolStatus.FAILURE:
                failed_tools.append(tool_name)
            elif result.status == ToolStatus.SUCCESS:
                completed_tools.append(tool_name)
        
        # Save to workflow context
        self.session_store.save_workflow_context(
            session_id=task_id,
            tool_name="legacy_tool_results",
            step_number=round_number,
            context_data={
                'tool_results': serializable_results,
                'round_summary': {
                    'total_tools': len(results),
                    'successful': len(completed_tools),
                    'failed': len(failed_tools),
                    'execution_time': sum(r.execution_time_seconds for r in results.values())
                }
            }
        )