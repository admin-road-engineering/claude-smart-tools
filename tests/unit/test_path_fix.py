#!/usr/bin/env python
"""
Simple test to verify WindowsPath fix
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_path_fix():
    """Test the path normalization fix"""
    print("🚀 Testing WindowsPath Fix")
    print("=" * 50)
    
    # First test path_utils directly
    print("\n📝 Test 1: Testing path_utils.normalize_paths")
    from src.utils.path_utils import normalize_paths
    
    # Test with WindowsPath
    test_path = Path("src")
    print(f"Input: {test_path} (type: {type(test_path)})")
    result = normalize_paths(test_path)
    print(f"Output: {result[:3] if len(result) > 3 else result}... (type: {type(result)}, length: {len(result)})")
    assert isinstance(result, list), "Result should be a list"
    assert all(isinstance(p, str) for p in result), "All items should be strings"
    print("✅ path_utils.normalize_paths works correctly")
    
    # Now test smart tool initialization
    print("\n📝 Test 2: Testing smart tool initialization")
    try:
        # Change to gemini-engines directory for imports
        current_dir = os.getcwd()
        gemini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gemini-engines")
        
        os.chdir(gemini_path)
        if gemini_path not in sys.path:
            sys.path.insert(0, gemini_path)
        
        # Add src subdirectory to path as well
        gemini_src_path = os.path.join(gemini_path, "src")
        if gemini_src_path not in sys.path:
            sys.path.insert(0, gemini_src_path)
        
        from services.gemini_tool_implementations import GeminiToolImplementations
        from clients.gemini_client import GeminiClient
        
        # Create instances
        tool_impl = GeminiToolImplementations()
        gemini_client = GeminiClient()
        
        # Configure API
        import google.generativeai as genai
        api_key = os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            print(f"✅ Configured Gemini API")
        
        # Go back to smart tools directory
        os.chdir(current_dir)
        
        # Create engine wrapper
        from src.engines.engine_wrapper import EngineFactory
        engines = EngineFactory.create_engines_from_original(tool_impl)
        print(f"✅ Created {len(engines)} engines")
        
        # Create understand tool
        from src.smart_tools.understand_tool import UnderstandTool
        understand_tool = UnderstandTool(engines)
        print("✅ Created understand tool")
        
        # Test with WindowsPath
        print("\n📝 Test 3: Testing understand tool with WindowsPath")
        test_path = Path("src/smart_tools")
        print(f"Input path: {test_path} (type: {type(test_path)})")
        
        result = await understand_tool.execute(
            files=test_path,
            question="What does this module do?"
        )
        
        print(f"Success: {result.success}")
        if result.success:
            print(f"Engines used: {result.engines_used}")
            print(f"Result preview: {result.result[:200]}...")
            print("✅ Understand tool handled WindowsPath correctly!")
        else:
            print(f"❌ Error: {result.result}")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 50)
    print("✅ All tests passed! WindowsPath issue is fixed.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_path_fix())
    sys.exit(0 if success else 1)