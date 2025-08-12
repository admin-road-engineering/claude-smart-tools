"""
Configuration settings for Claude Smart Tools
Inherits the sophisticated dual API key system from claude-gemini-mcp
"""
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field, validator

# Get absolute project root path for consistent file resolution
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class SmartToolsConfig(BaseSettings):
    """Configuration for Smart Tools system with inherited claude-gemini-mcp settings"""
    
    # API Configuration - Same as original system
    google_api_key: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    google_api_key2: Optional[str] = Field(None, env="GOOGLE_API_KEY2")
    
    # Timeout Configuration - Inherit generous settings from original
    gemini_request_timeout: float = Field(60.0, env="GEMINI_REQUEST_TIMEOUT")
    gemini_connect_timeout: float = Field(20.0, env="GEMINI_CONNECT_TIMEOUT")
    timeout_retry_count: int = Field(3, env="TIMEOUT_RETRY_COUNT")
    
    # Logging Configuration
    gemini_mcp_log_level: str = Field("INFO", env="GEMINI_MCP_LOG_LEVEL")
    
    # Smart Tools Specific Configuration
    smart_tool_routing_confidence: float = Field(0.7, env="SMART_TOOL_ROUTING_CONFIDENCE")
    enable_multi_engine_synthesis: bool = Field(True, env="ENABLE_MULTI_ENGINE_SYNTHESIS")
    max_engines_per_smart_tool: int = Field(5, env="MAX_ENGINES_PER_SMART_TOOL")
    
    # CPU Performance Configuration - Inherit from original
    file_scan_yield_frequency: int = Field(50, env="FILE_SCAN_YIELD_FREQUENCY")
    processing_yield_interval_ms: int = Field(100, env="PROCESSING_YIELD_INTERVAL_MS")
    max_cpu_usage_percent: float = Field(80.0, env="MAX_CPU_USAGE_PERCENT")
    cpu_check_interval: int = Field(10, env="CPU_CHECK_INTERVAL")
    max_concurrent_reviews: int = Field(4, env="MAX_CONCURRENT_REVIEWS")
    enable_streaming_responses: bool = Field(True, env="ENABLE_STREAMING_RESPONSES")
    
    # Rate Limiting Configuration - Inherit sophisticated settings
    enable_pre_blocking: bool = Field(False, env="ENABLE_PRE_BLOCKING")
    max_block_minutes: float = Field(2.0, env="MAX_BLOCK_MINUTES")
    progressive_backoff_seconds: List[int] = Field([10, 30], env="PROGRESSIVE_BACKOFF_SECONDS")
    retry_other_key_first: bool = Field(True, env="RETRY_OTHER_KEY_FIRST")
    enable_retry_after_header: bool = Field(True, env="ENABLE_RETRY_AFTER_HEADER")
    
    # File Paths
    logs_dir: str = str(PROJECT_ROOT / "logs")
    rate_limit_file: str = str(PROJECT_ROOT / "gemini_rate_limits.json")
    session_log_file: str = str(PROJECT_ROOT / "logs" / "dialogue_sessions.json")
    
    @validator('google_api_key', 'google_api_key2', pre=True)
    def validate_api_keys(cls, v):
        """Ensure at least one API key is provided"""
        return v
    
    @validator('gemini_mcp_log_level')
    def validate_log_level(cls, v):
        """Validate log level is a valid logging level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()
    
    @validator('smart_tool_routing_confidence')
    def validate_routing_confidence(cls, v):
        """Validate routing confidence threshold is between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Routing confidence threshold must be between 0.0 and 1.0")
        return v
    
    @validator('max_cpu_usage_percent')
    def validate_cpu_usage_threshold(cls, v):
        """Validate CPU usage threshold is between 10 and 100"""
        if not 10 <= v <= 100:
            raise ValueError("CPU usage threshold must be between 10.0 and 100.0 percent")
        return v
    
    @property
    def api_keys(self) -> List[str]:
        """Get list of valid API keys - simplified version without security module dependency"""
        keys = []
        if self.google_api_key:
            keys.append(self.google_api_key)
        if self.google_api_key2:
            keys.append(self.google_api_key2)
        
        if not keys:
            raise ValueError("At least one API key (GOOGLE_API_KEY or GOOGLE_API_KEY2) is required")
        return keys
    
    @property
    def log_level_value(self) -> int:
        """Get logging level as integer value"""
        return getattr(logging, self.gemini_mcp_log_level, logging.INFO)
    
    @property
    def gemini_models(self) -> Dict[str, str]:
        """Gemini model configuration - same as original"""
        return {
            "pro": "gemini-2.5-pro",
            "flash": "gemini-2.5-flash", 
            "flash-lite": "gemini-2.5-flash-lite"
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global configuration instance
config = SmartToolsConfig()

# Backward compatibility exports for original tool integration
GOOGLE_API_KEY = config.google_api_key
GOOGLE_API_KEY2 = config.google_api_key2
GEMINI_REQUEST_TIMEOUT = config.gemini_request_timeout
GEMINI_CONNECT_TIMEOUT = config.gemini_connect_timeout
TIMEOUT_RETRY_COUNT = config.timeout_retry_count
GEMINI_MCP_LOG_LEVEL = config.gemini_mcp_log_level
LOG_LEVEL_VALUE = config.log_level_value
GEMINI_MODELS = config.gemini_models
LOGS_DIR = config.logs_dir
RATE_LIMIT_FILE = config.rate_limit_file
SESSION_LOG_FILE = config.session_log_file
API_KEYS = config.api_keys