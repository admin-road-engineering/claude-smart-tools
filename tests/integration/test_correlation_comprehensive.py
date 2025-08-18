#!/usr/bin/env python3
"""
Comprehensive test of correlation framework features
Demonstrates all correlation types, conflict types, and resolution strategies
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.correlation_framework import CorrelationFramework, CorrelationType
from services.resolution_strategies import (
    StrategySelector, ResolutionContext,
    ConsensusStrategy, ExpertWeightingStrategy, 
    ConfidenceBasedStrategy, HierarchicalStrategy
)
from services.correlation_cache import get_correlation_cache

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)

def test_correlation_types():
    """Test different types of correlations"""
    print_section("TESTING CORRELATION TYPES")
    
    framework = CorrelationFramework(use_cache=False)
    
    # Test 1: Confirming results
    print("\n1️⃣ Testing CONFIRMING correlations:")
    confirming_results = {
        'engine1': "Found 5 security vulnerabilities: SQL injection, XSS, CSRF",
        'engine2': "Detected 5 security issues including SQL injection and XSS attacks"
    }
    
    analysis = framework.analyze(confirming_results)
    for corr in analysis['correlations']:
        if corr.correlation_type == CorrelationType.CONFIRMS:
            print(f"   ✅ {corr}")
    
    # Test 2: Contradicting results
    print("\n2️⃣ Testing CONTRADICTING correlations:")
    contradicting_results = {
        'engine1': "No security issues found. Code is secure.",
        'engine2': "Critical vulnerabilities detected! Multiple security issues found."
    }
    
    analysis = framework.analyze(contradicting_results)
    for corr in analysis['correlations']:
        if corr.correlation_type == CorrelationType.CONTRADICTS:
            print(f"   ⚠️ {corr}")
    
    # Test 3: Complementary results
    print("\n3️⃣ Testing COMPLEMENTARY correlations:")
    complementary_results = {
        'performance_profiler': "Response time: 200ms, CPU usage: 45%",
        'memory_analyzer': "Memory usage: 512MB, No memory leaks detected"
    }
    
    analysis = framework.analyze(complementary_results)
    for corr in analysis['correlations']:
        if corr.correlation_type == CorrelationType.COMPLEMENTS:
            print(f"   🔄 {corr}")

def test_conflict_types():
    """Test different types of conflicts"""
    print_section("TESTING CONFLICT TYPES")
    
    framework = CorrelationFramework(use_cache=False)
    
    # Test metric discrepancies
    print("\n1️⃣ Metric Discrepancy Conflicts:")
    metric_conflict_results = {
        'coverage_tool1': "Code coverage: 85%",
        'coverage_tool2': "Test coverage: 45%", 
        'coverage_tool3': "Coverage analysis: 92%"
    }
    
    analysis = framework.analyze(metric_conflict_results)
    for conflict in analysis['conflicts']:
        if conflict.conflict_type == "metric_discrepancy":
            print(f"   📊 {conflict}")
            print(f"      Values: {conflict.conflicting_findings}")
    
    # Test contradictory findings
    print("\n2️⃣ Contradictory Results Conflicts:")
    contradictory_results = {
        'security_scanner': "No vulnerabilities found",
        'code_analyzer': "5 critical security vulnerabilities detected"
    }
    
    analysis = framework.analyze(contradictory_results)
    for conflict in analysis['conflicts']:
        print(f"   ⚔️ {conflict}")

def test_resolution_strategies():
    """Test all resolution strategies"""
    print_section("TESTING RESOLUTION STRATEGIES")
    
    # Test data
    test_context = ResolutionContext(
        conflict_type="metric_discrepancy",
        engines_involved=['check_quality', 'analyze_code', 'analyze_test_coverage'],
        conflicting_values={
            'check_quality': "85% coverage with high confidence",
            'analyze_code': "82% coverage estimated",
            'analyze_test_coverage': "45% actual coverage measured"
        },
        engine_metadata={
            'check_quality': {'confidence': 0.9},
            'analyze_code': {'confidence': 0.7},
            'analyze_test_coverage': {'confidence': 0.95}
        }
    )
    
    # Test each strategy
    strategies = [
        ConsensusStrategy(),
        ExpertWeightingStrategy(),
        ConfidenceBasedStrategy(),
        HierarchicalStrategy()
    ]
    
    for strategy in strategies:
        print(f"\n🎯 Testing {strategy.__class__.__name__}:")
        if strategy.can_resolve(test_context):
            resolution = strategy.resolve(test_context)
            print(f"   Strategy: {resolution.strategy_name}")
            print(f"   Confidence: {resolution.confidence:.2f}")
            print(f"   Supporting: {', '.join(resolution.supporting_engines)}")
            print(f"   Explanation: {resolution.explanation}")
        else:
            print(f"   Cannot resolve this conflict type")

def test_caching():
    """Test caching functionality"""
    print_section("TESTING CACHING MECHANISM")
    
    # Get cache instance
    cache = get_correlation_cache()
    cache.clear()  # Start fresh
    
    framework = CorrelationFramework(use_cache=True)
    
    # Test data
    test_results = {
        'engine1': "Test result 1 with some findings",
        'engine2': "Test result 2 with other findings"
    }
    
    print("\n1️⃣ First analysis (should compute):")
    analysis1 = framework.analyze(test_results)
    print(f"   Correlations found: {len(analysis1['correlations'])}")
    
    print("\n2️⃣ Second analysis (should use cache):")
    analysis2 = framework.analyze(test_results)
    print(f"   Correlations found: {len(analysis2['correlations'])}")
    
    # Check cache stats
    stats = cache.get_stats()
    print("\n📊 Cache Statistics:")
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Total hits: {stats['total_hits']}")
    print(f"   TTL: {stats['ttl_seconds']} seconds")

def test_confidence_scoring():
    """Test the formalized confidence scoring algorithm"""
    print_section("TESTING CONFIDENCE SCORING")
    
    framework = CorrelationFramework(use_cache=False)
    
    # Create test results with varying quality
    test_results = {
        'high_quality': {
            'findings': ['issue1', 'issue2', 'issue3'],
            'metrics': {'coverage': 85, 'errors': 5},
            'summary': 'Detailed analysis found 3 issues with 85% coverage\n' * 50
        },
        'medium_quality': "Found some issues with moderate detail",
        'low_quality': "Brief result"
    }
    
    # Create a conflict to trigger confidence scoring
    print("\n📊 Testing multi-factor confidence calculation:")
    
    # The framework will calculate confidence internally
    analysis = framework.analyze(test_results)
    
    print("\nFactors considered in confidence scoring:")
    print("  1. Result completeness (30% weight)")
    print("  2. Result structure (20% weight)")
    print("  3. Findings present (20% weight)")
    print("  4. Metrics present (15% weight)")
    print("  5. Engine reliability (15% weight)")
    
    if analysis['resolutions']:
        for resolution in analysis['resolutions']:
            print(f"\n✅ Resolution confidence: {resolution.confidence:.2f}")
            print(f"   Strategy: {resolution.strategy_used}")

def run_all_tests():
    """Run all comprehensive tests"""
    print("\n" + "🚀" * 30)
    print("  COMPREHENSIVE CORRELATION FRAMEWORK TEST SUITE")
    print("🚀" * 30)
    
    try:
        test_correlation_types()
        test_conflict_types()
        test_resolution_strategies()
        test_caching()
        test_confidence_scoring()
        
        print_section("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)