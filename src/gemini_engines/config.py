"""
Configuration settings for the Gemini MCP Server
Centralized, typed configuration using Pydantic BaseSettings
"""
import logging
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


class GeminiMCPConfig(BaseSettings):
    """Typed configuration for Gemini MCP Server with validation"""
    
    # API Configuration
    google_api_key: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    google_api_key2: Optional[str] = Field(None, env="GOOGLE_API_KEY2")
    
    # Timeout Configuration (Generous for 32GB RAM system)
    gemini_request_timeout: float = Field(60.0, env="GEMINI_REQUEST_TIMEOUT")  # Increased from 30s
    gemini_connect_timeout: float = Field(20.0, env="GEMINI_CONNECT_TIMEOUT")  # Increased from 10s
    timeout_retry_count: int = Field(3, env="TIMEOUT_RETRY_COUNT")  # Increased from 2
    
    # Logging Configuration
    gemini_mcp_log_level: str = Field("INFO", env="GEMINI_MCP_LOG_LEVEL")
    
    # File Freshness Guardian Configuration
    file_cache_ttl_seconds: int = Field(300, env="FILE_CACHE_TTL_SECONDS")
    file_cache_max_size: int = Field(1000, env="FILE_CACHE_MAX_SIZE")
    enable_gitignore_filtering: bool = Field(True, env="ENABLE_GITIGNORE_FILTERING")
    validation_confidence_threshold: float = Field(0.1, env="VALIDATION_CONFIDENCE_THRESHOLD")
    max_concurrent_file_reads: int = Field(10, env="MAX_CONCURRENT_FILE_READS")
    
    # Phase 2 Enhanced Tool Suite Configuration
    # Test Coverage Analyzer
    test_mapping_strategy: str = Field("convention", env="TEST_MAPPING_STRATEGY")  # "convention", "directory", "docstring"
    ast_parsing_timeout: int = Field(30, env="AST_PARSING_TIMEOUT")  # seconds per file
    coverage_complexity_threshold: float = Field(0.7, env="COVERAGE_COMPLEXITY_THRESHOLD")
    
    # Dependency Mapper
    dependency_graph_depth_limit: int = Field(50, env="DEPENDENCY_GRAPH_DEPTH_LIMIT")
    coupling_threshold: float = Field(0.7, env="COUPLING_THRESHOLD")
    high_impact_threshold: float = Field(0.8, env="HIGH_IMPACT_THRESHOLD")
    max_summary_nodes: int = Field(20, env="MAX_SUMMARY_NODES")
    max_summary_edges: int = Field(50, env="MAX_SUMMARY_EDGES")
    enable_dot_export: bool = Field(False, env="ENABLE_DOT_EXPORT")
    
    # Phase 0 Enhanced Tools Configuration
    # API Contract Checker
    breaking_change_sensitivity: str = Field("balanced", env="BREAKING_CHANGE_SENSITIVITY")  # "strict", "balanced", "lenient"
    # Interface Inconsistency Detector
    interface_priority_threshold: float = Field(5.0, env="INTERFACE_PRIORITY_THRESHOLD")  # Only show issues >= this score
    
    # Comprehensive Review Tool Configuration
    max_comprehensive_dialogue_rounds: int = Field(15, env="MAX_COMPREHENSIVE_DIALOGUE_ROUNDS")
    comprehensive_review_timeout: int = Field(300, env="COMPREHENSIVE_REVIEW_TIMEOUT")  # 5 minutes
    comprehensive_tool_parallelism: int = Field(4, env="COMPREHENSIVE_TOOL_PARALLELISM")
    comprehensive_synthesis_model: str = Field("pro", env="COMPREHENSIVE_SYNTHESIS_MODEL")
    comprehensive_intent_model: str = Field("flash", env="COMPREHENSIVE_INTENT_MODEL")
    
    # Resilience and Streaming Configuration - NO MEMORY/SIZE RESTRICTIONS
    # Note: Restrictions removed after determining terminal freezes were CPU-related, not memory
    max_response_size_kb: int = Field(999999, env="MAX_RESPONSE_SIZE_KB")  # Effectively unlimited
    memory_limit_mb: int = Field(999999, env="MEMORY_LIMIT_MB")  # Effectively unlimited
    max_chunk_size_kb: int = Field(999999, env="MAX_CHUNK_SIZE_KB")  # Effectively unlimited
    review_timeout_seconds: int = Field(9999, env="REVIEW_TIMEOUT_SECONDS")  # Effectively unlimited
    
    # CPU Performance Configuration
    file_scan_yield_frequency: int = Field(50, env="FILE_SCAN_YIELD_FREQUENCY")  # Yield CPU every N files during directory scans
    processing_yield_interval_ms: int = Field(100, env="PROCESSING_YIELD_INTERVAL_MS")  # Yield every 100ms during heavy processing
    max_cpu_usage_percent: float = Field(80.0, env="MAX_CPU_USAGE_PERCENT")  # CPU usage threshold for throttling
    cpu_check_interval: int = Field(10, env="CPU_CHECK_INTERVAL")  # Check CPU usage every N operations
    max_concurrent_reviews: int = Field(4, env="MAX_CONCURRENT_REVIEWS")  # 4 per session, safe for multiple sessions
    enable_streaming_responses: bool = Field(True, env="ENABLE_STREAMING_RESPONSES")
    enable_large_response_mode: bool = Field(True, env="ENABLE_LARGE_RESPONSE_MODE")
    
    # Rate Limiting Configuration - Reasonable defaults for personal use
    enable_pre_blocking: bool = Field(False, env="ENABLE_PRE_BLOCKING")  # Disable aggressive pre-blocking
    max_block_minutes: float = Field(2.0, env="MAX_BLOCK_MINUTES")  # Maximum block time for RPM limits
    progressive_backoff_seconds: List[int] = Field([10, 30, 60], env="PROGRESSIVE_BACKOFF_SECONDS")  # Short delays before model fallback
    retry_other_key_first: bool = Field(True, env="RETRY_OTHER_KEY_FIRST")  # Try other API key before backing off
    enable_retry_after_header: bool = Field(True, env="ENABLE_RETRY_AFTER_HEADER")  # Use API response headers
    
    # File Paths (converted to absolute paths)
    logs_dir: str = str(PROJECT_ROOT / "logs")
    rate_limit_file: str = str(PROJECT_ROOT / "gemini_rate_limits.json")
    session_log_file: str = str(PROJECT_ROOT / "logs" / "dialogue_sessions.json")
    database_path: str = str(PROJECT_ROOT / "logs" / "sessions.db")
    
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
    
    @validator('validation_confidence_threshold')
    def validate_confidence_threshold(cls, v):
        """Validate confidence threshold is between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        return v
    
    @validator('file_scan_yield_frequency', 'processing_yield_interval_ms', 'cpu_check_interval')
    def validate_yield_frequency(cls, v):
        """Validate yield and CPU check frequencies are positive"""
        if v <= 0:
            raise ValueError("Yield frequency and CPU check interval must be positive")
        return v
    
    @validator('max_cpu_usage_percent')
    def validate_cpu_usage_threshold(cls, v):
        """Validate CPU usage threshold is between 10 and 100"""
        if not 10 <= v <= 100:
            raise ValueError("CPU usage threshold must be between 10.0 and 100.0 percent")
        return v
    
    @validator('file_cache_ttl_seconds', 'max_concurrent_file_reads', 
              'max_response_size_kb', 'memory_limit_mb', 'max_chunk_size_kb', 
              'review_timeout_seconds', 'max_concurrent_reviews',
              'ast_parsing_timeout', 'dependency_graph_depth_limit',
              'max_summary_nodes', 'max_summary_edges',
              'max_comprehensive_dialogue_rounds', 'comprehensive_review_timeout',
              'comprehensive_tool_parallelism')
    def validate_positive_integers(cls, v):
        """Validate positive integer values"""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v
    
    @validator('max_response_size_kb')
    def validate_response_size(cls, v):
        """No restrictions - allow any size"""
        # Removed all restrictions
        return v
    
    @validator('memory_limit_mb')
    def validate_memory_limit(cls, v):
        """No restrictions - allow any memory usage"""
        # Removed all restrictions
        return v
    
    @validator('test_mapping_strategy')
    def validate_test_mapping_strategy(cls, v):
        """Validate test mapping strategy"""
        valid_strategies = ['convention', 'directory', 'docstring']
        if v not in valid_strategies:
            raise ValueError(f"Invalid test mapping strategy. Must be one of: {valid_strategies}")
        return v
    
    @validator('coverage_complexity_threshold', 'coupling_threshold', 'high_impact_threshold')
    def validate_threshold_range(cls, v):
        """Validate threshold values are between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Threshold values must be between 0.0 and 1.0")
        return v
    
    @validator('breaking_change_sensitivity')
    def validate_breaking_change_sensitivity(cls, v):
        """Validate breaking change sensitivity level"""
        valid_levels = ['strict', 'balanced', 'lenient']
        if v not in valid_levels:
            raise ValueError(f"Invalid breaking change sensitivity. Must be one of: {valid_levels}")
        return v
    
    @validator('interface_priority_threshold')
    def validate_interface_priority_threshold(cls, v):
        """Validate interface priority threshold is between 1 and 10"""
        if not 1 <= v <= 10:
            raise ValueError("Interface priority threshold must be between 1.0 and 10.0")
        return v
    
    @validator('comprehensive_synthesis_model', 'comprehensive_intent_model')
    def validate_model_names(cls, v):
        """Validate model names are valid"""
        valid_models = ['pro', 'flash', 'flash-lite']
        if v not in valid_models:
            raise ValueError(f"Invalid model name. Must be one of: {valid_models}")
        return v
    
    @property
    def api_keys(self) -> List[str]:
        """Get list of valid API keys from secure storage"""
        # Try secure key manager first
        try:
            from .security import get_api_keys
            keys = get_api_keys()
            # Filter out literal Windows environment variable strings
            keys = [k for k in keys if k and not (k.startswith('%') and k.endswith('%'))]
            if keys:
                return keys
        except Exception as e:
            logging.debug(f"Failed to get keys from secure storage: {e}")
        
        # Fall back to environment variables
        keys = []
        if self.google_api_key and not (self.google_api_key.startswith('%') and self.google_api_key.endswith('%')):
            keys.append(self.google_api_key)
        if self.google_api_key2 and not (self.google_api_key2.startswith('%') and self.google_api_key2.endswith('%')):
            keys.append(self.google_api_key2)
        
        # If we only have literal strings, try reading from .env file
        if not keys:
            try:
                from pathlib import Path
                env_file = Path(__file__).parent.parent / '.env'
                if env_file.exists():
                    with open(env_file) as f:
                        for line in f:
                            if line.startswith('GOOGLE_API_KEY='):
                                key = line.split('=', 1)[1].strip()
                                if key and not (key.startswith('%') and key.endswith('%')):
                                    keys.append(key)
                            elif line.startswith('GOOGLE_API_KEY2='):
                                key = line.split('=', 1)[1].strip()
                                if key and not (key.startswith('%') and key.endswith('%')):
                                    keys.append(key)
            except:
                pass
        
        if not keys:
            raise ValueError("At least one API key (GOOGLE_API_KEY or GOOGLE_API_KEY2) is required")
        return keys
    
    @property
    def log_level_value(self) -> int:
        """Get logging level as integer value"""
        return getattr(logging, self.gemini_mcp_log_level, logging.INFO)
    
    @property
    def gemini_models(self) -> Dict[str, str]:
        """Gemini model configuration"""
        return {
            "pro": "gemini-2.5-pro",
            "flash": "gemini-2.5-flash", 
            "flash-lite": "gemini-2.5-flash-lite"
        }
    
    @property
    def complexity_indicators(self) -> List[str]:
        """Keywords that indicate code complexity"""
        return [
            'async', 'await', 'threading', 'multiprocessing',
            'security', 'authentication', 'crypto', 'encryption',
            'database', 'sql', 'transaction', 'migration',
            'api', 'microservice', 'distributed', 'scale',
            'performance', 'optimization', 'cache', 'redis',
            'docker', 'kubernetes', 'deployment', 'infrastructure',
            'documentation', 'readme', 'changelog', 'guide'
        ]
    
    @property
    def length_thresholds(self) -> Dict[str, int]:
        """Content length thresholds for complexity scoring"""
        return {
            'large': 2000,
            'medium': 1000
        }
    
    @property
    def complex_focus_areas(self) -> List[str]:
        """Focus areas that increase complexity score"""
        return ['security', 'architecture', 'all']
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables from other projects


