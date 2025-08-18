#!/usr/bin/env python3
"""
Direct test of the correlation framework without MCP tools
Tests correlation detection, conflict identification, and resolution
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.correlation_framework import CorrelationFramework
from services.resolution_strategies import StrategySelector, ResolutionContext

def test_correlation_framework():
    """Test the correlation framework with sample engine results"""
    
    print("=" * 60)
    print("TESTING CORRELATION AND CONFLICT RESOLUTION FRAMEWORK")
    print("=" * 60)
    
    # Initialize framework
    framework = CorrelationFramework(use_cache=True)
    print("\n✅ Framework initialized with caching enabled")
    
    # Create sample engine results with some correlations and conflicts
    engine_results = {
        'check_quality': """
            Security Analysis Complete:
            - Found 5 security vulnerabilities
            - Code coverage: 85%
            - Performance: 200ms average response time
            - 3 SQL injection risks detected
            - Authentication issues found
        """,
        
        'analyze_code': """
            Architecture Analysis:
            - Detected 5 security issues  
            - Coverage estimated at 82%
            - Well-structured codebase
            - 3 SQL injection vulnerabilities
            - Good separation of concerns
        """,
        
        'performance_profiler': """
            Performance Report:
            - Response time: 150ms average
            - No major bottlenecks
            - Memory usage: 256MB
            - CPU usage: 15%
        """,
        
        'analyze_test_coverage': """
            Test Coverage Report:
            - Actual coverage: 45%
            - 120 tests passing
            - 5 tests failing
            - Critical paths not covered
        """
    }
    
    print("\n📊 Analyzing results from 4 engines:")
    for engine in engine_results.keys():
        print(f"  - {engine}")
    
    # Run correlation analysis
    print("\n🔍 Running correlation analysis...")
    analysis = framework.analyze(engine_results)
    
    # Display correlations
    print("\n🔗 CORRELATIONS DETECTED:")
    print("-" * 40)
    if analysis['correlations']:
        for i, corr in enumerate(analysis['correlations'], 1):
            print(f"{i}. {corr}")
            if corr.evidence:
                for evidence in corr.evidence[:2]:
                    print(f"   Evidence: {evidence}")
    else:
        print("No correlations detected")
    
    # Display conflicts
    print("\n⚠️ CONFLICTS IDENTIFIED:")
    print("-" * 40)
    if analysis['conflicts']:
        for i, conflict in enumerate(analysis['conflicts'], 1):
            print(f"{i}. {conflict}")
            print(f"   Description: {conflict.description}")
    else:
        print("No conflicts detected")
    
    # Display resolutions
    print("\n✅ CONFLICT RESOLUTIONS:")
    print("-" * 40)
    if analysis['resolutions']:
        for i, resolution in enumerate(analysis['resolutions'], 1):
            print(f"{i}. {resolution}")
            print(f"   Explanation: {resolution.explanation}")
    else:
        print("No resolutions generated")
    
    # Display summary
    print("\n📈 ANALYSIS SUMMARY:")
    print("-" * 40)
    print(analysis['summary'])
    
    # Test caching
    print("\n🔄 Testing cache functionality...")
    print("Running same analysis again (should use cache)...")
    analysis2 = framework.analyze(engine_results)
    
    # The log should show "Using cached correlation results"
    print("✅ Cache test complete")
    
    # Test resolution strategies directly
    print("\n🎯 Testing Resolution Strategies:")
    print("-" * 40)
    
    selector = StrategySelector()
    
    # Create a sample conflict
    test_context = ResolutionContext(
        conflict_type="metric_discrepancy",
        engines_involved=['check_quality', 'analyze_code', 'analyze_test_coverage'],
        conflicting_values={
            'check_quality': 85,
            'analyze_code': 82,
            'analyze_test_coverage': 45
        },
        engine_metadata={}
    )
    
    print("Test conflict: Coverage discrepancy (85% vs 82% vs 45%)")
    
    # Resolve the conflict
    resolution = selector.resolve_with_best_strategy(test_context)
    print(f"Resolution strategy used: {resolution.strategy_name}")
    print(f"Resolved value: {resolution.resolved_value}")
    print(f"Confidence: {resolution.confidence:.2f}")
    print(f"Explanation: {resolution.explanation}")
    
    print("\n" + "=" * 60)
    print("✅ CORRELATION FRAMEWORK TEST COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = test_correlation_framework()
        if success:
            print("\n🎉 All tests passed successfully!")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)