"""
Base class for smart tools that route to multiple engines
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class SmartToolResult(BaseModel):
    """Result from a smart tool execution"""
    tool_name: str
    success: bool
    result: str
    engines_used: List[str]
    routing_decision: str
    metadata: Dict[str, Any] = {}


class BaseSmartTool(ABC):
    """Base class for all smart tools"""
    
    def __init__(self, engines: Dict[str, Any]):
        self.engines = engines
        self.tool_name = self.__class__.__name__.replace('Tool', '').lower()
    
    @abstractmethod
    async def execute(self, **kwargs) -> SmartToolResult:
        """Execute the smart tool with intelligent routing"""
        pass
    
    @abstractmethod
    def get_routing_strategy(self, **kwargs) -> Dict[str, Any]:
        """Determine which engines to use and how"""
        pass
    
    def get_available_engines(self) -> List[str]:
        """Get list of available engine names"""
        return list(self.engines.keys())
    
    async def execute_engine(self, engine_name: str, **kwargs) -> Any:
        """Execute a specific engine with improved error handling"""
        if engine_name not in self.engines:
            return f"Engine {engine_name} not available"
        
        try:
            engine = self.engines[engine_name]
            if hasattr(engine, 'execute'):
                result = await engine.execute(**kwargs)
            else:
                # Direct function call
                result = await engine(**kwargs)
            return result
        except Exception as e:
            error_msg = str(e)
            
            # Improve rate limiting error messages
            if "rate limited" in error_msg.lower() or "exhausted" in error_msg.lower():
                return f"⚠️ Rate limit reached. The Gemini API has usage limits. Please try again in a few minutes."
            
            # Improve file not found messages
            if "no files found" in error_msg.lower() or "no code files" in error_msg.lower():
                return f"📁 No valid files found. Please check the file paths."
            
            # API key issues
            if "api key" in error_msg.lower():
                return f"🔑 API key issue detected. Please check your Gemini API configuration."
            
            # General error with more context
            return f"Error in {engine_name}: {error_msg[:200]}..."