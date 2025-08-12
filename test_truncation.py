#!/usr/bin/env python
"""Test to demonstrate result truncation in smart tools"""
import asyncio
import sys
import os

# Add paths
sys.path.insert(0, 'src')
sys.path.insert(0, 'gemini-engines')

async def test_direct_vs_smart():
    """Compare direct Gemini tool output vs smart tool output"""
    
    # Test files
    test_files = ["C:\\Users\\Admin\\claude-smart-tools\\src\\smart_tools"]
    
    # 1. Direct Gemini tool call
    print("=" * 80)
    print("1. DIRECT GEMINI TOOL CALL (analyze_code)")
    print("=" * 80)
    
    # Save current directory
    original_dir = os.getcwd()
    
    # Change to gemini-engines for proper context
    gemini_path = os.path.join(os.getcwd(), 'gemini-engines')
    os.chdir(gemini_path)
    sys.path.insert(0, gemini_path)
    
    from src.services.gemini_tool_implementations import GeminiToolImplementations
    
    tool_impl = GeminiToolImplementations()
    direct_result = await tool_impl.analyze_code(
        paths=test_files,
        analysis_type="architecture",
        question="How do the smart tools work?",
        verbose=True
    )
    
    print(f"Direct result length: {len(str(direct_result))} characters")
    print(f"First 500 chars: {str(direct_result)[:500]}...")
    print(f"Last 500 chars: ...{str(direct_result)[-500:]}")
    
    # 2. Smart tool call
    print("\n" + "=" * 80)
    print("2. SMART TOOL CALL (understand)")
    print("=" * 80)
    
    # Change back to original directory
    os.chdir(original_dir)
    sys.path.insert(0, 'src')
    from smart_mcp_server import SmartToolsMcpServer
    
    server = SmartToolsMcpServer()
    await server.initialize_engines()
    
    understand_tool = server.smart_tools.get('understand')
    if understand_tool:
        smart_result = await understand_tool.execute(
            files=test_files,
            question="How do the smart tools work?"
        )
        
        print(f"Smart tool result length: {len(smart_result.result)} characters")
        print(f"Success: {smart_result.success}")
        print(f"Engines used: {smart_result.engines_used}")
        
        # Check for truncation indicators
        truncation_count = smart_result.result.count("...")
        print(f"Truncation indicators ('...'): {truncation_count} occurrences")
        
        # Compare lengths
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        print(f"Direct Gemini result: {len(str(direct_result))} chars")
        print(f"Smart tool result: {len(smart_result.result)} chars")
        print(f"Data loss: {len(str(direct_result)) - len(smart_result.result)} chars ({((len(str(direct_result)) - len(smart_result.result)) / len(str(direct_result)) * 100):.1f}%)")
    else:
        print("Could not get understand tool")

if __name__ == "__main__":
    asyncio.run(test_direct_vs_smart())