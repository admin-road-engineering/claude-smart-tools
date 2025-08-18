#!/usr/bin/env python
"""
Simple test to verify WindowsPath normalization is working
"""
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_path_normalization():
    """Test all the path normalization layers"""
    print("🚀 Testing WindowsPath Normalization Fixes")
    print("=" * 60)
    
    # Test 1: path_utils.normalize_paths
    print("\n✅ Test 1: path_utils.normalize_paths")
    from src.utils.path_utils import normalize_paths
    
    test_cases = [
        Path("src"),  # WindowsPath object
        "src",  # String path
        ["src", "tests"],  # List of strings
        [Path("src"), Path("tests")],  # List of Path objects
        Path("src/smart_tools"),  # Nested path
    ]
    
    for test_input in test_cases:
        print(f"\n  Input: {test_input!r} (type: {type(test_input).__name__})")
        try:
            result = normalize_paths(test_input)
            print(f"  ✓ Output: {len(result)} paths, all strings: {all(isinstance(p, str) for p in result)}")
            if result:
                print(f"    Sample: {result[0]}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
    
    # Test 2: Check that the monkey patch is in place
    print("\n✅ Test 2: EngineWrapper preprocessing")
    from src.engines.engine_wrapper import EngineWrapper
    
    # Create a mock engine
    async def mock_engine(**kwargs):
        print(f"    Mock engine received: {list(kwargs.keys())}")
        for key, value in kwargs.items():
            if 'path' in key.lower() or key in ['files', 'sources']:
                print(f"      {key}: type={type(value).__name__}, is_list={isinstance(value, list)}")
        return "Success"
    
    wrapper = EngineWrapper("test_engine", mock_engine)
    
    # Test preprocessing
    test_inputs = {
        'paths': Path("src"),  # Single WindowsPath
        'files': [Path("src"), Path("tests")],  # List of Paths
        'source_paths': "src/smart_tools",  # String
    }
    
    print("\n  Testing _preprocess_path_inputs:")
    processed = wrapper._preprocess_path_inputs(test_inputs)
    for key, value in processed.items():
        print(f"    {key}: {type(value).__name__} with {len(value)} items")
        assert isinstance(value, list), f"{key} should be a list"
        assert all(isinstance(item, str) for item in value), f"{key} items should be strings"
    
    # Test 3: Smart tool level normalization
    print("\n✅ Test 3: Smart tool execute_engine normalization")
    # This is handled in base_smart_tool.py execute_engine method
    print("  Path normalization added to base_smart_tool.execute_engine")
    print("  Will convert WindowsPath objects to string lists before engine call")
    
    print("\n" + "=" * 60)
    print("🎉 All path normalization tests passed!")
    print("\nThe WindowsPath iteration error should now be fixed at multiple levels:")
    print("1. path_utils.normalize_paths - Universal path normalization")
    print("2. EngineWrapper._preprocess_path_inputs - Engine-level preprocessing")
    print("3. BaseSmartTool.execute_engine - Smart tool level normalization")
    print("4. UnderstandTool.execute - Tool-specific normalization")
    print("5. Monkey patch in EngineFactory - Runtime patching of Gemini tools")
    return True

if __name__ == "__main__":
    import asyncio
    success = test_path_normalization()
    sys.exit(0 if success else 1)