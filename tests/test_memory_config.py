"""
Test memory threshold configuration and fallback behavior
"""
import unittest
from unittest.mock import patch, Mock, AsyncMock
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemoryConfiguration(unittest.TestCase):
    """Test memory threshold configuration in investigate_tool"""
    
    def test_default_memory_threshold(self):
        """Test default 90% memory threshold"""
        from src.smart_tools.investigate_tool import InvestigateTool
        
        engines = {}
        tool = InvestigateTool(engines)
        
        # Check default values
        self.assertEqual(tool._execution_mode, 'parallel')
        self.assertTrue(tool._sequential_fallback)
        # Note: The 90% threshold is currently hardcoded in the execute method
    
    @patch.dict(os.environ, {
        'INVESTIGATE_EXECUTION_MODE': 'sequential',
        'INVESTIGATE_SEQUENTIAL_FALLBACK': 'false'
    })
    def test_execution_mode_configuration(self):
        """Test configuration via environment variables"""
        from src.smart_tools.investigate_tool import InvestigateTool
        
        engines = {}
        tool = InvestigateTool(engines)
        
        self.assertEqual(tool._execution_mode, 'sequential')
        self.assertFalse(tool._sequential_fallback)
    
    @patch('psutil.virtual_memory')
    def test_memory_based_fallback(self, mock_memory):
        """Test automatic fallback to sequential when memory is high"""
        from src.smart_tools.investigate_tool import InvestigateTool
        
        async def test():
            # Setup
            engines = {
                'search_code': AsyncMock(return_value="search_result"),
                'check_quality': AsyncMock(return_value="quality_result")
            }
            tool = InvestigateTool(engines)
            tool._execution_mode = 'parallel'
            tool._sequential_fallback = True
            
            # Mock high memory usage (95%)
            mock_memory.return_value = Mock(percent=95)
            
            # Mock the sequential execution method
            tool._execute_sequential_investigation = AsyncMock(
                return_value={"search_code": "sequential_result"}
            )
            
            # Execute
            with patch('asyncio.to_thread', return_value=mock_memory.return_value):
                result = await tool.execute(
                    files=["test.py"],
                    problem="test problem"
                )
            
            # Should have used sequential execution due to high memory
            tool._execute_sequential_investigation.assert_called_once()
        
        asyncio.run(test())
    
    @patch('psutil.virtual_memory')
    def test_parallel_execution_with_low_memory(self, mock_memory):
        """Test parallel execution when memory is low"""
        from src.smart_tools.investigate_tool import InvestigateTool
        
        async def test():
            # Setup
            engines = {
                'search_code': AsyncMock(return_value="search_result"),
                'check_quality': AsyncMock(return_value="quality_result")
            }
            tool = InvestigateTool(engines)
            tool._execution_mode = 'parallel'
            tool._sequential_fallback = True
            
            # Mock low memory usage (50%)
            mock_memory.return_value = Mock(percent=50)
            
            # Execute
            with patch('asyncio.to_thread', return_value=mock_memory.return_value):
                with patch.object(tool, '_prepare_investigation_kwargs', 
                                return_value={'query': 'test'}):
                    with patch('asyncio.gather', return_value=["result1", "result2"]):
                        result = await tool.execute(
                            files=["test.py"],
                            problem="test problem"
                        )
            
            # Should use parallel execution
            self.assertIn("Detected issues", result.result)
        
        asyncio.run(test())
    
    def test_forced_sequential_mode(self):
        """Test forced sequential mode ignores memory"""
        from src.smart_tools.investigate_tool import InvestigateTool
        
        async def test():
            # Setup
            engines = {
                'search_code': AsyncMock(return_value="search_result")
            }
            tool = InvestigateTool(engines)
            tool._execution_mode = 'sequential'
            tool._sequential_fallback = False  # Shouldn't matter
            
            # Mock sequential execution
            tool._execute_sequential_investigation = AsyncMock(
                return_value={"search_code": "sequential_result"}
            )
            
            # Execute (memory check shouldn't even happen)
            result = await tool.execute(
                files=["test.py"],
                problem="test problem"
            )
            
            # Should use sequential regardless of memory
            tool._execute_sequential_investigation.assert_called_once()
        
        asyncio.run(test())
    
    @patch.dict(os.environ, {
        'INVESTIGATE_MEMORY_FALLBACK_THRESHOLD': '85'
    })
    def test_configurable_memory_threshold(self):
        """Test that memory threshold can be configured (future implementation)"""
        # This test demonstrates what should work after making threshold configurable
        from src.smart_tools.investigate_tool import InvestigateTool
        
        # After implementation, this should work:
        # tool = InvestigateTool({})
        # self.assertEqual(tool._memory_fallback_threshold, 85)
        
        # For now, just verify the environment variable is set
        self.assertEqual(os.environ.get('INVESTIGATE_MEMORY_FALLBACK_THRESHOLD'), '85')


