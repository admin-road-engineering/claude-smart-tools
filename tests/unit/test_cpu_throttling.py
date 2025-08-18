#!/usr/bin/env python3
"""
Test script to validate CPU throttling integration
"""
import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_cpu_throttling():
    """Test CPU throttling functionality"""
    try:
        from src.services.cpu_throttler import CPUThrottler, get_cpu_throttler
        from src.config import config
        
        print("🔧 Testing CPU Throttling Integration")
        print("=" * 50)
        
        # Test 1: Initialize CPU throttler
        print("1. Initializing CPU throttler...")
        throttler = CPUThrottler.get_instance(config)
        if throttler:
            print(f"   ✅ CPU throttler initialized successfully")
            print(f"   📊 Max CPU: {throttler.max_cpu_percent}%")
            print(f"   ⏱️  Yield interval: {throttler.yield_interval_ms}ms")
        else:
            print("   ❌ Failed to initialize CPU throttler")
            return False
        
        # Test 2: Test singleton pattern
        print("\n2. Testing singleton pattern...")
        throttler2 = CPUThrottler.get_instance()
        if throttler is throttler2:
            print("   ✅ Singleton pattern working correctly")
        else:
            print("   ❌ Singleton pattern failed")
            return False
        
        # Test 3: Test CPU monitoring
        print("\n3. Testing CPU monitoring...")
        cpu_usage = throttler._get_cpu_usage()
        print(f"   📈 Current CPU usage: {cpu_usage:.1f}%")
        
        # Test 4: Test yielding functionality
        print("\n4. Testing yield functionality...")
        should_yield = await throttler.should_yield()
        print(f"   🔄 Should yield: {should_yield}")
        
        await throttler.yield_if_needed()
        print("   ✅ Yield operation completed")
        
        # Test 5: Test throttling stats
        print("\n5. Testing throttling stats...")
        stats = throttler.get_throttling_stats()
        print(f"   📊 Throttle active: {stats['throttle_active']}")
        print(f"   📊 Last CPU usage: {stats['last_cpu_usage']:.1f}%")
        print(f"   📊 Singleton initialized: {stats['singleton_initialized']}")
        
        # Test 6: Test get_cpu_throttler convenience function
        print("\n6. Testing convenience function...")
        throttler3 = get_cpu_throttler()
        if throttler3 is throttler:
            print("   ✅ Convenience function working correctly")
        else:
            print("   ❌ Convenience function failed")
            return False
        
        print("\n🎉 All CPU throttling tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ CPU throttling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_smart_tools_integration():
    """Test smart tools integration with CPU throttling"""
    try:
        print("\n\n🛠️  Testing Smart Tools Integration")
        print("=" * 50)
        
        # Test importing base smart tool
        from src.smart_tools.base_smart_tool import BaseSmartTool
        print("1. ✅ BaseSmartTool imported successfully")
        
        # Test importing MCP server
        from src.smart_mcp_server import SmartToolsMcpServer
        print("2. ✅ SmartToolsMcpServer imported successfully")
        
        # Test server initialization (without actually running)
        print("3. Testing server initialization...")
        server = SmartToolsMcpServer()
        if server.cpu_throttler:
            print("   ✅ MCP server initialized with CPU throttling")
        else:
            print("   ⚠️  MCP server initialized without CPU throttling")
        
        print("\n🎉 Smart tools integration test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Smart tools integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting CPU Throttling Validation Tests")
    print("=" * 60)
    
    # Test CPU throttling core functionality
    cpu_test_passed = await test_cpu_throttling()
    
    # Test smart tools integration
    integration_test_passed = await test_smart_tools_integration()
    
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print(f"CPU Throttling: {'✅ PASSED' if cpu_test_passed else '❌ FAILED'}")
    print(f"Smart Tools Integration: {'✅ PASSED' if integration_test_passed else '❌ FAILED'}")
    
    if cpu_test_passed and integration_test_passed:
        print("\n🎉 ALL TESTS PASSED - CPU throttling is ready for use!")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED - Review implementation")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)