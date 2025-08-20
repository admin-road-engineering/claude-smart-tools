"""
Performance Profiler Tool for Gemini MCP System
Captures timing metrics, memory usage patterns, and identifies bottlenecks
Following Tool-as-a-Service pattern established by File Freshness Guardian
"""
import asyncio
import time
import psutil
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class OperationMetrics:
    """Metrics for a single operation"""
    operation_name: str
    start_time: float
    end_time: float
    duration_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    trace_id: Optional[str] = None
    model_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

@dataclass
class PerformanceProfile:
    """Complete performance profile for analysis session"""
    profile_id: str
    timestamp: datetime
    total_duration_ms: float
    operations: List[OperationMetrics]
    bottlenecks: List[Dict[str, Any]]
    memory_profile: Dict[str, float]
    recommendations: List[str]
    summary: str

class PerformanceProfiler:
    """
    Performance profiling service for Gemini MCP operations
    Tracks timing, memory usage, and identifies optimization opportunities
    """
    
    def __init__(self, 
                 logs_dir: str = "logs/performance",
                 bottleneck_duration_ms: float = 1000,
                 bottleneck_percentage: float = 30,
                 memory_high_mb: float = 500,
                 memory_large_mb: float = 100):
        """
        Initialize performance profiler with storage directory and thresholds
        
        Args:
            logs_dir: Directory to store profile logs
            bottleneck_duration_ms: Operations longer than this are bottlenecks (default 1000ms)
            bottleneck_percentage: Operations taking more than this % of total time are bottlenecks (default 30%)
            memory_high_mb: Total memory allocation above this triggers recommendation (default 500MB)
            memory_large_mb: Single allocation above this triggers recommendation (default 100MB)
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.current_profile: List[OperationMetrics] = []
        self.profile_start_time: Optional[float] = None
        self.process = psutil.Process()
        
        # Configurable thresholds
        self.bottleneck_duration_ms = bottleneck_duration_ms
        self.bottleneck_percentage = bottleneck_percentage
        self.memory_high_mb = memory_high_mb
        self.memory_large_mb = memory_large_mb
        
        # Operation aggregation for multiple calls to same operation
        self.operation_stats: Dict[str, Dict[str, Any]] = {}
        
    async def start_profiling(self, session_id: Optional[str] = None) -> str:
        """Start a new profiling session"""
        self.profile_start_time = time.time()
        self.current_profile = []
        self.operation_stats = {}  # Reset aggregation stats
        profile_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"Started performance profiling session: {profile_id}")
        return profile_id
        
    async def capture_operation(self, 
                               operation_name: str,
                               operation_func,
                               trace_id: Optional[str] = None,
                               model_used: Optional[str] = None) -> Tuple[Any, OperationMetrics]:
        """
        Capture metrics for a single operation
        
        Args:
            operation_name: Name of the operation being profiled
            operation_func: Async function to execute and profile
            trace_id: Optional trace ID for request correlation
            model_used: Optional Gemini model used
            
        Returns:
            Tuple of (operation result, metrics)
        """
        # Capture initial state
        memory_before = self.process.memory_info().rss / 1024 / 1024  # MB
        start_time = time.time()
        
        # Execute operation
        success = True
        error = None
        result = None
        try:
            result = await operation_func()
        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"Operation {operation_name} failed: {e}")
            
        # Capture final state
        end_time = time.time()
        memory_after = self.process.memory_info().rss / 1024 / 1024  # MB
        duration_ms = (end_time - start_time) * 1000
        
        # Create metrics
        metrics = OperationMetrics(
            operation_name=operation_name,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_delta_mb=memory_after - memory_before,
            trace_id=trace_id,
            model_used=model_used,
            success=success,
            error=error
        )
        
        self.current_profile.append(metrics)
        
        # Update aggregation statistics
        if operation_name not in self.operation_stats:
            self.operation_stats[operation_name] = {
                "count": 0,
                "total_duration_ms": 0,
                "min_duration_ms": float('inf'),
                "max_duration_ms": 0,
                "avg_duration_ms": 0,
                "total_memory_delta_mb": 0
            }
        
        stats = self.operation_stats[operation_name]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)
        stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)
        stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
        stats["total_memory_delta_mb"] += metrics.memory_delta_mb
        
        logger.debug(f"Captured metrics for {operation_name}: {duration_ms:.2f}ms, "
                    f"Memory: {memory_before:.1f}MB -> {memory_after:.1f}MB "
                    f"(#{stats['count']} avg: {stats['avg_duration_ms']:.2f}ms)")
        
        return result, metrics
        
    async def analyze_profile(self, profile_id: str) -> PerformanceProfile:
        """
        Analyze captured metrics and generate performance profile
        
        Args:
            profile_id: ID of the profiling session
            
        Returns:
            Complete performance profile with analysis
        """
        if not self.current_profile:
            raise ValueError("No metrics captured in current profile")
            
        # Calculate total duration
        total_duration_ms = (time.time() - self.profile_start_time) * 1000
        
        # Identify bottlenecks using configurable thresholds
        bottlenecks = []
        for op in self.current_profile:
            if op.duration_ms > self.bottleneck_duration_ms or \
               op.duration_ms / total_duration_ms > (self.bottleneck_percentage / 100):
                bottlenecks.append({
                    "operation": op.operation_name,
                    "duration_ms": op.duration_ms,
                    "percentage": (op.duration_ms / total_duration_ms) * 100,
                    "memory_impact_mb": op.memory_delta_mb
                })
                
        # Sort bottlenecks by duration
        bottlenecks.sort(key=lambda x: x["duration_ms"], reverse=True)
        
        # Memory profile
        memory_profile = {
            "initial_mb": self.current_profile[0].memory_before_mb if self.current_profile else 0,
            "peak_mb": max(op.memory_after_mb for op in self.current_profile),
            "final_mb": self.current_profile[-1].memory_after_mb if self.current_profile else 0,
            "total_allocated_mb": sum(max(0, op.memory_delta_mb) for op in self.current_profile),
            "largest_allocation_mb": max(op.memory_delta_mb for op in self.current_profile)
        }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(bottlenecks, memory_profile)
        
        # Add aggregation statistics to recommendations if there are repeated operations
        if self.operation_stats:
            for op_name, stats in self.operation_stats.items():
                if stats["count"] > 1:
                    recommendations.append(
                        f"📊 '{op_name}' called {stats['count']} times: "
                        f"avg {stats['avg_duration_ms']:.0f}ms, "
                        f"min {stats['min_duration_ms']:.0f}ms, "
                        f"max {stats['max_duration_ms']:.0f}ms"
                    )
        
        # Generate summary
        summary = self._generate_summary(total_duration_ms, bottlenecks, memory_profile)
        
        # Create profile
        profile = PerformanceProfile(
            profile_id=profile_id,
            timestamp=datetime.now(),
            total_duration_ms=total_duration_ms,
            operations=self.current_profile,
            bottlenecks=bottlenecks,
            memory_profile=memory_profile,
            recommendations=recommendations,
            summary=summary
        )
        
        # Save profile
        await self._save_profile(profile)
        
        return profile
        
    def _generate_recommendations(self, 
                                 bottlenecks: List[Dict],
                                 memory_profile: Dict[str, float]) -> List[str]:
        """Generate actionable performance recommendations"""
        recommendations = []
        
        # Bottleneck recommendations
        if bottlenecks:
            top_bottleneck = bottlenecks[0]
            if "file" in top_bottleneck["operation"].lower():
                recommendations.append(
                    f"🔧 File operations consuming {top_bottleneck['duration_ms']:.0f}ms. "
                    "Consider batching file reads or implementing parallel I/O."
                )
            elif "gemini" in top_bottleneck["operation"].lower() or "api" in top_bottleneck["operation"].lower():
                recommendations.append(
                    f"🌐 API calls taking {top_bottleneck['duration_ms']:.0f}ms. "
                    "Consider caching responses or using lighter models for simple tasks."
                )
            else:
                recommendations.append(
                    f"⚡ {top_bottleneck['operation']} is the primary bottleneck "
                    f"({top_bottleneck['percentage']:.1f}% of total time). Focus optimization here."
                )
                
        # Memory recommendations using configurable thresholds
        if memory_profile["total_allocated_mb"] > self.memory_high_mb:
            recommendations.append(
                f"💾 High memory allocation detected ({memory_profile['total_allocated_mb']:.0f}MB). "
                "Consider streaming large responses or processing in chunks."
            )
            
        if memory_profile["largest_allocation_mb"] > self.memory_large_mb:
            recommendations.append(
                f"🔍 Large single allocation ({memory_profile['largest_allocation_mb']:.0f}MB). "
                "Review data structures and consider lazy loading."
            )
            
        # Response time recommendations
        total_duration_s = sum(op.duration_ms for op in self.current_profile) / 1000
        if total_duration_s > 5:
            recommendations.append(
                f"⏱️ Total operation time exceeds 5 seconds ({total_duration_s:.1f}s). "
                "Consider implementing progress indicators and async processing."
            )
            
        # Model selection recommendations
        model_usage = {}
        for op in self.current_profile:
            if op.model_used:
                model_usage[op.model_used] = model_usage.get(op.model_used, 0) + op.duration_ms
                
        if model_usage:
            most_used = max(model_usage, key=model_usage.get)
            if most_used == "pro" and model_usage[most_used] > 3000:
                recommendations.append(
                    "🤖 Heavy Pro model usage detected. Consider using Flash for simpler operations."
                )
                
        if not recommendations:
            recommendations.append("✅ Performance is within optimal parameters.")
            
        return recommendations
        
    def _generate_summary(self,
                         total_duration_ms: float,
                         bottlenecks: List[Dict],
                         memory_profile: Dict[str, float]) -> str:
        """Generate human-readable performance summary"""
        summary_parts = []
        
        # Duration summary
        summary_parts.append(f"Total Duration: {total_duration_ms:.0f}ms")
        
        # Operations summary
        summary_parts.append(f"Operations: {len(self.current_profile)}")
        
        # Success rate
        successful = sum(1 for op in self.current_profile if op.success)
        success_rate = (successful / len(self.current_profile)) * 100 if self.current_profile else 0
        summary_parts.append(f"Success Rate: {success_rate:.0f}%")
        
        # Bottleneck summary
        if bottlenecks:
            summary_parts.append(
                f"Main Bottleneck: {bottlenecks[0]['operation']} "
                f"({bottlenecks[0]['duration_ms']:.0f}ms)"
            )
            
        # Memory summary
        summary_parts.append(
            f"Memory: {memory_profile['initial_mb']:.0f}MB → {memory_profile['peak_mb']:.0f}MB"
        )
        
        return " | ".join(summary_parts)
        
    async def _save_profile(self, profile: PerformanceProfile):
        """Save performance profile to disk using non-blocking I/O"""
        profile_file = self.logs_dir / f"profile_{profile.profile_id}.json"
        
        # Convert to serializable format
        profile_dict = {
            "profile_id": profile.profile_id,
            "timestamp": profile.timestamp.isoformat(),
            "total_duration_ms": profile.total_duration_ms,
            "operations": [asdict(op) for op in profile.operations],
            "bottlenecks": profile.bottlenecks,
            "memory_profile": profile.memory_profile,
            "recommendations": profile.recommendations,
            "summary": profile.summary,
            "operation_stats": self.operation_stats  # Include aggregation stats
        }
        
        # Use asyncio to perform file I/O in a thread pool (non-blocking)
        def write_json():
            with open(profile_file, 'w') as f:
                json.dump(profile_dict, f, indent=2)
        
        # Run blocking I/O in executor to avoid blocking event loop
        await asyncio.get_event_loop().run_in_executor(None, write_json)
            
        logger.info(f"Saved performance profile to {profile_file}")
        
    async def load_profile(self, profile_id: str) -> Optional[Dict]:
        """Load a saved performance profile using non-blocking I/O"""
        profile_file = self.logs_dir / f"profile_{profile_id}.json"
        
        if not profile_file.exists():
            return None
        
        # Use asyncio to perform file I/O in a thread pool (non-blocking)
        def read_json():
            with open(profile_file, 'r') as f:
                return json.load(f)
        
        # Run blocking I/O in executor to avoid blocking event loop
        return await asyncio.get_event_loop().run_in_executor(None, read_json)
            
    async def compare_profiles(self, profile_id1: str, profile_id2: str) -> Dict[str, Any]:
        """
        Compare two performance profiles to detect regressions
        
        Args:
            profile_id1: First profile ID (baseline)
            profile_id2: Second profile ID (comparison)
            
        Returns:
            Comparison report with regressions and improvements
        """
        profile1 = await self.load_profile(profile_id1)
        profile2 = await self.load_profile(profile_id2)
        
        if not profile1 or not profile2:
            raise ValueError("One or both profiles not found")
            
        comparison = {
            "baseline_id": profile_id1,
            "comparison_id": profile_id2,
            "duration_change_ms": profile2["total_duration_ms"] - profile1["total_duration_ms"],
            "duration_change_percent": (
                (profile2["total_duration_ms"] - profile1["total_duration_ms"]) / 
                profile1["total_duration_ms"] * 100
            ),
            "memory_change_mb": (
                profile2["memory_profile"]["peak_mb"] - 
                profile1["memory_profile"]["peak_mb"]
            ),
            "regressions": [],
            "improvements": []
        }
        
        # Identify regressions and improvements
        if comparison["duration_change_ms"] > 500:
            comparison["regressions"].append(
                f"Performance regression: +{comparison['duration_change_ms']:.0f}ms "
                f"({comparison['duration_change_percent']:+.1f}%)"
            )
        elif comparison["duration_change_ms"] < -500:
            comparison["improvements"].append(
                f"Performance improvement: {comparison['duration_change_ms']:.0f}ms "
                f"({comparison['duration_change_percent']:+.1f}%)"
            )
            
        if comparison["memory_change_mb"] > 100:
            comparison["regressions"].append(
                f"Memory regression: +{comparison['memory_change_mb']:.0f}MB peak usage"
            )
        elif comparison["memory_change_mb"] < -100:
            comparison["improvements"].append(
                f"Memory improvement: {comparison['memory_change_mb']:.0f}MB peak usage"
            )
            
        return comparison

# Export for MCP tool integration
async def profile_performance(
    operation_type: str = "review",
    trace_id: Optional[str] = None,
    detailed: bool = True
) -> str:
    """
    MCP tool endpoint for performance profiling
    
    Args:
        operation_type: Type of operation to profile
        trace_id: Optional trace ID for correlation
        detailed: Whether to include detailed metrics
        
    Returns:
        Markdown-formatted performance report
    """
    profiler = PerformanceProfiler()
    profile_id = await profiler.start_profiling(trace_id)
    
    # Simulate profiling some operations (in real usage, this would wrap actual operations)
    # For now, return a sample profile structure
    
    report = f"""# Performance Profile Report

**Profile ID**: {profile_id}
**Timestamp**: {datetime.now().isoformat()}
**Operation Type**: {operation_type}
{f'**Trace ID**: {trace_id}' if trace_id else ''}

## Summary
- Total Duration: Awaiting operation execution
- Memory Usage: Monitoring active
- Bottlenecks: Analysis pending

## Recommendations
1. Use this profiler to wrap actual Gemini operations
2. Integrate with TraceContext for request correlation
3. Monitor memory usage during large file operations
4. Compare profiles to detect performance regressions

## Integration Instructions
```python
from src.tools.performance_profiler import PerformanceProfiler

profiler = PerformanceProfiler()
profile_id = await profiler.start_profiling()

# Wrap operations
result, metrics = await profiler.capture_operation(
    "gemini_review",
    lambda: review_service.review_output(content),
    trace_id=trace_context.get_trace_id(),
    model_used="flash"
)

# Analyze results
profile = await profiler.analyze_profile(profile_id)
print(profile.summary)
for rec in profile.recommendations:
    print(f"- {rec}")
```

## Next Steps
- Register this tool in mcp_server.py
- Integrate with existing review operations
- Generate baseline profiles for comparison
- Set up automated regression detection
"""
    
    return report