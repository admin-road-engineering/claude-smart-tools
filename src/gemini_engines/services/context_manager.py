"""
Context Manager service for cross-tool context sharing.

This service manages the storage, retrieval, and routing of context between tools
during a Claude Code session, enabling intelligent context-aware analysis.
"""
import json
import logging
import sqlite3
import uuid
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone, timedelta

from ..models.context_models import (
    ContextEntry, ContextType, ContextCategory, ContextPriority,
    ToolContextRequirements, ContextCollection, ContextFlow, CodeLocus
)
from ..config import DATABASE_PATH
from ..exceptions import PersistenceError

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages shared context between tools in a Claude Code session.
    
    Features:
    - Store and retrieve context entries
    - Route relevant context to tools based on requirements
    - Track context flow between tools
    - Manage context lifecycle and expiry
    - Provide context analytics and insights
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize ContextManager with database connection.
        
        Args:
            db_path: Path to SQLite database (uses default if None)
        """
        self.db_path = db_path or DATABASE_PATH
        self._init_database()
        
        # In-memory cache for active sessions
        self._session_contexts: Dict[str, ContextCollection] = {}
        self._context_flows: Dict[str, ContextFlow] = {}
        
        # Tool requirements registry
        self._tool_requirements: Dict[str, ToolContextRequirements] = {}
        
        logger.info(f"ContextManager initialized with database: {self.db_path}")
    
    def _init_database(self):
        """Initialize or update database schema for context storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if workflow_context table exists and has all columns
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(workflow_context)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # Add missing columns if table exists
                if existing_columns:
                    columns_to_add = [
                        ("context_type", "TEXT"),
                        ("category", "TEXT"),
                        ("priority", "TEXT DEFAULT 'medium'"),
                        ("title", "TEXT"),
                        ("content", "TEXT"),  # JSON stored as text
                        ("source_tool", "TEXT"),
                        ("source_file", "TEXT"),
                        ("source_line", "INTEGER"),
                        ("confidence", "REAL DEFAULT 0.8"),
                        ("tags", "TEXT"),  # JSON array
                        ("related_contexts", "TEXT")  # JSON array
                    ]
                    
                    for col_name, col_def in columns_to_add:
                        if col_name not in existing_columns:
                            try:
                                conn.execute(f"ALTER TABLE workflow_context ADD COLUMN {col_name} {col_def}")
                                logger.info(f"Added column {col_name} to workflow_context table")
                            except sqlite3.OperationalError:
                                pass  # Column might already exist
                
                # Create indexes for better performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_workflow_context_session 
                    ON workflow_context(session_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_workflow_context_type 
                    ON workflow_context(context_type)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_workflow_context_category 
                    ON workflow_context(category)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_workflow_context_tool 
                    ON workflow_context(source_tool)
                """)
                
                # Create context flow tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS context_flow (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        from_tool TEXT NOT NULL,
                        to_tool TEXT NOT NULL,
                        context_id TEXT NOT NULL,
                        context_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(task_id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_context_flow_session 
                    ON context_flow(session_id)
                """)
                
                conn.commit()
                logger.info("Context database schema initialized/updated successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize context database: {e}")
            raise PersistenceError(f"Context database initialization failed: {e}")
    
    def register_tool_requirements(self, requirements: ToolContextRequirements) -> None:
        """
        Register a tool's context requirements and capabilities.
        
        Args:
            requirements: Tool's context requirements specification
        """
        self._tool_requirements[requirements.tool_name] = requirements
        logger.info(f"Registered context requirements for tool: {requirements.tool_name}")
    
    def add_context(self, session_id: str, entry: ContextEntry) -> str:
        """
        Add a new context entry for a session.
        
        Args:
            session_id: Session identifier
            entry: Context entry to add
            
        Returns:
            ID of the created context entry
        """
        # Generate ID if not provided
        if not entry.id:
            entry.id = str(uuid.uuid4())
        
        entry.session_id = session_id
        
        # Add to in-memory collection
        if session_id not in self._session_contexts:
            self._session_contexts[session_id] = ContextCollection(session_id=session_id)
        
        self._session_contexts[session_id].add_context(entry)
        
        # Persist to database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO workflow_context (
                        session_id, tool_name, step_number, context_data, created_at, expires_at,
                        context_type, category, priority, title, content, source_tool,
                        source_file, source_line, confidence, tags, related_contexts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    entry.source_tool,
                    0,  # step_number - legacy field
                    json.dumps(entry.content),  # Legacy context_data field
                    entry.created_at.isoformat(),
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    entry.type.value,
                    entry.category.value,
                    entry.priority.value,
                    entry.title,
                    json.dumps(entry.content),
                    entry.source_tool,
                    entry.source_file,
                    entry.source_line,
                    entry.confidence,
                    json.dumps(entry.tags),
                    json.dumps(entry.related_contexts)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to persist context entry: {e}")
            raise PersistenceError(f"Failed to save context: {e}")
        
        logger.info(f"Added context entry {entry.id} for session {session_id}: {entry.type} from {entry.source_tool}")
        return entry.id
    
    def get_context_for_tool(self, session_id: str, tool_name: str) -> List[ContextEntry]:
        """
        Get relevant context for a tool based on its requirements.
        
        Args:
            session_id: Session identifier
            tool_name: Name of the tool requesting context
            
        Returns:
            List of relevant context entries
        """
        # Get tool requirements
        requirements = self._tool_requirements.get(tool_name)
        if not requirements:
            logger.warning(f"No requirements registered for tool: {tool_name}")
            return []
        
        # Get session context collection
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return []
        
        # Get relevant context
        relevant_context = collection.get_context_for_tool(requirements)
        
        # Record context flow for each relevant entry
        for entry in relevant_context:
            self._record_context_flow(session_id, entry.source_tool, tool_name, 
                                    entry.id, entry.type)
        
        logger.info(f"Providing {len(relevant_context)} context entries to {tool_name}")
        return relevant_context
    
    def get_context_by_type(self, session_id: str, context_type: ContextType) -> List[ContextEntry]:
        """
        Get all context entries of a specific type.
        
        Args:
            session_id: Session identifier
            context_type: Type of context to retrieve
            
        Returns:
            List of matching context entries
        """
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return []
        
        return collection.get_by_type(context_type)
    
    def get_context_by_category(self, session_id: str, category: ContextCategory) -> List[ContextEntry]:
        """
        Get all context entries in a specific category.
        
        Args:
            session_id: Session identifier
            category: Category to filter by
            
        Returns:
            List of matching context entries
        """
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return []
        
        return collection.get_by_category(category)
    
    def get_high_priority_context(self, session_id: str) -> List[ContextEntry]:
        """
        Get all high priority context entries for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of critical and high priority context entries
        """
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return []
        
        return [e for e in collection.entries 
                if e.priority in [ContextPriority.CRITICAL, ContextPriority.HIGH]
                and not e.is_expired]
    
    def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary statistics about context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary dictionary with statistics
        """
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return {'error': 'No context found for session'}
        
        summary = collection.get_summary()
        
        # Add flow information if available
        if session_id in self._context_flows:
            flow = self._context_flows[session_id]
            summary['tool_dependencies'] = flow.get_tool_dependencies()
            summary['most_connected_tools'] = flow.get_most_connected_tools()[:5]
        
        return summary
    
    def _load_session_context(self, session_id: str) -> None:
        """
        Load context from database for a session.
        
        Args:
            session_id: Session identifier
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT context_type, category, priority, title, content,
                           source_tool, source_file, source_line, confidence,
                           tags, related_contexts, created_at, expires_at
                    FROM workflow_context
                    WHERE session_id = ?
                    ORDER BY created_at
                """, (session_id,))
                
                collection = ContextCollection(session_id=session_id)
                
                for row in cursor.fetchall():
                    try:
                        entry = ContextEntry(
                            type=ContextType(row[0]) if row[0] else ContextType.FINDING,
                            category=ContextCategory(row[1]) if row[1] else ContextCategory.QUALITY,
                            priority=ContextPriority(row[2]) if row[2] else ContextPriority.MEDIUM,
                            title=row[3] or "Untitled",
                            content=json.loads(row[4]) if row[4] else {},
                            source_tool=row[5] or "unknown",
                            source_file=row[6],
                            source_line=row[7],
                            confidence=row[8] or 0.8,
                            tags=json.loads(row[9]) if row[9] else [],
                            related_contexts=json.loads(row[10]) if row[10] else [],
                            created_at=datetime.fromisoformat(row[11]) if row[11] else datetime.now(timezone.utc),
                            expires_at=datetime.fromisoformat(row[12]) if row[12] else None
                        )
                        collection.add_context(entry)
                    except Exception as e:
                        logger.warning(f"Failed to load context entry: {e}")
                
                self._session_contexts[session_id] = collection
                logger.info(f"Loaded {len(collection.entries)} context entries for session {session_id}")
                
        except Exception as e:
            logger.error(f"Failed to load session context: {e}")
            self._session_contexts[session_id] = ContextCollection(session_id=session_id)
    
    def _record_context_flow(self, session_id: str, from_tool: str, to_tool: str,
                           context_id: str, context_type: ContextType) -> None:
        """
        Record context flow between tools.
        
        Args:
            session_id: Session identifier
            from_tool: Tool that created the context
            to_tool: Tool that consumed the context
            context_id: ID of the context entry
            context_type: Type of context
        """
        # Update in-memory flow
        if session_id not in self._context_flows:
            self._context_flows[session_id] = ContextFlow(session_id=session_id)
        
        self._context_flows[session_id].record_flow(from_tool, to_tool, context_id, context_type)
        
        # Persist to database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO context_flow (
                        session_id, from_tool, to_tool, context_id, context_type, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id, from_tool, to_tool, context_id, 
                    context_type.value, datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record context flow: {e}")
    
    def cleanup_expired_context(self, session_id: str = None) -> int:
        """
        Remove expired context entries.
        
        Args:
            session_id: Optional session ID to cleanup (all sessions if None)
            
        Returns:
            Number of entries removed
        """
        total_removed = 0
        
        if session_id:
            sessions = [session_id]
        else:
            sessions = list(self._session_contexts.keys())
        
        for sid in sessions:
            if sid in self._session_contexts:
                removed = self._session_contexts[sid].remove_expired()
                total_removed += removed
                if removed > 0:
                    logger.info(f"Removed {removed} expired context entries from session {sid}")
        
        # Also cleanup in database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if session_id:
                    cursor.execute("""
                        DELETE FROM workflow_context 
                        WHERE session_id = ? AND expires_at < ?
                    """, (session_id, datetime.now(timezone.utc).isoformat()))
                else:
                    cursor.execute("""
                        DELETE FROM workflow_context 
                        WHERE expires_at < ?
                    """, (datetime.now(timezone.utc).isoformat(),))
                
                db_removed = cursor.rowcount
                conn.commit()
                
                if db_removed > 0:
                    logger.info(f"Removed {db_removed} expired context entries from database")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup expired context in database: {e}")
        
        return total_removed
    
    def merge_session_contexts(self, session_id: str, strategy: str = "consensus") -> List[ContextEntry]:
        """
        Merge related context entries in a session.
        
        This is useful when multiple tools have analyzed the same code and we want
        to consolidate their findings to avoid redundancy.
        
        Args:
            session_id: Session identifier
            strategy: Merge strategy (consensus, union, latest)
            
        Returns:
            List of merged context entries
        """
        if session_id not in self._session_contexts:
            self._load_session_context(session_id)
        
        collection = self._session_contexts.get(session_id)
        if not collection:
            return []
        
        merged = collection.merge_related_contexts(strategy)
        logger.info(f"Merged {len(collection.entries)} contexts into {len(merged)} entries using {strategy} strategy")
        
        return merged
    
    def get_context_flow_visualization(self, session_id: str) -> str:
        """
        Generate a text visualization of context flow between tools.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Text representation of context flow
        """
        if session_id not in self._context_flows:
            # Try to load from database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT from_tool, to_tool, context_type, COUNT(*) as count
                        FROM context_flow
                        WHERE session_id = ?
                        GROUP BY from_tool, to_tool, context_type
                        ORDER BY count DESC
                    """, (session_id,))
                    
                    flows = cursor.fetchall()
                    if not flows:
                        return "No context flow recorded for this session"
                    
                    lines = ["## Context Flow Between Tools\n"]
                    for from_tool, to_tool, context_type, count in flows:
                        lines.append(f"  {from_tool} → {to_tool}: {context_type} ({count}x)")
                    
                    return "\n".join(lines)
                    
            except Exception as e:
                logger.error(f"Failed to load context flow: {e}")
                return "Error loading context flow"
        
        flow = self._context_flows[session_id]
        dependencies = flow.get_tool_dependencies()
        
        if not dependencies:
            return "No context flow recorded for this session"
        
        lines = ["## Context Flow Between Tools\n"]
        for tool, sources in dependencies.items():
            lines.append(f"  {tool} receives context from: {', '.join(sources)}")
        
        lines.append("\n## Most Connected Tools:")
        for tool, count in flow.get_most_connected_tools()[:5]:
            lines.append(f"  {tool}: {count} connections")
        
        return "\n".join(lines)