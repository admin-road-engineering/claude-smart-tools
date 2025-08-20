"""
Abstract repository interfaces for clean separation of concerns
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class SessionRepository(ABC):
    """Abstract interface for session-related data operations"""
    
    @abstractmethod
    def create_session(self, task_id: str, output_type: str, focus: str, context: str = "") -> Dict:
        """Create a new session"""
        pass
    
    @abstractmethod
    def get_session(self, task_id: str) -> Optional[Dict]:
        """Retrieve session with full dialogue history"""
        pass
    
    @abstractmethod
    def add_dialogue_turn(self, task_id: str, round_number: int, model_used: str, 
                         attempts: int, user_input: str = "", ai_response: str = "", 
                         metadata: Dict = None) -> None:
        """Add a dialogue turn to the session"""
        pass
    
    @abstractmethod
    def save_session_summary(self, task_id: str, polished_summary: str, 
                           key_points: List[str] = None, recommendations: List[str] = None) -> None:
        """Save final session summary"""
        pass

class AnalyticsRepository(ABC):
    """Abstract interface for analytics and performance data operations"""
    
    @abstractmethod
    def get_session_stats(self) -> Dict:
        """Get session statistics and analytics"""
        pass
    
    @abstractmethod
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions for analytics"""
        pass
    
    @abstractmethod
    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old sessions for maintenance"""
        pass