"""
Simple integration tests that should work with the existing codebase
Tests basic functionality without complex mocking
"""
import pytest
import os
import tempfile
from pathlib import Path

# Import basic utilities that should work
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestBasicImports:
    """Test that all modules can be imported without errors"""
    
    def test_import_smart_tools_base(self):
        """Test importing base smart tool"""
        from smart_tools.base_smart_tool import BaseSmartTool, SmartToolResult
        assert BaseSmartTool is not None
        assert SmartToolResult is not None
    
    def test_import_path_utils(self):
        """Test importing path utilities"""
        from utils.path_utils import normalize_paths, safe_path_iteration
        assert normalize_paths is not None
        assert safe_path_iteration is not None
    
    def test_import_cpu_throttler(self):
        """Test importing CPU throttler"""
        from services.cpu_throttler import get_cpu_throttler, CPUThrottler
        assert get_cpu_throttler is not None
        assert CPUThrottler is not None
    
    def test_import_project_context(self):
        """Test importing project context utilities"""
        from utils.project_context import get_project_context_reader, ProjectContextReader
        assert get_project_context_reader is not None
        assert ProjectContextReader is not None


class TestCPUThrottlerBasic:
    """Test basic CPU throttler functionality"""
    
    def test_cpu_throttler_singleton(self):
        """Test that CPU throttler returns singleton instance"""
        from services.cpu_throttler import get_cpu_throttler
        
        throttler1 = get_cpu_throttler()
        throttler2 = get_cpu_throttler()
        
        # Should return the same instance
        assert throttler1 is throttler2
    
    def test_cpu_throttler_initialization(self):
        """Test CPU throttler initializes with defaults"""
        from services.cpu_throttler import get_cpu_throttler
        
        throttler = get_cpu_throttler()
        assert throttler is not None
        assert hasattr(throttler, 'max_cpu_percent')
        assert hasattr(throttler, 'yield_interval_ms')
    
    @pytest.mark.asyncio
    async def test_cpu_throttler_yield(self):
        """Test CPU throttler yield functionality"""
        from services.cpu_throttler import get_cpu_throttler
        
        throttler = get_cpu_throttler()
        
        # Should not raise any errors
        await throttler.yield_if_needed()
        
        # Multiple calls should work
        await throttler.yield_if_needed()
        await throttler.yield_if_needed()


class TestProjectContextReader:
    """Test basic project context functionality"""
    
    def test_project_context_reader_creation(self):
        """Test creating project context reader"""
        from utils.project_context import ProjectContextReader
        
        reader = ProjectContextReader()
        assert reader is not None
        assert hasattr(reader, 'read_project_context')
        assert hasattr(reader, 'format_context_for_analysis')
    
    def test_project_context_with_temp_files(self):
        """Test project context reading with temporary files"""
        from utils.project_context import ProjectContextReader
        
        reader = ProjectContextReader()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a simple test file
            test_file = os.path.join(tmp_dir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('# Test file\ndef hello():\n    pass')
            
            # Should not crash when reading context
            context = reader.read_project_context([test_file])
            assert isinstance(context, dict)
    
    def test_format_context_for_analysis(self):
        """Test context formatting"""
        from utils.project_context import ProjectContextReader
        
        reader = ProjectContextReader()
        
        # Create minimal context
        context = {
            'project_type': 'python',
            'claude_md_content': '# Test Project\nThis is a test.',
            'context_files_found': ['CLAUDE.md']
        }
        
        formatted = reader.format_context_for_analysis(context)
        assert isinstance(formatted, str)
        assert len(formatted) > 0


class TestSmartToolResultModel:
    """Test the SmartToolResult Pydantic model"""
    
    def test_smart_tool_result_basic_creation(self):
        """Test creating basic SmartToolResult"""
        from smart_tools.base_smart_tool import SmartToolResult
        
        result = SmartToolResult(
            tool_name="test",
            success=True,
            result="Test result",
            engines_used=["engine1"],
            routing_decision="Test decision"
        )
        
        assert result.tool_name == "test"
        assert result.success is True
        assert result.result == "Test result"
        assert result.engines_used == ["engine1"]
        assert result.routing_decision == "Test decision"
    
    def test_smart_tool_result_with_metadata(self):
        """Test SmartToolResult with metadata"""
        from smart_tools.base_smart_tool import SmartToolResult
        
        metadata = {"files": ["test.py"], "question": "How does this work?"}
        
        result = SmartToolResult(
            tool_name="understand",
            success=True,
            result="Analysis complete",
            engines_used=["analyze_code", "search_code"],
            routing_decision="Multi-engine analysis",
            metadata=metadata
        )
        
        assert result.metadata == metadata
        assert result.metadata["files"] == ["test.py"]
        assert result.metadata["question"] == "How does this work?"
    
    def test_smart_tool_result_optional_fields(self):
        """Test SmartToolResult optional fields"""
        from smart_tools.base_smart_tool import SmartToolResult
        
        result = SmartToolResult(
            tool_name="test",
            success=False,
            result="Failed",
            engines_used=[],
            routing_decision="No routing"
        )
        
        # Optional fields should be None/default
        assert result.metadata == {}
        assert result.correlations is None
        assert result.conflicts is None
        assert result.resolutions is None


class TestBasicFileOperations:
    """Test basic file operations that Smart Tools rely on"""
    
    def test_file_caching_structure(self):
        """Test that file caching structure works"""
        from smart_tools.base_smart_tool import BaseSmartTool
        
        # Create a mock implementation just to test the structure
        class MockTool(BaseSmartTool):
            async def execute(self, **kwargs):
                return None
            
            def get_routing_strategy(self, **kwargs):
                return {"engines": [], "strategy": "test"}
        
        tool = MockTool({})
        
        # Should have caching attributes
        assert hasattr(tool, '_file_content_cache')
        assert hasattr(tool, '_cache_enabled')
        assert hasattr(tool, 'get_cache_stats')
        assert hasattr(tool, 'clear_cache')
        
        # Cache stats should work
        stats = tool.get_cache_stats()
        assert isinstance(stats, dict)
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
    
    def test_path_normalization_with_real_files(self):
        """Test path normalization with real temporary files"""
        from utils.path_utils import normalize_paths
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp.write('# Test file\nprint("hello")')
            tmp_path = tmp.name
        
        try:
            # Test string path
            result = normalize_paths(tmp_path)
            assert len(result) == 1
            assert os.path.isabs(result[0])
            assert os.path.exists(result[0])
            
            # Test Path object
            result2 = normalize_paths(Path(tmp_path))
            assert len(result2) == 1
            assert isinstance(result2[0], str)
            assert os.path.isabs(result2[0])
            
        finally:
            os.unlink(tmp_path)
    
    def test_directory_file_discovery(self):
        """Test that normalize_paths can discover files in directories"""
        from utils.path_utils import normalize_paths
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create some test files
            py_file = os.path.join(tmp_dir, 'test.py')
            js_file = os.path.join(tmp_dir, 'test.js')
            
            with open(py_file, 'w') as f:
                f.write('# Python file')
            with open(js_file, 'w') as f:
                f.write('// JavaScript file')
            
            # Test directory discovery
            result = normalize_paths(tmp_dir)
            assert len(result) >= 2  # Should find both files
            assert any('test.py' in path for path in result)
            assert any('test.js' in path for path in result)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])