"""
SQLite-based session storage with ACID guarantees

SECURITY AUDIT (2025-01-08): All SQL queries in this module use parameterized 
statements with ? placeholders. No SQL injection vulnerabilities found.
All user inputs are properly escaped through SQLite's parameter binding.
"""
import sqlite3
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..config import DATABASE_PATH
from .base_repositories import SessionRepository, AnalyticsRepository
from ..exceptions import PersistenceError


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

logger = logging.getLogger(__name__)

class SqliteSessionStore(SessionRepository, AnalyticsRepository):
    """SQLite-based session storage with ACID guarantees"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    task_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    output_type TEXT,
                    focus TEXT,
                    context TEXT,
                    total_rounds INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)
            
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dialogue_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        round_number INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        model_used TEXT,
                        attempts INTEGER DEFAULT 1,
                        user_input TEXT,
                        ai_response TEXT,
                        metadata TEXT,
                        FOREIGN KEY (task_id) REFERENCES sessions (task_id)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_summaries (
                        task_id TEXT PRIMARY KEY,
                        polished_summary TEXT,
                        key_points TEXT,
                        recommendations TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (task_id) REFERENCES sessions (task_id)
                    )
                """)
                
                # New tables for enhanced tool functionality
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_context (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        tool_name TEXT NOT NULL,
                        step_number INTEGER NOT NULL,
                        context_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        FOREIGN KEY (session_id) REFERENCES sessions (task_id)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tool_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        tool_name TEXT NOT NULL,
                        execution_time_ms INTEGER,
                        success BOOLEAN NOT NULL,
                        result_count INTEGER DEFAULT 0,
                        timeout_level INTEGER DEFAULT 1,
                        complexity_level TEXT,
                        error_code TEXT,
                        created_at TEXT NOT NULL,
                        parameters TEXT,
                        FOREIGN KEY (session_id) REFERENCES sessions (task_id)
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_dialogue_turns_task_id ON dialogue_turns (task_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_dialogue_turns_round ON dialogue_turns (task_id, round_number)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_context_session ON workflow_context (session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_metrics_session ON tool_metrics (session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_metrics_tool ON tool_metrics (tool_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_metrics_created ON tool_metrics (created_at)")
            
                conn.commit()
                logger.info(f"Initialized SQLite database with enhanced schema at {self.db_path}")
        except sqlite3.Error as e:
            raise PersistenceError(f"Failed to initialize database: {e}")
    
    def create_session(self, task_id: str, output_type: str, focus: str, context: str = "") -> Dict:
        """Create new session with ACID guarantees"""
        session_data = {
            'task_id': task_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'output_type': output_type,
            'focus': focus,
            'context': context,
            'total_rounds': 0,
            'status': 'active'
        }
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions 
                (task_id, created_at, updated_at, output_type, focus, context, total_rounds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, session_data['created_at'], session_data['updated_at'],
                output_type, focus, context, 0, 'active'
            ))
            conn.commit()
        
        logger.info(f"Created session {task_id}")
        return session_data
    
    def add_dialogue_turn(self, task_id: str, round_number: int, model_used: str, 
                         attempts: int, user_input: str = "", ai_response: str = "", 
                         metadata: Dict = None) -> None:
        """Add dialogue turn with transactional safety"""
        with sqlite3.connect(self.db_path) as conn:
            # Ensure metadata is JSON-serializable by handling Pydantic models
            serializable_metadata = None
            if metadata:
                try:
                    serializable_metadata = {}
                    for key, value in metadata.items():
                        if hasattr(value, 'model_dump'):
                            # Handle Pydantic models (like IntentResult)
                            serializable_metadata[key] = value.model_dump()
                        elif hasattr(value, 'dict') and callable(value.dict):
                            # Handle Pydantic v1 models
                            serializable_metadata[key] = value.dict()
                        else:
                            serializable_metadata[key] = value
                except Exception as e:
                    logger.warning(f"Failed to serialize metadata for dialogue turn: {e}")
                    serializable_metadata = {"error": "Failed to serialize metadata"}
            
            # Insert dialogue turn
            conn.execute("""
                INSERT INTO dialogue_turns 
                (task_id, round_number, timestamp, model_used, attempts, user_input, ai_response, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, round_number, datetime.now().isoformat(),
                model_used, attempts, user_input, ai_response,
                json.dumps(serializable_metadata, cls=DateTimeEncoder) if serializable_metadata else None
            ))
            
            # Update session round count
            conn.execute("""
                UPDATE sessions 
                SET total_rounds = ?, updated_at = ?
                WHERE task_id = ?
            """, (round_number, datetime.now().isoformat(), task_id))
            
            conn.commit()
        
        logger.info(f"Added turn {round_number} to session {task_id}")
    
    def get_session(self, task_id: str) -> Optional[Dict]:
        """Retrieve session with full dialogue history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get session info
            session_row = conn.execute("""
                SELECT * FROM sessions WHERE task_id = ?
            """, (task_id,)).fetchone()
            
            if not session_row:
                return None
            
            # Get dialogue turns
            turns = conn.execute("""
                SELECT * FROM dialogue_turns 
                WHERE task_id = ? 
                ORDER BY round_number
            """, (task_id,)).fetchall()
            
            # Get summary if exists
            summary_row = conn.execute("""
                SELECT * FROM session_summaries WHERE task_id = ?
            """, (task_id,)).fetchone()
            
            # Build session dict
            session = dict(session_row)
            session['dialogue_turns'] = []
            for turn in turns:
                turn_dict = dict(turn)
                if turn_dict['metadata']:
                    turn_dict['metadata'] = json.loads(turn_dict['metadata'])
                session['dialogue_turns'].append(turn_dict)
            
            if summary_row:
                summary_dict = dict(summary_row)
                if summary_dict['key_points']:
                    summary_dict['key_points'] = json.loads(summary_dict['key_points'])
                if summary_dict['recommendations']:
                    summary_dict['recommendations'] = json.loads(summary_dict['recommendations'])
                session['summary'] = summary_dict
            else:
                session['summary'] = None
            
            return session
    
    def get_recent_dialogue(self, task_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get recent dialogue exchanges for context"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT claude_content, gemini_response, round_number, created_at
                    FROM dialogue_turns
                    WHERE task_id = ?
                    ORDER BY round_number DESC
                    LIMIT ?
                """, (task_id, limit))
                
                rows = cursor.fetchall()
                
                # Convert to list of dicts in chronological order
                dialogue_history = []
                for row in reversed(rows):  # Reverse to get chronological order
                    dialogue_history.append({
                        "claude_response": row[0],
                        "gemini_response": row[1],
                        "round_number": row[2],
                        "timestamp": row[3]
                    })
                
                self.logger.info(f"Retrieved {len(dialogue_history)} dialogue exchanges for task {task_id}")
                return dialogue_history
                
        except Exception as e:
            self.logger.error(f"Failed to get dialogue history: {e}")
            return []
    
    def get_dialogue_turns(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all dialogue turns for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT round_number, claude_content as user_input, gemini_response as ai_response, 
                           created_at as timestamp, metadata
                    FROM dialogue_turns
                    WHERE task_id = ?
                    ORDER BY round_number ASC
                """, (task_id,))
                
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = dict(row)
                    # Parse metadata JSON if present
                    if row_dict.get('metadata'):
                        try:
                            row_dict['metadata'] = json.loads(row_dict['metadata'])
                        except (json.JSONDecodeError, TypeError):
                            row_dict['metadata'] = {}
                    else:
                        row_dict['metadata'] = {}
                    result.append(row_dict)
                
                return result
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get dialogue turns for {task_id}: {e}")
            return []
    
    def save_session_summary(self, task_id: str, polished_summary: str, 
                           key_points: List[str] = None, recommendations: List[str] = None) -> None:
        """Save final session summary"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO session_summaries 
                (task_id, polished_summary, key_points, recommendations, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                task_id, polished_summary,
                json.dumps(key_points, cls=DateTimeEncoder) if key_points else None,
                json.dumps(recommendations, cls=DateTimeEncoder) if recommendations else None,
                datetime.now().isoformat()
            ))
            
            # Mark session as completed
            conn.execute("""
                UPDATE sessions SET status = 'completed' WHERE task_id = ?
            """, (task_id,))
            
            conn.commit()
        
        logger.info(f"Saved summary for session {task_id}")
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions for analytics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT task_id, created_at, output_type, focus, total_rounds, status
                FROM sessions 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up sessions older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with sqlite3.connect(self.db_path) as conn:
            # Delete old workflow contexts first (foreign key constraint)
            conn.execute("""
                DELETE FROM workflow_context 
                WHERE session_id IN (
                    SELECT task_id FROM sessions 
                    WHERE created_at < ?
                )
            """, (cutoff_date.isoformat(),))
            
            # Delete old tool metrics 
            conn.execute("""
                DELETE FROM tool_metrics 
                WHERE session_id IN (
                    SELECT task_id FROM sessions 
                    WHERE created_at < ?
                )
            """, (cutoff_date.isoformat(),))
            
            # Delete old dialogue turns (foreign key constraint)
            conn.execute("""
                DELETE FROM dialogue_turns 
                WHERE task_id IN (
                    SELECT task_id FROM sessions 
                    WHERE created_at < ?
                )
            """, (cutoff_date.isoformat(),))
            
            # Delete old summaries
            conn.execute("""
                DELETE FROM session_summaries 
                WHERE task_id IN (
                    SELECT task_id FROM sessions 
                    WHERE created_at < ?
                )
            """, (cutoff_date.isoformat(),))
            
            # Delete old sessions
            result = conn.execute("""
                DELETE FROM sessions WHERE created_at < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = result.rowcount
            conn.commit()
        
        logger.info(f"Cleaned up {deleted_count} old sessions")
        return deleted_count
    
    def get_session_stats(self) -> Dict:
        """Get session statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            stats = {}
            
            # Total sessions
            stats['total_sessions'] = conn.execute("SELECT COUNT(*) as count FROM sessions").fetchone()['count']
            
            # Active vs completed sessions
            status_counts = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM sessions 
                GROUP BY status
            """).fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in status_counts}
            
            # Average rounds per session
            avg_rounds = conn.execute("""
                SELECT AVG(total_rounds) as avg_rounds 
                FROM sessions 
                WHERE total_rounds > 0
            """).fetchone()
            stats['avg_rounds_per_session'] = round(avg_rounds['avg_rounds'] or 0, 2)
            
            return stats
    
    # Enhanced methods for workflow context and tool metrics
    
    def save_workflow_context(self, session_id: str, tool_name: str, step_number: int, 
                            context_data: Dict, expires_minutes: int = 60) -> None:
        """Save workflow context for cross-tool integration"""
        expires_at = datetime.now() + timedelta(minutes=expires_minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO workflow_context 
                (session_id, tool_name, step_number, context_data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id, tool_name, step_number, 
                json.dumps(context_data, cls=DateTimeEncoder), 
                datetime.now().isoformat(),
                expires_at.isoformat()
            ))
            conn.commit()
        
        logger.debug(f"Saved workflow context for {tool_name} step {step_number}")
    
    def get_workflow_context(self, session_id: str, tool_name: str = None) -> List[Dict]:
        """Get workflow context, optionally filtered by tool"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if tool_name:
                rows = conn.execute("""
                    SELECT * FROM workflow_context 
                    WHERE session_id = ? AND tool_name = ? 
                    AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY step_number ASC
                """, (session_id, tool_name, datetime.now().isoformat())).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM workflow_context 
                    WHERE session_id = ? 
                    AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY step_number ASC
                """, (session_id, datetime.now().isoformat())).fetchall()
            
            contexts = []
            for row in rows:
                context = dict(row)
                context['context_data'] = json.loads(context['context_data'])
                contexts.append(context)
            
            return contexts
    
    def cleanup_expired_workflow_context(self) -> int:
        """Clean up expired workflow context"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                DELETE FROM workflow_context 
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (datetime.now().isoformat(),))
            
            deleted_count = result.rowcount
            conn.commit()
        
        if deleted_count > 0:
            logger.debug(f"Cleaned up {deleted_count} expired workflow contexts")
        return deleted_count
    
    def save_tool_metrics(self, session_id: str, tool_name: str, execution_time_ms: int,
                         success: bool, result_count: int = 0, timeout_level: int = 1,
                         complexity_level: str = None, error_code: str = None,
                         parameters: Dict = None) -> None:
        """Save tool execution metrics for analytics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO tool_metrics 
                (session_id, tool_name, execution_time_ms, success, result_count, 
                 timeout_level, complexity_level, error_code, created_at, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, tool_name, execution_time_ms, success, result_count,
                timeout_level, complexity_level, error_code,
                datetime.now().isoformat(),
                json.dumps(parameters, cls=DateTimeEncoder) if parameters else None
            ))
            conn.commit()
        
        logger.debug(f"Saved metrics for {tool_name}: {execution_time_ms}ms, success={success}")
    
    def get_tool_metrics(self, session_id: str = None, tool_name: str = None, 
                        hours_back: int = 24) -> List[Dict]:
        """Get tool metrics for analytics"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            where_conditions = ["created_at > ?"]
            params = [cutoff_time.isoformat()]
            
            if session_id:
                where_conditions.append("session_id = ?")
                params.append(session_id)
            
            if tool_name:
                where_conditions.append("tool_name = ?")
                params.append(tool_name)
            
            where_clause = " AND ".join(where_conditions)
            
            # SECURITY: Building SQL safely - where_clause only contains safe column names
            # and ? placeholders, no user input is directly concatenated
            query = f"""
                SELECT * FROM tool_metrics 
                WHERE {where_clause}
                ORDER BY created_at DESC
            """
            rows = conn.execute(query, params).fetchall()
            
            metrics = []
            for row in rows:
                metric = dict(row)
                if metric['parameters']:
                    metric['parameters'] = json.loads(metric['parameters'])
                metrics.append(metric)
            
            return metrics
    
    def get_tool_performance_stats(self, tool_name: str = None, days_back: int = 7) -> Dict:
        """Get performance statistics for tools"""
        cutoff_time = datetime.now() - timedelta(days=days_back)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            base_query = """
                SELECT 
                    tool_name,
                    COUNT(*) as total_executions,
                    AVG(execution_time_ms) as avg_execution_time,
                    MAX(execution_time_ms) as max_execution_time,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_executions,
                    AVG(result_count) as avg_result_count,
                    AVG(timeout_level) as avg_timeout_level
                FROM tool_metrics 
                WHERE created_at > ?
            """
            
            params = [cutoff_time.isoformat()]
            
            if tool_name:
                base_query += " AND tool_name = ?"
                params.append(tool_name)
            
            base_query += " GROUP BY tool_name ORDER BY total_executions DESC"
            
            rows = conn.execute(base_query, params).fetchall()
            
            stats = {}
            for row in rows:
                tool_stats = dict(row)
                tool_stats['success_rate'] = round(
                    (tool_stats['successful_executions'] / tool_stats['total_executions']) * 100, 2
                ) if tool_stats['total_executions'] > 0 else 0
                tool_stats['avg_execution_time'] = round(tool_stats['avg_execution_time'] or 0, 2)
                tool_stats['avg_result_count'] = round(tool_stats['avg_result_count'] or 0, 2)
                tool_stats['avg_timeout_level'] = round(tool_stats['avg_timeout_level'] or 0, 2)
                
                stats[tool_stats['tool_name']] = tool_stats
            
            return stats