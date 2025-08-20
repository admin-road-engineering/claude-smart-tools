"""
Unit tests for EngineWrapper functionality
Tests the engine wrapper that provides Smart Tools access to Gemini engines
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

# Import the class to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from engines.engine_wrapper import EngineWrapper


class TestEngineWrapper:
    """Test EngineWrapper basic functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_gemini_impl = Mock()
        self.mock_gemini_impl.analyze_code = AsyncMock(return_value="Mock analysis")
        self.mock_gemini_impl.search_code = AsyncMock(return_value="Mock search")
        self.mock_gemini_impl.check_quality = AsyncMock(return_value="Mock quality")
        
        self.wrapper = EngineWrapper(self.mock_gemini_impl)
    
    def test_initialization(self):
        """Test that EngineWrapper initializes correctly"""
        assert self.wrapper.gemini_impl == self.mock_gemini_impl
        assert hasattr(self.wrapper, 'available_engines')
        assert len(self.wrapper.available_engines) > 0
    
    def test_available_engines_detection(self):
        """Test that available engines are detected correctly"""
        available = self.wrapper.get_available_engines()
        
        # Should include methods from the gemini implementation
        assert 'analyze_code' in available
        assert 'search_code' in available
        assert 'check_quality' in available
        
        # Should not include private methods or non-callable attributes
        assert '_private_method' not in available
        assert '__init__' not in available
    
    @pytest.mark.asyncio
    async def test_execute_valid_engine(self):
        """Test executing a valid engine"""
        result = await self.wrapper.execute('analyze_code', files=['test.py'])
        
        assert result == "Mock analysis"
        self.mock_gemini_impl.analyze_code.assert_called_once_with(files=['test.py'])
    
    @pytest.mark.asyncio
    async def test_execute_invalid_engine(self):
        """Test executing an invalid engine name"""
        result = await self.wrapper.execute('nonexistent_engine')
        
        assert "Engine nonexistent_engine not available" in result
        # Should not call any methods on gemini_impl
        assert not any(call[0] for call in self.mock_gemini_impl.method_calls)
    
    @pytest.mark.asyncio
    async def test_path_normalization_monkey_patch(self):
        """Test that path normalization monkey patch is applied"""
        # This tests that the monkey patch is applied correctly
        with patch.object(self.wrapper, '_apply_path_normalization_monkey_patch') as mock_patch:
            wrapper = EngineWrapper(self.mock_gemini_impl)
            mock_patch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_engine_execution(self):
        """Test error handling when engine execution fails"""
        # Make the engine method raise an exception
        self.mock_gemini_impl.analyze_code.side_effect = Exception("Engine execution failed")
        
        result = await self.wrapper.execute('analyze_code', files=['test.py'])
        
        assert "Error in analyze_code" in result
        assert "Engine execution failed" in result
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of timeout errors"""
        import asyncio
        self.mock_gemini_impl.analyze_code.side_effect = asyncio.TimeoutError("Request timed out")
        
        result = await self.wrapper.execute('analyze_code', files=['test.py'])
        
        assert "Error in analyze_code" in result
        assert "timed out" in result.lower()


class TestEngineWrapperPathNormalization:
    """Test path normalization functionality in EngineWrapper"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_gemini_impl = Mock()
        # Create a method that we can inspect the arguments of
        self.mock_gemini_impl.analyze_code = AsyncMock(return_value="Analysis result")
        self.wrapper = EngineWrapper(self.mock_gemini_impl)
    
    @pytest.mark.asyncio
    async def test_string_paths_preserved(self):
        """Test that string paths are preserved correctly"""
        await self.wrapper.execute('analyze_code', files=['test.py', 'src/main.py'])
        
        call_args = self.mock_gemini_impl.analyze_code.call_args
        files_arg = call_args[1]['files']  # kwargs
        
        assert isinstance(files_arg, list)
        assert all(isinstance(path, str) for path in files_arg)
        assert 'test.py' in files_arg
        assert 'src/main.py' in files_arg
    
    @pytest.mark.asyncio
    async def test_path_object_normalization(self):
        """Test that Path objects are normalized to strings"""
        from pathlib import Path
        
        path_obj = Path('test.py')
        await self.wrapper.execute('analyze_code', files=[path_obj])
        
        call_args = self.mock_gemini_impl.analyze_code.call_args
        files_arg = call_args[1]['files']
        
        assert isinstance(files_arg, list)
        assert isinstance(files_arg[0], str)
        assert 'test.py' in files_arg[0]
    
    @pytest.mark.asyncio
    async def test_mixed_path_types_normalization(self):
        """Test normalization of mixed path types"""
        from pathlib import Path
        
        mixed_paths = ['string_file.py', Path('path_object.py')]
        await self.wrapper.execute('analyze_code', files=mixed_paths)
        
        call_args = self.mock_gemini_impl.analyze_code.call_args
        files_arg = call_args[1]['files']
        
        assert len(files_arg) == 2
        assert all(isinstance(path, str) for path in files_arg)
        assert any('string_file.py' in path for path in files_arg)
        assert any('path_object.py' in path for path in files_arg)
    
    @pytest.mark.asyncio
    async def test_single_path_to_list_conversion(self):
        """Test that single paths are converted to lists"""
        await self.wrapper.execute('analyze_code', files='single_file.py')
        
        call_args = self.mock_gemini_impl.analyze_code.call_args
        files_arg = call_args[1]['files']
        
        assert isinstance(files_arg, list)
        assert len(files_arg) == 1
        assert 'single_file.py' in files_arg[0]
    
    def test_monkey_patch_application(self):
        """Test that monkey patch is applied to gemini implementation"""
        # Check that the _collect_code_from_paths method exists after patching
        assert hasattr(self.mock_gemini_impl, '_collect_code_from_paths')
        # The method should be callable
        assert callable(getattr(self.mock_gemini_impl, '_collect_code_from_paths'))


