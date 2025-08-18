#!/usr/bin/env python
"""
Test script to verify the understand tool WindowsPath fix
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_understand_tool():
    """Test the understand tool with various path inputs"""
    try:
        # Import after path is set
        from src.smart_mcp_server import create_smart_tools
        
        print("🚀 Testing Understand Tool WindowsPath Fix")
        print("=" * 50)
        
        # Create smart tools
        print("Creating smart tools...")
        smart_tools = await create_smart_tools()
        understand_tool = smart_tools.get('understand')
        
        if not understand_tool:
            print("❌ Failed to create understand tool")
            return False
        
        print("✅ Understand tool created successfully")
        
        # Test 1: Single string path
        print("\n📝 Test 1: Single string path")
        result = await understand_tool.execute(
            files="src",
            question="What is the architecture?"
        )
        print(f"Result success: {result.success}")
        if not result.success:
            print(f"Error: {result.result[:200]}")
        
        # Test 2: WindowsPath object (the problematic case)
        print("\n📝 Test 2: WindowsPath object")
        path_obj = Path("src")
        result = await understand_tool.execute(
            files=path_obj,
            question="What is the architecture?"
        )
        print(f"Result success: {result.success}")
        if not result.success:
            print(f"Error: {result.result[:200]}")
        
        # Test 3: List of paths
        print("\n📝 Test 3: List of paths")
        result = await understand_tool.execute(
            files=["src/smart_tools", "src/engines"],
            question="How do smart tools work?"
        )
        print(f"Result success: {result.success}")
        if not result.success:
            print(f"Error: {result.result[:200]}")
        
        # Test 4: List with WindowsPath objects
        print("\n📝 Test 4: List with WindowsPath objects")
        result = await understand_tool.execute(
            files=[Path("src/smart_tools"), Path("src/engines")],
            question="How do smart tools work?"
        )
        print(f"Result success: {result.success}")
        if not result.success:
            print(f"Error: {result.result[:200]}")
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_understand_tool())
    sys.exit(0 if success else 1)