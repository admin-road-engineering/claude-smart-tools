"""
Unit tests for the BaseSmartTool class
Tests core Smart Tool functionality including routing, caching, and error handling
"""
import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Import the class to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from smart_tools.base_smart_tool import BaseSmartTool, SmartToolResult


class MockSmartTool(BaseSmartTool):
    """Mock implementation of BaseSmartTool for testing"""
    
    async def execute(self, **kwargs) -> SmartToolResult:
        """Mock execute implementation"""
        routing_strategy = self.get_routing_strategy(**kwargs)
        return SmartToolResult(
            tool_name=self.tool_name,
            success=True,
            result="Mock result",
            engines_used=routing_strategy.get('engines', []),
            routing_decision="Mock routing decision",
            metadata=kwargs
        )
    
    def get_routing_strategy(self, **kwargs) -> dict:
        """Mock routing strategy"""
        return {
            'engines': ['analyze_code', 'search_code'],
            'strategy': 'parallel',
            'reason': 'Mock routing for testing'
        }


class TestBaseSmartTool:
    """Test the BaseSmartTool abstract class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_engines = {
            'analyze_code': AsyncMock(return_value="Mock analyze result"),
            'search_code': AsyncMock(return_value="Mock search result"),
            'check_quality': AsyncMock(return_value="Mock quality result")
        }
        self.tool = MockSmartTool(self.mock_engines)
    
    def test_initialization(self):
        """Test that BaseSmartTool initializes correctly"""
        assert self.tool.engines == self.mock_engines
        assert self.tool.tool_name == "mocksmartool"  # Class name with "Tool" removed and lowercased
        assert hasattr(self.tool, 'cpu_throttler')
        assert hasattr(self.tool, 'context_reader')
    
    def test_get_available_engines(self):
        """Test getting list of available engines"""
        available = self.tool.get_available_engines()
        assert 'analyze_code' in available
        assert 'search_code' in available
        assert 'check_quality' in available
        assert len(available) == 3
    
    @pytest.mark.asyncio
    async def test_execute_engine_basic(self):
        """Test basic engine execution"""
        result = await self.tool.execute_engine('analyze_code', files=['test.py'])
        assert result == "Mock analyze result"
        self.mock_engines['analyze_code'].assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_engine_not_available(self):
        """Test execution of non-existent engine"""
        result = await self.tool.execute_engine('nonexistent_engine')
        assert "Engine nonexistent_engine not available" in result
    
    @pytest.mark.asyncio
    async def test_path_normalization_in_execute_engine(self):
        """Test that path parameters are normalized before passing to engines"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            tmp_path = Path(tmp.name)
        
        try:
            await self.tool.execute_engine('analyze_code', files=tmp_path)
            
            # Check that the engine was called with normalized string paths
            call_args = self.mock_engines['analyze_code'].call_args
            assert call_args is not None
            called_files = call_args[1]['files']  # kwargs
            assert isinstance(called_files, list)
            assert len(called_files) == 1
            assert isinstance(called_files[0], str)
            assert os.path.isabs(called_files[0])
        finally:
            os.unlink(tmp.name)
    
    @pytest.mark.asyncio
    async def test_execute_multiple_engines(self):
        """Test executing multiple engines"""
        engine_names = ['analyze_code', 'search_code']
        results = await self.tool.execute_multiple_engines(engine_names, files=['test.py'])
        
        assert len(results) == 2
        assert 'analyze_code' in results
        assert 'search_code' in results
        assert results['analyze_code'] == "Mock analyze result"
        assert results['search_code'] == "Mock search result"
    
    def test_file_content_cache_initialization(self):
        """Test that file content caching is properly initialized"""
        assert hasattr(self.tool, '_file_content_cache')
        assert hasattr(self.tool, '_cache_enabled')
        assert hasattr(self.tool, '_cache_extensions')
        assert hasattr(self.tool, '_cache_dir_limit')
        
        # Test cache statistics
        stats = self.tool.get_cache_stats()
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'cache_size' in stats
    
    @pytest.mark.asyncio
    async def test_project_context_reading(self):
        """Test project context reading functionality"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a mock CLAUDE.md file
            claude_md = os.path.join(tmp_dir, 'CLAUDE.md')
            with open(claude_md, 'w') as f:
                f.write('# Test Project\nThis is a test project.')
            
            # Create a test file
            test_file = os.path.join(tmp_dir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('# Test Python file')
            
            # Test context reading
            context = await self.tool._get_project_context([test_file])
            assert isinstance(context, dict)
    
    def test_cache_management(self):
        """Test cache management methods"""
        # Test cache stats
        initial_stats = self.tool.get_cache_stats()
        assert initial_stats['cache_size'] == 0
        
        # Test cache clearing
        self.tool.clear_cache()  # Should not error even when empty
        
        # Test cache stats after clearing
        stats_after_clear = self.tool.get_cache_stats()
        assert stats_after_clear['cache_size'] == 0


class TestSmartToolResult:
    """Test the SmartToolResult data model"""
    
    def test_smart_tool_result_creation(self):
        """Test creating a SmartToolResult"""
        result = SmartToolResult(
            tool_name="test_tool",
            success=True,
            result="Test result content",
            engines_used=["analyze_code", "search_code"],
            routing_decision="Test routing decision",
            metadata={"test": "data"}
        )
        
        assert result.tool_name == "test_tool"
        assert result.success is True
        assert result.result == "Test result content"
        assert result.engines_used == ["analyze_code", "search_code"]
        assert result.routing_decision == "Test routing decision"
        assert result.metadata == {"test": "data"}
        assert result.correlations is None  # Optional field
    
    def test_smart_tool_result_with_correlations(self):
        """Test SmartToolResult with correlation data"""
        correlations = {
            "correlations": ["Engine A and B agree on issue X"],
            "conflicts": ["Engine A disagrees with B on issue Y"],
            "resolutions": ["Resolved conflict by prioritizing Engine A"]
        }
        
        result = SmartToolResult(
            tool_name="test_tool",
            success=True,
            result="Test result",
            engines_used=["engine_a", "engine_b"],
            routing_decision="Multi-engine analysis",
            correlations=correlations
        )
        
        assert result.correlations == correlations
        assert result.correlations["correlations"] == ["Engine A and B agree on issue X"]


class TestSmartToolErrorHandling:
    """Test error handling in Smart Tools"""
    
    def setup_method(self):
        """Set up test fixtures with error-prone engines"""
        self.error_engines = {
            'failing_engine': AsyncMock(side_effect=Exception("Engine error")),
            'timeout_engine': AsyncMock(side_effect=asyncio.TimeoutError("Timeout")),
            'working_engine': AsyncMock(return_value="Success")
        }
        self.tool = MockSmartTool(self.error_engines)
    
    @pytest.mark.asyncio
    async def test_engine_exception_handling(self):
        """Test that engine exceptions are handled gracefully"""
        result = await self.tool.execute_engine('failing_engine')
        assert "Error in failing_engine" in result
        assert "Engine error" in result
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test that timeouts are handled gracefully"""
        result = await self.tool.execute_engine('timeout_engine')
        assert "Error in timeout_engine" in result
        assert "Timeout" in result
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_in_multiple_engines(self):
        """Test executing multiple engines where some fail"""
        engine_names = ['failing_engine', 'working_engine']
        results = await self.tool.execute_multiple_engines(engine_names)
        
        assert len(results) == 2
        assert 'failing_engine' in results
        assert 'working_engine' in results
        assert "Error in failing_engine" in results['failing_engine']
        assert results['working_engine'] == "Success"


class TestSmartToolCPUThrottling:
    """Test CPU throttling functionality"""
    
    def setup_method(self):
        """Set up test with mock CPU throttler"""
        self.mock_engines = {
            'test_engine': AsyncMock(return_value="Test result")
        }
        self.tool = MockSmartTool(self.mock_engines)
    
    @pytest.mark.asyncio
    async def test_cpu_throttling_integration(self):
        """Test that CPU throttling is integrated properly"""
        # Mock the CPU throttler
        with patch.object(self.tool, 'cpu_throttler') as mock_throttler:
            mock_throttler.yield_if_needed = AsyncMock()
            
            await self.tool.execute_engine('test_engine', files=['test.py'])
            
            # Should call yield_if_needed before and after engine execution
            assert mock_throttler.yield_if_needed.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_cpu_throttling_when_disabled(self):
        """Test behavior when CPU throttling is disabled"""
        # Temporarily disable CPU throttler
        original_throttler = self.tool.cpu_throttler
        self.tool.cpu_throttler = None
        
        try:
            # Should still work without throttler
            result = await self.tool.execute_engine('test_engine')
            assert result == "Test result"
        finally:
            self.tool.cpu_throttler = original_throttler


if __name__ == '__main__':
    pytest.main([__file__, '-v'])