# Global configuration instance
config = GeminiMCPConfig()

# Backward compatibility exports (deprecated - use config.property instead)
GOOGLE_API_KEY = config.google_api_key
GOOGLE_API_KEY2 = config.google_api_key2
GEMINI_REQUEST_TIMEOUT = config.gemini_request_timeout
GEMINI_CONNECT_TIMEOUT = config.gemini_connect_timeout
TIMEOUT_RETRY_COUNT = config.timeout_retry_count
GEMINI_MCP_LOG_LEVEL = config.gemini_mcp_log_level
LOG_LEVEL_VALUE = config.log_level_value
GEMINI_MODELS = config.gemini_models
COMPLEXITY_INDICATORS = config.complexity_indicators
LENGTH_THRESHOLDS = config.length_thresholds
COMPLEX_FOCUS_AREAS = config.complex_focus_areas
LOGS_DIR = config.logs_dir
RATE_LIMIT_FILE = config.rate_limit_file
SESSION_LOG_FILE = config.session_log_file
DATABASE_PATH = config.database_path
API_KEYS = config.api_keys
MAX_COMPREHENSIVE_DIALOGUE_ROUNDS = config.max_comprehensive_dialogue_rounds
COMPREHENSIVE_REVIEW_TIMEOUT = config.comprehensive_review_timeout
COMPREHENSIVE_TOOL_PARALLELISM = config.comprehensive_tool_parallelism

def validate_config():
    """Backward compatibility - validation is now done automatically"""
    return config.api_keys