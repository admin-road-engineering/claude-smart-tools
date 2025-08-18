"""
Unit tests for the Cross-Engine Correlation and Conflict Resolution Framework
"""
import pytest
import asyncio
from typing import Dict, Any
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.correlation_framework import (
    CorrelationFramework,
    CorrelationType,
    CorrelationStrength,
    ConflictSeverity,
    Correlation,
    Conflict,
    Resolution
)
from services.resolution_strategies import (
    ConsensusStrategy,
    ExpertWeightingStrategy,
    ConfidenceBasedStrategy,
    HierarchicalStrategy,
    ManualReviewStrategy,
    CompositeStrategy,
    ResolutionContext,
    StrategySelector
)


class TestCorrelationFramework:
    """Test the correlation framework functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.framework = CorrelationFramework()
    
    def test_initialization(self):
        """Test framework initialization"""
        assert self.framework.correlations == []
        assert self.framework.conflicts == []
        assert self.framework.resolutions == []
        assert self.framework.similarity_threshold == 0.3
    
    def test_extract_patterns(self):
        """Test pattern extraction from engine results"""
        engine_results = {
            'check_quality': "Found 5 security vulnerabilities and 3 performance issues",
            'analyze_code': {"issues": ["memory leak", "sql injection"], "metrics": {"complexity": 15}}
        }
        
        patterns = self.framework._extract_patterns(engine_results)
        
        assert 'check_quality' in patterns
        assert 'analyze_code' in patterns
        assert 'text_content' in patterns['check_quality']
        assert 'categories' in patterns['check_quality']
    
    def test_extract_metrics(self):
        """Test metric extraction from text"""
        result = "Code coverage: 85.5% with 100ms response time and 2 errors"
        metrics = self.framework._extract_metrics(result)
        
        assert 'coverage' in metrics
        assert metrics['coverage'] == 85.5
        assert 'performance' in metrics
        assert metrics['performance'] == 100
        assert 'errors' in metrics
        assert metrics['errors'] == 2
    
    def test_categorize_content(self):
        """Test content categorization"""
        result = "Security vulnerability found: SQL injection in authentication module"
        categories = self.framework._categorize_content(result)
        
        assert 'security' in categories
    
    def test_calculate_similarity(self):
        """Test similarity calculation between patterns"""
        pattern1 = {
            'text_content': 'security vulnerability found',
            'categories': {'security', 'quality'},
            'metrics': {'errors': 5},
            'findings': ['sql injection', 'xss']
        }
        
        pattern2 = {
            'text_content': 'security issue detected',
            'categories': {'security', 'testing'},
            'metrics': {'errors': 4},
            'findings': ['sql injection', 'csrf']
        }
        
        similarity = self.framework._calculate_similarity(pattern1, pattern2)
        
        assert similarity > 0.3  # Should detect some similarity
        assert similarity < 1.0  # Not identical
    
    def test_detect_correlations(self):
        """Test correlation detection between engine results"""
        patterns = {
            'engine1': {
                'text_content': 'found security issues',
                'categories': {'security'},
                'metrics': {'vulnerabilities': 3},
                'findings': ['sql injection'],
                'recommendations': []
            },
            'engine2': {
                'text_content': 'detected security problems',
                'categories': {'security'},
                'metrics': {'vulnerabilities': 3},
                'findings': ['sql injection'],
                'recommendations': []
            }
        }
        
        correlations = self.framework._detect_correlations(patterns)
        
        assert len(correlations) > 0
        correlation = correlations[0]
        assert correlation.correlation_type in [CorrelationType.CONFIRMS, CorrelationType.OVERLAPS]
    
    def test_identify_conflicts(self):
        """Test conflict identification"""
        patterns = {
            'engine1': {
                'metrics': {'coverage': 85},
                'findings': [],
                'recommendations': [],
                'categories': set(),
                'text_content': 'good coverage'
            },
            'engine2': {
                'metrics': {'coverage': 45},
                'findings': [],
                'recommendations': [],
                'categories': set(),
                'text_content': 'poor coverage'
            }
        }
        
        correlations = []
        conflicts = self.framework._identify_conflicts(patterns, correlations)
        
        assert len(conflicts) > 0
        conflict = conflicts[0]
        assert conflict.conflict_type == "metric_discrepancy"
    
    def test_full_analysis(self):
        """Test complete analysis workflow"""
        engine_results = {
            'check_quality': "Found 5 security vulnerabilities with 80% code coverage",
            'analyze_code': "Detected 5 security issues with 82% coverage",
            'performance_profiler': "Response time: 200ms, no performance issues"
        }
        
        analysis = self.framework.analyze(engine_results)
        
        assert 'correlations' in analysis
        assert 'conflicts' in analysis
        assert 'resolutions' in analysis
        assert 'summary' in analysis


class TestResolutionStrategies:
    """Test resolution strategies"""
    
    def test_consensus_strategy(self):
        """Test consensus-based resolution"""
        strategy = ConsensusStrategy()
        context = ResolutionContext(
            conflict_type="metric_discrepancy",
            engines_involved=['engine1', 'engine2', 'engine3'],
            conflicting_values={
                'engine1': 85,
                'engine2': 83,
                'engine3': 50
            },
            engine_metadata={}
        )
        
        assert strategy.can_resolve(context)
        result = strategy.resolve(context)
        
        assert result.strategy_name == "ConsensusStrategy"
        # Should pick the value that appears most similar (85 or 83)
        assert result.resolved_value in [85, 83]
    
    def test_expert_weighting_strategy(self):
        """Test expertise-based resolution"""
        strategy = ExpertWeightingStrategy()
        context = ResolutionContext(
            conflict_type="security_vulnerability",
            engines_involved=['check_quality', 'analyze_code'],
            conflicting_values={
                'check_quality': "5 vulnerabilities",
                'analyze_code': "3 vulnerabilities"
            },
            engine_metadata={}
        )
        
        assert strategy.can_resolve(context)
        result = strategy.resolve(context)
        
        assert result.strategy_name == "ExpertWeightingStrategy"
        # check_quality should be preferred for security
        assert 'check_quality' in result.supporting_engines
    
    def test_confidence_based_strategy(self):
        """Test confidence-based resolution"""
        strategy = ConfidenceBasedStrategy()
        context = ResolutionContext(
            conflict_type="general",
            engines_involved=['engine1', 'engine2'],
            conflicting_values={
                'engine1': "result1",
                'engine2': "result2"
            },
            engine_metadata={
                'engine1': {'confidence': 0.9},
                'engine2': {'confidence': 0.6}
            }
        )
        
        assert strategy.can_resolve(context)
        result = strategy.resolve(context)
        
        assert result.strategy_name == "ConfidenceBasedStrategy"
        assert result.resolved_value == "result1"  # Higher confidence
    
    def test_hierarchical_strategy(self):
        """Test hierarchy-based resolution"""
        strategy = HierarchicalStrategy()
        context = ResolutionContext(
            conflict_type="general",
            engines_involved=['search_code', 'check_quality', 'analyze_code'],
            conflicting_values={
                'search_code': "result1",
                'check_quality': "result2",
                'analyze_code': "result3"
            },
            engine_metadata={}
        )
        
        assert strategy.can_resolve(context)
        result = strategy.resolve(context)
        
        assert result.strategy_name == "HierarchicalStrategy"
        # check_quality has higher priority than search_code
        assert result.resolved_value == "result2"
    
    def test_manual_review_strategy(self):
        """Test manual review fallback"""
        strategy = ManualReviewStrategy()
        context = ResolutionContext(
            conflict_type="complex",
            engines_involved=['engine1', 'engine2'],
            conflicting_values={
                'engine1': "result1",
                'engine2': "result2"
            },
            engine_metadata={}
        )
        
        assert strategy.can_resolve(context)  # Always available
        result = strategy.resolve(context)
        
        assert result.strategy_name == "ManualReviewStrategy"
        assert result.confidence == 0.0  # Indicates manual review needed
        assert isinstance(result.resolved_value, dict)
        assert 'recommendation' in result.resolved_value
    
    def test_strategy_selector(self):
        """Test strategy selection logic"""
        selector = StrategySelector()
        
        # Test metric discrepancy selection
        context = ResolutionContext(
            conflict_type="metric_discrepancy",
            engines_involved=['engine1', 'engine2', 'engine3'],
            conflicting_values={'engine1': 1, 'engine2': 2, 'engine3': 3},
            engine_metadata={}
        )
        
        strategy = selector.select_strategy(context)
        assert strategy.__class__.__name__ in ['ConsensusStrategy', 'ExpertWeightingStrategy', 
                                               'ConfidenceBasedStrategy']
        
        # Test resolution with best strategy
        result = selector.resolve_with_best_strategy(context)
        assert result.strategy_name is not None
        assert result.resolved_value is not None


class TestCorrelationTypes:
    """Test correlation type detection"""
    
    def setup_method(self):
        self.framework = CorrelationFramework()
    
    def test_contradiction_detection(self):
        """Test detection of contradictory results"""
        pattern1 = {
            'text_content': 'no issues found',
            'metrics': {'errors': 0},
            'findings': [],
            'recommendations': [],
            'categories': set()
        }
        
        pattern2 = {
            'text_content': 'multiple issues found',
            'metrics': {'errors': 10},
            'findings': ['error1', 'error2'],
            'recommendations': [],
            'categories': set()
        }
        
        has_contradiction = self.framework._has_contradiction(pattern1, pattern2)
        assert has_contradiction
    
    def test_confirmation_detection(self):
        """Test detection of confirming results"""
        pattern1 = {
            'text_content': 'found 5 security issues',
            'metrics': {'vulnerabilities': 5},
            'findings': ['sql injection', 'xss', 'csrf'],
            'recommendations': [],
            'categories': {'security'}
        }
        
        pattern2 = {
            'text_content': 'detected 5 security vulnerabilities',
            'metrics': {'vulnerabilities': 5},
            'findings': ['sql injection', 'xss', 'csrf'],
            'recommendations': [],
            'categories': {'security'}
        }
        
        has_confirmation = self.framework._has_confirmation(pattern1, pattern2)
        assert has_confirmation


class TestIntegration:
    """Integration tests for correlation and resolution"""
    
    def test_end_to_end_correlation_resolution(self):
        """Test complete correlation and resolution workflow"""
        framework = CorrelationFramework()
        
        # Simulate multiple engine results with conflicts
        engine_results = {
            'check_quality': {
                'summary': 'Found 10 security issues, 85% code coverage',
                'metrics': {'coverage': 85, 'issues': 10}
            },
            'analyze_code': {
                'summary': 'Found 5 quality issues, 82% coverage estimated',
                'metrics': {'coverage': 82, 'issues': 5}
            },
            'analyze_test_coverage': {
                'summary': 'Actual coverage is 45%',
                'metrics': {'coverage': 45}
            }
        }
        
        # Analyze correlations and conflicts
        analysis = framework.analyze(engine_results)
        
        # Verify analysis results
        assert len(analysis['correlations']) > 0
        assert len(analysis['conflicts']) > 0  # Should detect coverage conflict
        assert len(analysis['resolutions']) > 0  # Should resolve conflicts
        
        # Check that summary is generated
        assert 'summary' in analysis
        assert len(analysis['summary']) > 0
        
        # Verify conflict resolution
        for resolution in analysis['resolutions']:
            assert resolution.strategy_used is not None
            assert resolution.confidence >= 0.0
            assert resolution.explanation is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])