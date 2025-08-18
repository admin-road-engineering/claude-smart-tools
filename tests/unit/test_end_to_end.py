#!/usr/bin/env python
"""
End-to-end test of Smart Tools system
Tests API keys, gemini-engines, and smart tools
"""

import os
import sys
import asyncio
import traceback
from datetime import datetime

# Add paths
sys.path.insert(0, 'src')
sys.path.insert(0, 'gemini-engines/src')

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

async def test_environment():
    """Test 1: Environment Variables"""
    print_section("TEST 1: Environment Variables")
    
    api_key1 = os.environ.get('GOOGLE_API_KEY')
    api_key2 = os.environ.get('GOOGLE_API_KEY2')
    
    print(f"GOOGLE_API_KEY: {'✅ SET' if api_key1 else '❌ NOT SET'}")
    print(f"GOOGLE_API_KEY2: {'✅ SET' if api_key2 else '❌ NOT SET'}")
    
    if api_key1:
        print(f"  Key 1 prefix: {api_key1[:15]}...")
    if api_key2:
        print(f"  Key 2 prefix: {api_key2[:15]}...")
    
    return bool(api_key1 or api_key2)

async def test_direct_gemini_api():
    """Test 2: Direct Gemini API Call"""
    print_section("TEST 2: Direct Gemini API Call")
    
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            print("❌ No API key available")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content('Reply with exactly: "API WORKING"')
        result = response.text.strip()
        
        if "API WORKING" in result.upper():
            print(f"✅ Direct API call successful")
            print(f"  Response: {result}")
            return True
        else:
            print(f"❌ Unexpected response: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Direct API call failed: {e}")
        return False

async def test_gemini_engines_config():
    """Test 3: Gemini Engines Configuration"""
    print_section("TEST 3: Gemini Engines Configuration")
    
    try:
        # Change to gemini-engines directory
        original_cwd = os.getcwd()
        os.chdir('gemini-engines')
        sys.path.insert(0, os.getcwd())
        
        from src.config import config
        from src.clients.gemini_client import GeminiClient
        
        print(f"Config loaded: ✅")
        print(f"  API Key 1: {'✅ SET' if config.google_api_key else '❌ NOT SET'}")
        print(f"  API Key 2: {'✅ SET' if config.google_api_key2 else '❌ NOT SET'}")
        
        # Test client initialization
        client = GeminiClient()
        print(f"GeminiClient initialized: ✅")
        print(f"  Models available: {list(client.models.keys())}")
        
        os.chdir(original_cwd)
        return True
        
    except Exception as e:
        print(f"❌ Gemini engines config failed: {e}")
        traceback.print_exc()
        os.chdir(original_cwd)
        return False

async def test_gemini_tool_implementation():
    """Test 4: Gemini Tool Implementation"""
    print_section("TEST 4: Gemini Tool Implementation (analyze_code)")
    
    try:
        original_cwd = os.getcwd()
        os.chdir('gemini-engines')
        sys.path.insert(0, os.getcwd())
        
        from src.services.gemini_tool_implementations import GeminiToolImplementations
        
        tool_impl = GeminiToolImplementations()
        print("GeminiToolImplementations initialized: ✅")
        
        # Test analyze_code with a simple file
        test_file = os.path.join(original_cwd, "src/smart_tools/base_smart_tool.py")
        
        print(f"Testing analyze_code on: {test_file}")
        result = await tool_impl.analyze_code(
            paths=[test_file],
            analysis_type="overview",
            question="What does this file do?"
        )
        
        if result and len(result) > 50:
            print(f"✅ analyze_code returned result ({len(result)} chars)")
            print(f"  Result preview: {result[:100]}...")
            os.chdir(original_cwd)
            return True
        else:
            print(f"❌ analyze_code returned insufficient result")
            os.chdir(original_cwd)
            return False
            
    except Exception as e:
        print(f"❌ Tool implementation failed: {e}")
        traceback.print_exc()
        os.chdir(original_cwd)
        return False

async def test_smart_tools_adapter():
    """Test 5: Smart Tools Original Adapter"""
    print_section("TEST 5: Smart Tools Original Adapter")
    
    try:
        from engines.original_tool_adapter import OriginalToolAdapter
        
        # Import tools
        tool_impl, client, config = OriginalToolAdapter.import_original_implementations()
        
        if tool_impl:
            print("✅ Original tools imported successfully")
            
            # Create engine wrappers
            engines = OriginalToolAdapter.create_engine_wrappers()
            print(f"✅ Created {len(engines)} engine wrappers")
            print(f"  Engines: {list(engines.keys())[:5]}...")
            
            return True
        else:
            print("❌ Failed to import original tools")
            return False
            
    except Exception as e:
        print(f"❌ Smart tools adapter failed: {e}")
        traceback.print_exc()
        return False

async def test_understand_tool():
    """Test 6: Understand Smart Tool"""
    print_section("TEST 6: Understand Smart Tool")
    
    try:
        from smart_tools.understand_tool import UnderstandTool
        from engines.original_tool_adapter import OriginalToolAdapter
        
        # Get engines
        engines = OriginalToolAdapter.create_engine_wrappers()
        
        # Create understand tool
        understand = UnderstandTool(engines)
        print("✅ UnderstandTool created")
        
        # Test execution
        result = await understand.execute(
            files=["src/smart_tools/base_smart_tool.py"],
            question="What is the purpose of this file?",
            focus="architecture"
        )
        
        if result.success:
            print(f"✅ UnderstandTool execution successful")
            print(f"  Engines used: {result.engines_used}")
            print(f"  Result length: {len(result.result)} chars")
            return True
        else:
            print(f"❌ UnderstandTool execution failed")
            print(f"  Error: {result.result}")
            return False
            
    except Exception as e:
        print(f"❌ UnderstandTool test failed: {e}")
        traceback.print_exc()
        return False

async def test_mcp_tools():
    """Test 7: MCP Smart Tools (if available)"""
    print_section("TEST 7: MCP Smart Tools")
    
    print("⚠️  MCP tools can only be tested through Claude Desktop")
    print("   Please test manually using: mcp__claude-smart-tools__understand")
    return None

async def main():
    """Run all tests"""
    print("\n" + "🚀" * 35)
    print("     SMART TOOLS END-TO-END TEST SUITE")
    print("🚀" * 35)
    print(f"\nTest started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run tests
    results['environment'] = await test_environment()
    results['direct_api'] = await test_direct_gemini_api()
    results['engines_config'] = await test_gemini_engines_config()
    results['tool_implementation'] = await test_gemini_tool_implementation()
    results['adapter'] = await test_smart_tools_adapter()
    results['understand_tool'] = await test_understand_tool()
    results['mcp'] = await test_mcp_tools()
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test, result in results.items():
        status = "✅ PASS" if result is True else ("❌ FAIL" if result is False else "⚠️  SKIP")
        print(f"{status} - {test}")
    
    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Smart Tools system is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")

if __name__ == "__main__":
    asyncio.run(main())