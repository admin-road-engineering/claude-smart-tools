"""
Session management implementation for comprehensive review system.
Handles persistence, state tracking, and dialogue management.
"""
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..tools.interfaces import ISessionManager, AnalysisResult, ToolStatus
from ..persistence.sqlite_session_store import SqliteSessionStore

logger = logging.getLogger(__name__)


class SessionManager(ISessionManager):
    """
    Concrete implementation of session management using SQLite storage.
    Provides enhanced failure tracking and state recovery capabilities.
    """
    
    def __init__(self, session_store: SqliteSessionStore = None):
        """
        Initialize SessionManager with storage backend.
        
        Args:
            session_store: SQLite storage instance (will create if None)
        """
        self.session_store = session_store or SqliteSessionStore()
        
    async def create_session(self, 
                           task_id: str, 
                           review_type: str, 
                           focus: str, 
                           context: str = "") -> Dict[str, Any]:
        """
        Create a new comprehensive review session.
        
        Args:
            task_id: Unique session identifier
            review_type: Type of review (comprehensive_review)
            focus: Focus area for the review
            context: Additional context information
            
        Returns:
            Session data dictionary
        """
        try:
            # Create session in storage
            session = self.session_store.create_session(
                task_id=task_id,
                output_type=review_type,
                focus=focus,
                context=context
            )
            
            # Initialize session metadata
            session_data = {
                'task_id': task_id,
                'review_type': review_type,
                'focus': focus,
                'context': context,
                'created_at': datetime.now(),
                'total_rounds': 0,
                'status': 'active',
                'failed_tools': [],
                'completed_tools': []
            }
            
            # Store initial session state
            await self._save_session_metadata(task_id, session_data)
            
            logger.info(f"Created new session: {task_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to create session {task_id}: {e}")
            raise
    
    async def get_session(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by task ID.
        
        Args:
            task_id: Session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        try:
            # Get basic session from storage
            session = self.session_store.get_session(task_id)
            if not session:
                return None
            
            # Load enhanced session metadata
            metadata = await self._load_session_metadata(task_id)
            
            # Merge storage data with metadata
            session_data = {
                'task_id': task_id,
                'review_type': session.get('output_type', 'comprehensive_review'),
                'focus': session.get('focus', 'all'),
                'context': session.get('context', ''),
                'total_rounds': session.get('total_rounds', 0),
                'created_at': session.get('created_at'),
                **metadata  # Add enhanced metadata
            }
            
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to get session {task_id}: {e}")
            return None
    
    async def save_tool_results(self, 
                               task_id: str, 
                               round_number: int,
                               results: Dict[str, AnalysisResult]) -> None:
        """
        Save tool execution results for a dialogue round.
        
        Args:
            task_id: Session identifier
            round_number: Current dialogue round
            results: Dictionary of tool results by tool name
        """
        try:
            # Convert AnalysisResult objects to serializable format
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
                tool_name="comprehensive_review_results",
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
            
            # Update session metadata with tool tracking
            await self._update_session_tools(task_id, completed_tools, failed_tools)
            
            logger.info(f"Saved results for {len(results)} tools in session {task_id}, round {round_number}")
            
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
            # Get workflow contexts for this session
            contexts = self.session_store.get_workflow_context(session_id=task_id)
            
            results_by_round = {}
            
            for context in contexts:
                context_data = context.get('context_data', {})
                if 'tool_results' in context_data:
                    round_num = context.get('round_number', 1)
                    tool_results = {}
                    
                    # Convert back to AnalysisResult objects
                    for tool_name, result_data in context_data['tool_results'].items():
                        tool_results[tool_name] = AnalysisResult(
                            tool_name=result_data['tool_name'],
                            status=ToolStatus[result_data['status']],
                            output=result_data['output'],
                            error_message=result_data.get('error_message'),
                            execution_time_seconds=result_data.get('execution_time_seconds', 0.0),
                            timestamp=datetime.fromisoformat(result_data['timestamp']) if result_data.get('timestamp') else None
                        )
                    
                    results_by_round[round_num] = tool_results
            
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
            metadata = await self._load_session_metadata(task_id)
            metadata['failed_tools'] = list(set(metadata.get('failed_tools', []) + failed_tools))
            metadata['last_failure_update'] = datetime.now().isoformat()
            
            await self._save_session_metadata(task_id, metadata)
            
            logger.info(f"Updated failed tools for session {task_id}: {failed_tools}")
            
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
            metadata = await self._load_session_metadata(task_id)
            return metadata.get('failed_tools', [])
            
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
            metadata = await self._load_session_metadata(task_id)
            current_failed = set(metadata.get('failed_tools', []))
            
            if cleared_tools:
                # Remove specific tools
                current_failed -= set(cleared_tools)
            else:
                # Clear all failed tools
                current_failed.clear()
            
            metadata['failed_tools'] = list(current_failed)
            metadata['last_failure_clear'] = datetime.now().isoformat()
            
            await self._save_session_metadata(task_id, metadata)
            
            logger.info(f"Cleared failed tools for session {task_id}: {cleared_tools or 'all'}")
            
        except Exception as e:
            logger.error(f"Failed to clear failed tools for session {task_id}: {e}")
            raise
    
    async def add_dialogue_turn(self, 
                               task_id: str, 
                               round_number: int,
                               user_input: str, 
                               ai_response: str,
                               metadata: Dict[str, Any] = None) -> None:
        """
        Add a dialogue turn to the session.
        
        Args:
            task_id: Session identifier
            round_number: Current dialogue round
            user_input: User's input for this turn
            ai_response: AI's response for this turn
            metadata: Additional metadata for this turn
        """
        try:
            # Add to dialogue turns in storage
            self.session_store.add_dialogue_turn(
                task_id=task_id,
                round_number=round_number,
                model_used="comprehensive_orchestrator",
                attempts=1,
                user_input=user_input[:1000],  # Truncate for storage
                ai_response=ai_response[:1000],  # Truncate for storage
                metadata=metadata or {}
            )
            
            # Update session metadata
            session_metadata = await self._load_session_metadata(task_id)
            session_metadata['total_rounds'] = max(session_metadata.get('total_rounds', 0), round_number)
            session_metadata['last_activity'] = datetime.now().isoformat()
            
            await self._save_session_metadata(task_id, session_metadata)
            
            logger.debug(f"Added dialogue turn {round_number} to session {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to add dialogue turn to session {task_id}: {e}")
            raise
    
    async def get_dialogue_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get complete dialogue history for a session.
        
        Args:
            task_id: Session identifier
            
        Returns:
            List of dialogue turns with metadata
        """
        try:
            # Get dialogue turns from storage
            turns = self.session_store.get_dialogue_turns(task_id)
            
            dialogue_history = []
            for turn in turns:
                dialogue_history.append({
                    'round_number': turn.get('round_number'),
                    'user_input': turn.get('user_input'),
                    'ai_response': turn.get('ai_response'),
                    'timestamp': turn.get('timestamp'),
                    'metadata': turn.get('metadata', {})
                })
            
            return dialogue_history
            
        except Exception as e:
            logger.error(f"Failed to get dialogue history for session {task_id}: {e}")
            return []
    
    async def is_session_recoverable(self, task_id: str) -> bool:
        """
        Check if a session can be recovered after interruption.
        
        Args:
            task_id: Session identifier
            
        Returns:
            True if session can be continued
        """
        try:
            session = await self.get_session(task_id)
            if not session:
                return False
            
            # Check if session is active and recent
            if session.get('status') != 'active':
                return False
            
            # Session is recoverable if it exists and is active
            return True
            
        except Exception as e:
            logger.error(f"Failed to check session recoverability {task_id}: {e}")
            return False
    
    async def _save_session_metadata(self, task_id: str, metadata: Dict[str, Any]) -> None:
        """Save enhanced session metadata"""
        # Convert datetime objects to ISO strings for JSON serialization
        serializable_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, datetime):
                serializable_metadata[key] = value.isoformat()
            else:
                serializable_metadata[key] = value
        
        # Save as workflow context
        self.session_store.save_workflow_context(
            session_id=task_id,
            tool_name="session_metadata", 
            step_number=0,  # Use step 0 for metadata
            context_data=serializable_metadata
        )
    
    async def _load_session_metadata(self, task_id: str) -> Dict[str, Any]:
        """Load enhanced session metadata"""
        try:
            contexts = self.session_store.get_workflow_context(session_id=task_id, tool_name="session_metadata")
            if contexts:
                metadata = contexts[0].get('context_data', {})
                
                # Convert ISO strings back to datetime objects where appropriate
                for key in ['created_at', 'last_activity', 'last_failure_update', 'last_failure_clear']:
                    if key in metadata and isinstance(metadata[key], str):
                        try:
                            metadata[key] = datetime.fromisoformat(metadata[key])
                        except ValueError:
                            pass
                
                return metadata
            
            # Return default metadata if none exists
            return {
                'status': 'active',
                'failed_tools': [],
                'completed_tools': [],
                'total_rounds': 0
            }
            
        except Exception as e:
            logger.error(f"Failed to load session metadata for {task_id}: {e}")
            return {}
    
    async def _update_session_tools(self, task_id: str, completed_tools: List[str], failed_tools: List[str]) -> None:
        """Update session metadata with tool execution status"""
        try:
            metadata = await self._load_session_metadata(task_id)
            
            # Update completed tools
            current_completed = set(metadata.get('completed_tools', []))
            current_completed.update(completed_tools)
            metadata['completed_tools'] = list(current_completed)
            
            # Update failed tools
            current_failed = set(metadata.get('failed_tools', []))
            current_failed.update(failed_tools)
            # Remove any tools that succeeded from failed list
            current_failed -= set(completed_tools)
            metadata['failed_tools'] = list(current_failed)
            
            await self._save_session_metadata(task_id, metadata)
            
        except Exception as e:
            logger.error(f"Failed to update session tools for {task_id}: {e}")