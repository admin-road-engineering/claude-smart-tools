"""
Configuration for Cross-Engine Correlation and Conflict Resolution Framework
"""
import os
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis"""
    
    # Enable/disable correlation analysis
    enable_correlation: bool = True
    
    # Correlation detection thresholds
    similarity_threshold: float = 0.3
    strong_correlation_threshold: float = 0.8
    moderate_correlation_threshold: float = 0.5
    weak_correlation_threshold: float = 0.3
    
    # Conflict detection settings
    metric_discrepancy_threshold: float = 0.3  # 30% difference triggers conflict
    enable_recommendation_conflict_detection: bool = True
    enable_metric_conflict_detection: bool = True
    
    # Resolution strategy preferences
    preferred_strategies: List[str] = None  # Use default if None
    fallback_strategy: str = "manual"
    
    # Engine expertise weights for different domains
    engine_expertise: Dict[str, Dict[str, float]] = None
    
    # Display settings
    max_correlations_to_display: int = 5
    max_conflicts_to_display: int = 3
    max_resolutions_to_display: int = 3
    
    # Performance settings
    enable_correlation_caching: bool = True
    correlation_cache_ttl: int = 300  # seconds
    max_engines_for_correlation: int = 10
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.preferred_strategies is None:
            self.preferred_strategies = [
                'composite',
                'expert',
                'consensus',
                'confidence',
                'hierarchy'
            ]
        
        if self.engine_expertise is None:
            self.engine_expertise = self._get_default_expertise()
    
    def _get_default_expertise(self) -> Dict[str, Dict[str, float]]:
        """Get default engine expertise matrix"""
        return {
            'check_quality': {
                'security': 0.95,
                'performance': 0.85,
                'quality': 0.90,
                'testing': 0.70,
                'architecture': 0.60,
                'database': 0.40,
                'api': 0.50,
                'dependencies': 0.50
            },
            'analyze_code': {
                'architecture': 0.95,
                'quality': 0.80,
                'dependencies': 0.85,
                'security': 0.60,
                'performance': 0.50,
                'database': 0.40,
                'api': 0.50,
                'testing': 0.60
            },
            'performance_profiler': {
                'performance': 1.0,
                'optimization': 0.95,
                'bottlenecks': 0.90,
                'quality': 0.40,
                'security': 0.30,
                'architecture': 0.50,
                'database': 0.60,
                'api': 0.40
            },
            'analyze_test_coverage': {
                'testing': 1.0,
                'quality': 0.85,
                'coverage': 0.95,
                'architecture': 0.40,
                'security': 0.50,
                'performance': 0.30,
                'database': 0.30,
                'api': 0.40
            },
            'config_validator': {
                'configuration': 0.95,
                'security': 0.85,
                'deployment': 0.80,
                'quality': 0.60,
                'performance': 0.50,
                'architecture': 0.50,
                'database': 0.40,
                'api': 0.40
            },
            'analyze_database': {
                'database': 0.95,
                'schema': 0.90,
                'optimization': 0.85,
                'architecture': 0.70,
                'security': 0.60,
                'performance': 0.70,
                'quality': 0.50,
                'api': 0.40
            },
            'api_contract_checker': {
                'api': 0.95,
                'contracts': 0.90,
                'integration': 0.85,
                'architecture': 0.70,
                'quality': 0.65,
                'security': 0.60,
                'performance': 0.50,
                'database': 0.40
            },
            'map_dependencies': {
                'dependencies': 0.95,
                'architecture': 0.85,
                'coupling': 0.90,
                'quality': 0.70,
                'security': 0.50,
                'performance': 0.40,
                'database': 0.40,
                'api': 0.50
            },
            'interface_inconsistency_detector': {
                'consistency': 0.95,
                'interfaces': 0.90,
                'quality': 0.85,
                'architecture': 0.75,
                'testing': 0.60,
                'security': 0.40,
                'performance': 0.30,
                'database': 0.30
            },
            'analyze_logs': {
                'debugging': 0.90,
                'performance': 0.70,
                'errors': 0.85,
                'security': 0.60,
                'quality': 0.50,
                'architecture': 0.40,
                'database': 0.50,
                'api': 0.50
            },
            'search_code': {
                'patterns': 0.85,
                'quality': 0.60,
                'architecture': 0.50,
                'security': 0.50,
                'performance': 0.40,
                'testing': 0.50,
                'database': 0.40,
                'api': 0.40
            },
            'analyze_docs': {
                'documentation': 0.95,
                'architecture': 0.70,
                'quality': 0.60,
                'api': 0.65,
                'security': 0.40,
                'performance': 0.30,
                'database': 0.40,
                'testing': 0.40
            }
        }
    
    @classmethod
    def from_env(cls) -> 'CorrelationConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Override from environment if available
        if os.environ.get('ENABLE_CORRELATION_ANALYSIS'):
            config.enable_correlation = os.environ.get('ENABLE_CORRELATION_ANALYSIS', 'true').lower() == 'true'
        
        if os.environ.get('CORRELATION_SIMILARITY_THRESHOLD'):
            try:
                config.similarity_threshold = float(os.environ['CORRELATION_SIMILARITY_THRESHOLD'])
            except ValueError:
                pass
        
        if os.environ.get('CORRELATION_STRONG_THRESHOLD'):
            try:
                config.strong_correlation_threshold = float(os.environ['CORRELATION_STRONG_THRESHOLD'])
            except ValueError:
                pass
        
        if os.environ.get('CORRELATION_MODERATE_THRESHOLD'):
            try:
                config.moderate_correlation_threshold = float(os.environ['CORRELATION_MODERATE_THRESHOLD'])
            except ValueError:
                pass
        
        if os.environ.get('METRIC_DISCREPANCY_THRESHOLD'):
            try:
                config.metric_discrepancy_threshold = float(os.environ['METRIC_DISCREPANCY_THRESHOLD'])
            except ValueError:
                pass
        
        if os.environ.get('MAX_CORRELATIONS_DISPLAY'):
            try:
                config.max_correlations_to_display = int(os.environ['MAX_CORRELATIONS_DISPLAY'])
            except ValueError:
                pass
        
        if os.environ.get('CORRELATION_CACHE_TTL'):
            try:
                config.correlation_cache_ttl = int(os.environ['CORRELATION_CACHE_TTL'])
            except ValueError:
                pass
        
        if os.environ.get('PREFERRED_RESOLUTION_STRATEGIES'):
            strategies = os.environ['PREFERRED_RESOLUTION_STRATEGIES'].split(',')
            config.preferred_strategies = [s.strip() for s in strategies]
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'enable_correlation': self.enable_correlation,
            'similarity_threshold': self.similarity_threshold,
            'strong_correlation_threshold': self.strong_correlation_threshold,
            'moderate_correlation_threshold': self.moderate_correlation_threshold,
            'weak_correlation_threshold': self.weak_correlation_threshold,
            'metric_discrepancy_threshold': self.metric_discrepancy_threshold,
            'enable_recommendation_conflict_detection': self.enable_recommendation_conflict_detection,
            'enable_metric_conflict_detection': self.enable_metric_conflict_detection,
            'preferred_strategies': self.preferred_strategies,
            'fallback_strategy': self.fallback_strategy,
            'max_correlations_to_display': self.max_correlations_to_display,
            'max_conflicts_to_display': self.max_conflicts_to_display,
            'max_resolutions_to_display': self.max_resolutions_to_display,
            'enable_correlation_caching': self.enable_correlation_caching,
            'correlation_cache_ttl': self.correlation_cache_ttl,
            'max_engines_for_correlation': self.max_engines_for_correlation
        }


# Global configuration instance
_global_config: CorrelationConfig = None


def get_correlation_config() -> CorrelationConfig:
    """Get the global correlation configuration"""
    global _global_config
    if _global_config is None:
        _global_config = CorrelationConfig.from_env()
    return _global_config


def set_correlation_config(config: CorrelationConfig):
    """Set the global correlation configuration"""
    global _global_config
    _global_config = config


def reset_correlation_config():
    """Reset the global configuration to defaults"""
    global _global_config
    _global_config = CorrelationConfig.from_env()