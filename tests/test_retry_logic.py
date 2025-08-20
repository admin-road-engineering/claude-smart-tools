"""
Comprehensive unit tests for _execute_engine_with_retry method
Tests all retry scenarios including rate limits, transient errors, and max retries
"""
import unittest
from unittest.mock import Mock, patch, AsyncMock, call
import asyncio
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.smart_tools.base_smart_tool import BaseSmartTool


class TestEngineStub(BaseSmartTool):
    """Stub implementation for testing BaseSmartTool"""
    
    async def execute(self, **kwargs):
        return {"result": "test"}
    
    def get_routing_strategy(self, **kwargs):
        return {"engines": ["test_engine"]}


class TestRetryLogic(unittest.TestCase):
    """Test suite for _execute_engine_with_retry method"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engines = {"test_engine": AsyncMock()}
        self.tool = TestEngineStub(self.engines)
        # Set retry configuration for testing
        self.tool._max_retries = 3
        self.tool._base_retry_delay = 0.01  # Short delays for testing
        self.tool._max_retry_delay = 0.1
    
    def tearDown(self):
        """Clean up after tests"""
        self.tool = None
    
    async def async_test(self, coro):
        """Helper to run async tests"""
        return await coro
    
    def test_successful_execution_first_attempt(self):
        """Test successful execution on first attempt"""
        async def test():
            # Setup - Create engine without execute method (direct callable)
            engine = AsyncMock(return_value="success")
            # Ensure it doesn't have an execute method
            if hasattr(engine, 'execute'):
                delattr(engine, 'execute')
            kwargs = {"test": "data"}
            
            # Execute
            result = await self.tool._execute_engine_with_retry(
                engine, "test_engine", kwargs
            )
            
            # Assert
            self.assertEqual(result, "success")
            engine.assert_called_once_with(**kwargs)
        
        asyncio.run(test())
    
    def test_rate_limit_retry_success(self):
        """Test retry on rate limit error with eventual success"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            engine.execute.side_effect = [
                Exception("Rate limited - too many requests"),
                Exception("API exhausted quota"),
                "success"
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute
                result = await self.tool._execute_engine_with_retry(
                    engine, "test_engine", {}
                )
                
                # Assert
                self.assertEqual(result, "success")
                self.assertEqual(engine.execute.call_count, 3)
                # Check that sleep was called with exponential backoff
                self.assertEqual(mock_sleep.call_count, 2)
                
                # Verify exponential backoff pattern
                calls = mock_sleep.call_args_list
                first_delay = calls[0][0][0]
                second_delay = calls[1][0][0]
                # Second delay should be roughly double the first (plus jitter)
                # Or capped at max_retry_delay if exceeded
                if second_delay < self.tool._max_retry_delay:
                    self.assertGreater(second_delay, first_delay)
                else:
                    self.assertLessEqual(second_delay, self.tool._max_retry_delay)
        
        asyncio.run(test())
    
    def test_max_retries_exceeded(self):
        """Test that max retries is respected and final error is raised"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            rate_limit_error = Exception("Rate limited continuously")
            engine.execute.side_effect = [rate_limit_error] * 5  # More than max retries
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute and expect exception
                with self.assertRaises(Exception) as context:
                    await self.tool._execute_engine_with_retry(
                        engine, "test_engine", {}
                    )
                
                # Assert
                self.assertEqual(str(context.exception), "Rate limited continuously")
                # Should attempt max_retries + 1 times (initial + retries)
                self.assertEqual(engine.execute.call_count, 4)
                self.assertEqual(mock_sleep.call_count, 3)
        
        asyncio.run(test())
    
    def test_transient_error_retry(self):
        """Test retry on transient errors (timeout, connection)"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            engine.execute.side_effect = [
                TimeoutError("Connection timeout"),
                ConnectionError("Network error"),
                "success"
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute
                result = await self.tool._execute_engine_with_retry(
                    engine, "test_engine", {}
                )
                
                # Assert
                self.assertEqual(result, "success")
                self.assertEqual(engine.execute.call_count, 3)
        
        asyncio.run(test())
    
    def test_server_error_retry(self):
        """Test retry on server errors (500, 502, 503, 504)"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            engine.execute.side_effect = [
                Exception("Server error 500"),
                Exception("Bad gateway 502"),
                Exception("Service unavailable 503"),
                "success"
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute
                result = await self.tool._execute_engine_with_retry(
                    engine, "test_engine", {}
                )
                
                # Assert
                self.assertEqual(result, "success")
                self.assertEqual(engine.execute.call_count, 4)
        
        asyncio.run(test())
    
    def test_non_retryable_error(self):
        """Test that non-retryable errors are raised immediately"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            non_retryable_error = ValueError("Invalid parameter")
            engine.execute.side_effect = non_retryable_error
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute and expect immediate failure
                with self.assertRaises(ValueError) as context:
                    await self.tool._execute_engine_with_retry(
                        engine, "test_engine", {}
                    )
                
                # Assert
                self.assertEqual(str(context.exception), "Invalid parameter")
                engine.execute.assert_called_once()
                mock_sleep.assert_not_called()
        
        asyncio.run(test())
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff with jitter calculation"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            engine.execute.side_effect = [
                Exception("Rate limited"),
                Exception("Rate limited"),
                Exception("Rate limited"),
                "success"
            ]
            
            sleep_calls = []
            
            async def mock_sleep(delay):
                sleep_calls.append(delay)
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                # Execute
                result = await self.tool._execute_engine_with_retry(
                    engine, "test_engine", {}
                )
                
                # Assert exponential pattern (base * 2^attempt + jitter)
                self.assertEqual(len(sleep_calls), 3)
                
                # First retry: ~0.01 * 2^0 = 0.01 + jitter
                self.assertGreaterEqual(sleep_calls[0], 0.01)
                self.assertLessEqual(sleep_calls[0], 0.01 + 0.5)
                
                # Second retry: ~0.01 * 2^1 = 0.02 + jitter
                self.assertGreaterEqual(sleep_calls[1], 0.02)
                self.assertLessEqual(sleep_calls[1], 0.02 + 0.5)
                
                # Third retry: ~0.01 * 2^2 = 0.04 + jitter
                self.assertGreaterEqual(sleep_calls[2], 0.04)
                self.assertLessEqual(sleep_calls[2], 0.04 + 0.5)
        
        asyncio.run(test())
    
    def test_max_delay_cap(self):
        """Test that retry delay is capped at max_retry_delay"""
        async def test():
            # Setup with low max delay
            self.tool._max_retry_delay = 0.05
            
            engine = Mock()
            engine.execute = AsyncMock()
            # Many failures to trigger high exponential backoff
            engine.execute.side_effect = [Exception("Rate limited")] * 3 + ["success"]
            
            sleep_calls = []
            
            async def mock_sleep(delay):
                sleep_calls.append(delay)
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                # Execute
                await self.tool._execute_engine_with_retry(
                    engine, "test_engine", {}
                )
                
                # Assert all delays are capped
                for delay in sleep_calls:
                    self.assertLessEqual(delay, self.tool._max_retry_delay)
        
        asyncio.run(test())
    
    def test_engine_with_execute_method(self):
        """Test engine that has an execute method (wrapper pattern)"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock(return_value="wrapped_success")
            
            # Execute
            result = await self.tool._execute_engine_with_retry(
                engine, "test_engine", {"param": "value"}
            )
            
            # Assert
            self.assertEqual(result, "wrapped_success")
            engine.execute.assert_called_once_with(param="value")
        
        asyncio.run(test())
    
    def test_engine_direct_callable(self):
        """Test engine that is directly callable (function)"""
        async def test():
            # Setup - Create a callable without execute method
            async def engine_func(**kwargs):
                return "direct_success"
            
            # Execute
            result = await self.tool._execute_engine_with_retry(
                engine_func, "test_engine", {"param": "value"}
            )
            
            # Assert
            self.assertEqual(result, "direct_success")
        
        asyncio.run(test())
    
    def test_mixed_error_types(self):
        """Test handling of mixed error types in retry sequence"""
        async def test():
            # Setup
            engine = Mock()
            engine.execute = AsyncMock()
            engine.execute.side_effect = [
                Exception("Rate limited"),           # Retryable
                ValueError("Bad input"),             # Non-retryable
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.return_value = None
                
                # Execute and expect ValueError to be raised
                with self.assertRaises(ValueError) as context:
                    await self.tool._execute_engine_with_retry(
                        engine, "test_engine", {}
                    )
                
                # Assert
                self.assertEqual(str(context.exception), "Bad input")
                self.assertEqual(engine.execute.call_count, 2)
                # Should have slept once after first rate limit error
                self.assertEqual(mock_sleep.call_count, 1)
        
        asyncio.run(test())
    
    def test_environment_variable_configuration(self):
        """Test that retry parameters can be configured via environment variables"""
        async def test():
            # Setup
            with patch.dict(os.environ, {
                'ENGINE_MAX_RETRIES': '5',
                'ENGINE_BASE_RETRY_DELAY': '2.0',
                'ENGINE_MAX_RETRY_DELAY': '60.0'
            }):
                # Create new tool instance to pick up env vars
                tool = TestEngineStub(self.engines)
                
                # Assert configuration was loaded
                self.assertEqual(tool._max_retries, 5)
                self.assertEqual(tool._base_retry_delay, 2.0)
                self.assertEqual(tool._max_retry_delay, 60.0)
        
        asyncio.run(test())


if __name__ == '__main__':
    unittest.main()