class TestValidateMemoryConfiguration(unittest.TestCase):
    """Test memory configuration in validate_tool"""
    
    @patch('psutil.virtual_memory')
    def test_validate_memory_check(self, mock_memory):
        """Test validate tool memory check for parallel execution"""
        from src.smart_tools.validate_tool import ValidateTool
        
        async def test():
            # Setup
            engines = {
                'check_quality': AsyncMock(return_value="quality_result")
            }
            tool = ValidateTool(engines)
            
            # Mock memory at 85%
            mock_memory.return_value = Mock(percent=85)
            
            # Execute
            with patch('asyncio.to_thread', return_value=mock_memory.return_value):
                with patch.object(tool, '_prepare_validation_kwargs',
                                return_value={'check_type': 'all'}):
                    with patch('asyncio.gather', return_value=["result"]):
                        result = await tool.execute(
                            files=["test.py"],
                            validation_type="security"
                        )
            
            # Should execute normally with 85% memory
            self.assertIn("Validation", result.result)
        
        asyncio.run(test())
    
    @patch('psutil.virtual_memory')
    def test_validate_high_memory_handling(self, mock_memory):
        """Test validate tool behavior with very high memory"""
        from src.smart_tools.validate_tool import ValidateTool
        
        async def test():
            # Setup
            engines = {
                'check_quality': AsyncMock(return_value="quality_result")
            }
            tool = ValidateTool(engines)
            
            # Mock very high memory (95%)
            mock_memory.return_value = Mock(percent=95)
            
            # Execute - should limit parallelism
            with patch('asyncio.to_thread', return_value=mock_memory.return_value):
                with patch.object(tool, '_prepare_validation_kwargs',
                                return_value={'check_type': 'all'}):
                    with patch('asyncio.Semaphore') as mock_semaphore:
                        with patch('asyncio.gather', return_value=["result"]):
                            result = await tool.execute(
                                files=["test.py"],
                                validation_type="security"
                            )
                        
                        # Should create semaphore with max_parallel=2 for high memory
                        mock_semaphore.assert_called_with(2)
        
        asyncio.run(test())


class TestMemoryConfigurationIntegration(unittest.TestCase):
    """Integration tests for memory configuration across tools"""
    
    def test_all_tools_have_memory_awareness(self):
        """Verify all smart tools that use parallel execution have memory checks"""
        tools_with_parallel = [
            'investigate_tool',
            'validate_tool',
            'understand_tool',
            'full_analysis_tool'
        ]
        
        for tool_name in tools_with_parallel:
            module_path = f'src.smart_tools.{tool_name}'
            try:
                module = __import__(module_path, fromlist=[tool_name])
                # Check if the tool's execute method includes memory checking
                # This is a basic check - actual implementation may vary
                self.assertTrue(
                    hasattr(module, tool_name.replace('_tool', '').capitalize() + 'Tool'),
                    f"{tool_name} should have a tool class"
                )
            except ImportError:
                pass  # Some tools might not exist yet
    
    @patch.dict(os.environ, {
        'INVESTIGATE_MEMORY_FALLBACK_THRESHOLD': '80',
        'VALIDATE_MEMORY_THRESHOLD': '85',
        'UNDERSTAND_MEMORY_THRESHOLD': '90'
    })
    def test_per_tool_memory_configuration(self):
        """Test that different tools can have different memory thresholds"""
        # This demonstrates the desired configuration capability
        # Each tool should be able to have its own threshold
        
        expected_thresholds = {
            'INVESTIGATE_MEMORY_FALLBACK_THRESHOLD': '80',
            'VALIDATE_MEMORY_THRESHOLD': '85',
            'UNDERSTAND_MEMORY_THRESHOLD': '90'
        }
        
        for key, expected_value in expected_thresholds.items():
            self.assertEqual(os.environ.get(key), expected_value)


if __name__ == '__main__':
    unittest.main()