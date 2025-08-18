#!/usr/bin/env python
"""Simplified test to demonstrate result truncation in smart tools"""
import asyncio
import sys
import os

async def test_truncation():
    """Compare direct Gemini output vs smart tool output"""
    
    # Test files
    test_files = ["C:\\Users\\Admin\\claude-smart-tools\\src\\smart_tools"]
    
    print("=" * 80)
    print("TEST: Result Truncation Analysis")
    print("=" * 80)
    
    # Setup paths
    original_dir = os.getcwd()
    gemini_path = os.path.join(original_dir, 'gemini-engines')
    
    # 1. Direct Gemini call to get full result
    print("\n1. Getting direct Gemini result...")
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
    
    print(f"   Direct result length: {len(str(direct_result))} characters")
    
    # 2. Simulate what the smart tool synthesis does
    print("\n2. What happens in smart tool synthesis...")
    
    # This is what happens in investigate_tool._synthesize_investigation
    truncated_1000 = str(direct_result)[:1000] + "..." if len(str(direct_result)) > 1000 else str(direct_result)
    print(f"   After 1000 char truncation: {len(truncated_1000)} characters")
    
    # This is what happens in full_analysis_tool._synthesize_comprehensive_analysis  
    truncated_1500 = str(direct_result)[:1500] + "..." if len(str(direct_result)) > 1500 else str(direct_result)
    print(f"   After 1500 char truncation: {len(truncated_1500)} characters")
    
    truncated_2000 = str(direct_result)[:2000] + "..." if len(str(direct_result)) > 2000 else str(direct_result)
    print(f"   After 2000 char truncation: {len(truncated_2000)} characters")
    
    # 3. Calculate data loss
    print("\n3. Data Loss Analysis")
    print("=" * 80)
    original_len = len(str(direct_result))
    
    print(f"Original Gemini result: {original_len} characters")
    print(f"After 1000 char limit: {len(truncated_1000)} chars - Lost {original_len - len(truncated_1000)} chars ({(original_len - len(truncated_1000))/original_len*100:.1f}%)")
    print(f"After 1500 char limit: {len(truncated_1500)} chars - Lost {original_len - len(truncated_1500)} chars ({(original_len - len(truncated_1500))/original_len*100:.1f}%)")
    print(f"After 2000 char limit: {len(truncated_2000)} chars - Lost {original_len - len(truncated_2000)} chars ({(original_len - len(truncated_2000))/original_len*100:.1f}%)")
    
    print("\n4. Sample of Lost Content")
    print("=" * 80)
    print("Content from position 2000-2500 (would be lost with 2000 char limit):")
    print("-" * 40)
    print(str(direct_result)[2000:2500])
    print("-" * 40)
    
    print("\nContent from position 5000-5500 (lost with all current limits):")
    print("-" * 40)
    print(str(direct_result)[5000:5500])
    print("-" * 40)
    
    # Return to original directory
    os.chdir(original_dir)

if __name__ == "__main__":
    asyncio.run(test_truncation())