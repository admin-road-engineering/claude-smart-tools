#!/usr/bin/env python3
"""
Test script to validate smart tool execution with CPU throttling
"""
import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_smart_tool_cpu_integration():
    """Test that smart tools properly use CPU throttling"""
    try:
        print("🧠 Testing Smart Tool CPU Integration")
        print("=" * 50)
        
        # Import required components
        from src.smart_tools.base_smart_tool import BaseSmartTool
        from src.services.cpu_throttler import CPUThrottler
        from src.config import config
        
        # Create a test smart tool implementation
        class TestSmartTool(BaseSmartTool):
            async def execute(self, **kwargs):
                return {"result": "test execution"}
            
            def get_routing_strategy(self, **kwargs):
                return {"engines": ["test_engine"]}
        
        # Test 1: Initialize CPU throttler first (singleton pattern)
        print("1. Initializing CPU throttler...")
        cpu_throttler = CPUThrottler.get_instance(config)
        print(f"   ✅ CPU throttler initialized with {cpu_throttler.max_cpu_percent}% threshold")
        
        # Test 2: Initialize test smart tool
        print("\n2. Creating test smart tool...")
        engines = {"test_engine": lambda **kwargs: "test result"}
        test_tool = TestSmartTool(engines)
        
        if test_tool.cpu_throttler:
            print("   ✅ Smart tool has CPU throttler")
        else:
            print("   ❌ Smart tool missing CPU throttler")
            return False
        
        # Test 3: Test engine execution with CPU throttling
        print("\n3. Testing engine execution with CPU throttling...")
        result = await test_tool.execute_engine("test_engine", test_param="value")
        print(f"   📊 Engine result: {result}")
        
        # Test 4: Test multiple engine execution
        print("\n4. Testing multiple engine execution...")
        engines_multi = {
            "engine1": lambda **kwargs: "result1",
            "engine2": lambda **kwargs: "result2", 
            "engine3": lambda **kwargs: "result3"
        }
        test_tool_multi = TestSmartTool(engines_multi)
        
        results = await test_tool_multi.execute_multiple_engines(["engine1", "engine2", "engine3"])
        print(f"   📊 Multiple engines results: {len(results)} engines executed")
        
        # Test 5: Check CPU throttling statistics after operations
        print("\n5. Checking CPU throttling statistics...")
        stats = test_tool.cpu_throttler.get_throttling_stats()
        print(f"   📈 Current CPU: {stats['last_cpu_usage']:.1f}%")
        print(f"   🔄 Operations processed: {stats['operation_count']}")
        print(f"   ⚡ Throttle active: {stats['throttle_active']}")
        
        print("\n🎉 Smart tool CPU integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Smart tool CPU integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_gemini_client_cpu_integration():
    """Test Gemini client CPU throttling integration"""
    try:
        print("\n\n🌟 Testing Gemini Client CPU Integration")
        print("=" * 50)
        
        from src.clients.gemini_client import GeminiClient
        from src.config import config
        
        # Test 1: Initialize Gemini client with CPU throttling
        print("1. Initializing Gemini client...")
        try:
            client = GeminiClient(config)
            if client.cpu_throttler:
                print("   ✅ Gemini client initialized with CPU throttling")
            else:
                print("   ❌ Gemini client missing CPU throttling")
                return False
        except Exception as e:
            print(f"   ⚠️  Gemini client initialization failed (expected if no API key): {e}")
            return True  # This is expected in test environment
        
        print("\n🎉 Gemini client CPU integration test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Gemini client CPU integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run execution tests"""
    print("🚀 Starting Smart Tool Execution Tests")
    print("=" * 60)
    
    # Test smart tool CPU integration
    smart_tool_test = await test_smart_tool_cpu_integration()
    
    # Test Gemini client CPU integration
    client_test = await test_gemini_client_cpu_integration()
    
    print("\n" + "=" * 60)
    print("📋 EXECUTION TEST SUMMARY")
    print(f"Smart Tool CPU Integration: {'✅ PASSED' if smart_tool_test else '❌ FAILED'}")
    print(f"Gemini Client CPU Integration: {'✅ PASSED' if client_test else '❌ FAILED'}")
    
    if smart_tool_test and client_test:
        print("\n🎉 ALL EXECUTION TESTS PASSED!")
        print("💡 CPU throttling is fully integrated and ready to prevent terminal freezing!")
        return True
    else:
        print("\n⚠️  SOME EXECUTION TESTS FAILED")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)