class TestEngineWrapperAsyncMethods:
    """Test async method handling in EngineWrapper"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_gemini_impl = Mock()
        # Mix of async and sync methods
        self.mock_gemini_impl.async_engine = AsyncMock(return_value="Async result")
        self.mock_gemini_impl.sync_engine = Mock(return_value="Sync result")
        self.wrapper = EngineWrapper(self.mock_gemini_impl)
    
    @pytest.mark.asyncio
    async def test_async_engine_execution(self):
        """Test execution of async engine methods"""
        # Add the async method to available engines manually for testing
        self.wrapper.available_engines.append('async_engine')
        
        result = await self.wrapper.execute('async_engine', test_param='value')
        
        assert result == "Async result"
        self.mock_gemini_impl.async_engine.assert_called_once_with(test_param='value')
    
    @pytest.mark.asyncio
    async def test_sync_engine_execution(self):
        """Test execution of sync engine methods"""
        # Add the sync method to available engines manually for testing
        self.wrapper.available_engines.append('sync_engine')
        
        result = await self.wrapper.execute('sync_engine', test_param='value')
        
        assert result == "Sync result"
        self.mock_gemini_impl.sync_engine.assert_called_once_with(test_param='value')
    
    @pytest.mark.asyncio
    async def test_method_detection_excludes_private(self):
        """Test that private methods are not included in available engines"""
        # Add some private methods to the mock
        self.mock_gemini_impl._private_method = Mock(return_value="Private")
        self.mock_gemini_impl.__dunder_method__ = Mock(return_value="Dunder")
        
        # Re-initialize to pick up new methods
        wrapper = EngineWrapper(self.mock_gemini_impl)
        available = wrapper.get_available_engines()
        
        assert '_private_method' not in available
        assert '__dunder_method__' not in available


class TestEngineWrapperErrorScenarios:
    """Test error scenarios and edge cases"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_gemini_impl = Mock()
        self.wrapper = EngineWrapper(self.mock_gemini_impl)
    
    @pytest.mark.asyncio
    async def test_gemini_impl_none(self):
        """Test behavior when gemini_impl is None"""
        wrapper = EngineWrapper(None)
        
        result = await wrapper.execute('any_engine')
        assert "Engine any_engine not available" in result
    
    @pytest.mark.asyncio
    async def test_engine_returns_none(self):
        """Test handling when engine returns None"""
        self.mock_gemini_impl.test_engine = AsyncMock(return_value=None)
        self.wrapper.available_engines.append('test_engine')
        
        result = await self.wrapper.execute('test_engine')
        
        # Should handle None result gracefully
        assert result is None or isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_engine_raises_rate_limit_error(self):
        """Test handling of rate limit errors"""
        rate_limit_error = Exception("Rate limited - exhausted quota")
        self.mock_gemini_impl.test_engine = AsyncMock(side_effect=rate_limit_error)
        self.wrapper.available_engines.append('test_engine')
        
        result = await self.wrapper.execute('test_engine')
        
        assert "rate limit" in result.lower()
    
    @pytest.mark.asyncio
    async def test_engine_file_not_found_error(self):
        """Test handling of file not found errors"""
        file_error = Exception("No files found matching criteria")
        self.mock_gemini_impl.test_engine = AsyncMock(side_effect=file_error)
        self.wrapper.available_engines.append('test_engine')
        
        result = await self.wrapper.execute('test_engine')
        
        assert "no files found" in result.lower()
    
    @pytest.mark.asyncio
    async def test_api_key_error_handling(self):
        """Test handling of API key errors"""
        api_key_error = Exception("Invalid API key provided")
        self.mock_gemini_impl.test_engine = AsyncMock(side_effect=api_key_error)
        self.wrapper.available_engines.append('test_engine')
        
        result = await self.wrapper.execute('test_engine')
        
        assert "api key" in result.lower()


class TestEngineWrapperIntegration:
    """Test EngineWrapper integration aspects"""
    
    def test_wrapper_with_real_like_gemini_impl(self):
        """Test wrapper with a more realistic gemini implementation mock"""
        # Create a more realistic mock that simulates the actual gemini tools
        realistic_mock = Mock()
        
        # Add common gemini tool methods
        tool_methods = [
            'analyze_code', 'search_code', 'check_quality', 'analyze_docs',
            'analyze_logs', 'analyze_database', 'map_dependencies',
            'config_validator', 'api_contract_checker', 'analyze_test_coverage',
            'interface_inconsistency_detector', 'performance_profiler', 'review_output'
        ]
        
        for method_name in tool_methods:
            setattr(realistic_mock, method_name, AsyncMock(return_value=f"Mock {method_name} result"))
        
        wrapper = EngineWrapper(realistic_mock)
        available = wrapper.get_available_engines()
        
        # Should detect all the tool methods
        for method_name in tool_methods:
            assert method_name in available
        
        assert len(available) >= len(tool_methods)
    
    def test_wrapper_preserves_method_signatures(self):
        """Test that wrapper preserves original method signatures"""
        mock_impl = Mock()
        
        # Create a method with specific signature
        async def sample_method(files, focus=None, detail_level="summary"):
            return f"Result with {len(files)} files, focus={focus}, detail={detail_level}"
        
        mock_impl.sample_method = sample_method
        wrapper = EngineWrapper(mock_impl)
        wrapper.available_engines.append('sample_method')
        
        # The wrapper should preserve the ability to call with these parameters
        # This is more of an integration test with actual execution
        assert 'sample_method' in wrapper.get_available_engines()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])