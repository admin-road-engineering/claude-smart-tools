"""
Concurrency tests for ValidateTool parallel execution
Tests the parallel batching strategy and error handling
"""
import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.smart_tools.validate_tool import ValidateTool


class TestValidateToolConcurrency(unittest.IsolatedAsyncioTestCase):
    """Test concurrent execution in ValidateTool"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock engines dictionary
        self.mock_engines = {
            'check_quality': AsyncMock(),
            'config_validator': AsyncMock(),
            'interface_inconsistency_detector': AsyncMock(),
            'api_contract_checker': AsyncMock(),
            'analyze_database': AsyncMock(),
            'analyze_test_coverage': AsyncMock(),
            'performance_profiler': AsyncMock(),
            'map_dependencies': AsyncMock(),
            'analyze_code': AsyncMock()
        }
        
        # Mock executive synthesizer
        mock_executive = MagicMock()
        mock_executive.should_synthesize.return_value = False
        
        with patch('src.smart_tools.validate_tool.ExecutiveSynthesizer', return_value=mock_executive):
            self.tool = ValidateTool(self.mock_engines)
    
    async def test_parallel_batch_execution(self):
        """Test that engines execute in parallel batches"""
        # Setup return values for helper methods
        with patch.object(self.tool, '_run_quality_analysis', new_callable=AsyncMock) as mock_quality, \
             patch.object(self.tool, '_run_config_validation', new_callable=AsyncMock) as mock_config, \
             patch.object(self.tool, '_run_consistency_analysis', new_callable=AsyncMock) as mock_consistency, \
             patch.object(self.tool, '_run_test_coverage_analysis', new_callable=AsyncMock) as mock_test:
            
            # Setup return values
            mock_quality.return_value = {'quality': {'result': 'quality_result', 'issues': []}}
            mock_config.return_value = {'security_config': {'result': 'config_result', 'issues': []}}
            mock_consistency.return_value = {'consistency': {'result': 'consistency_result', 'issues': []}}
            mock_test.return_value = {'test_coverage': {'result': 'test_result', 'issues': []}}
            
            # Execute validation
            result = await self.tool.execute(
                files=['test.py'],
                validation_type='all',
                severity='medium'
            )
            
            # Assert all parallel tasks were called
            mock_quality.assert_awaited_once()
            mock_config.assert_awaited_once()
            mock_consistency.assert_awaited_once()
            mock_test.assert_awaited_once()
            
            # Assert result is successful
            self.assertTrue(result.success)
            self.assertEqual(result.metadata['performance_mode'], 'parallel')
    
    async def test_error_handling_in_parallel_batch(self):
        """Test that exceptions in parallel batch are handled properly"""
        with patch.object(self.tool, '_run_quality_analysis', new_callable=AsyncMock) as mock_quality, \
             patch.object(self.tool, '_run_config_validation', new_callable=AsyncMock) as mock_config:
            
            # Setup one success and one failure
            mock_quality.side_effect = ValueError("Quality analysis failed")
            mock_config.return_value = {'security_config': {'result': 'config_result', 'issues': []}}
            
            # Execute should not raise exception
            result = await self.tool.execute(
                files=['test.py', 'config.yaml'],
                validation_type='security',
                severity='high'
            )
            
            # Result should still be generated despite one failure
            self.assertIsNotNone(result)
            self.assertIn('Validation Results', result.result)
    
    async def test_resource_isolation_between_batches(self):
        """Test that batches don't share mutable state incorrectly"""
        # Track call order to ensure proper batching
        call_order = []
        
        async def track_call(name):
            call_order.append(name)
            await asyncio.sleep(0.01)  # Small delay to test concurrency
            return {name: {'result': f'{name}_result', 'issues': []}}
        
        with patch.object(self.tool, '_run_quality_analysis', side_effect=lambda *args: track_call('quality')), \
             patch.object(self.tool, '_run_config_validation', side_effect=lambda *args: track_call('config')), \
             patch.object(self.tool, '_run_dependency_analysis', side_effect=lambda *args: track_call('dependencies')):
            
            result = await self.tool.execute(
                files=['test.py'],
                validation_type='all',
                severity='medium'
            )
            
            # Check that parallel tasks ran concurrently (order may vary)
            self.assertIn('quality', call_order)
            self.assertIn('config', call_order)
            # Dependencies should run in second batch
            self.assertIn('dependencies', call_order)
    
    async def test_memory_safeguard_with_large_file_count(self):
        """Test that large file counts don't cause memory issues"""
        # Create a large list of files
        large_file_list = [f'file_{i}.py' for i in range(1000)]
        
        with patch.object(self.tool, '_detect_source_files', return_value=large_file_list[:100]), \
             patch.object(self.tool, '_find_config_files', return_value=large_file_list[:50]):
            
            # This should complete without memory errors
            result = await self.tool.execute(
                files=large_file_list,
                validation_type='all',
                severity='low'
            )
            
            # Should handle large file count gracefully
            self.assertIsNotNone(result)
            self.assertEqual(result.metadata['files_analyzed'], 1000)
    
    async def test_exception_aggregation_and_reporting(self):
        """Test that multiple exceptions are properly aggregated and reported"""
        exception_count = 0
        
        with patch.object(self.tool, '_run_quality_analysis', side_effect=ValueError("Quality failed")), \
             patch.object(self.tool, '_run_config_validation', side_effect=RuntimeError("Config failed")), \
             patch.object(self.tool, '_run_consistency_analysis', side_effect=TypeError("Consistency failed")):
            
            # Should handle multiple exceptions gracefully
            result = await self.tool.execute(
                files=['test.py'],
                validation_type='all',
                severity='medium'
            )
            
            # Result should still be generated
            self.assertIsNotNone(result)
            # Check that failures are mentioned in the result
            self.assertIn('failed', result.result.lower())


if __name__ == '__main__':
    unittest.main()