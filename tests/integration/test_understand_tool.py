"""
Test script for the understand tool
"""
import asyncio
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from smart_tools.understand_tool import UnderstandTool
from engines.original_tool_adapter import OriginalToolAdapter


async def test_understand_tool():
    """Test the understand tool with mock engines"""
    
    print("🚀 Testing Smart Tools - Understand Tool")
    print("=" * 50)
    
    # Create engines
    print("📦 Creating engine wrappers...")
    engines = OriginalToolAdapter.create_engine_wrappers()
    print(f"✅ Created {len(engines)} engines: {list(engines.keys())}")
    
    # Create understand tool
    understand_tool = UnderstandTool(engines)
    
    # Test case 1: Basic understanding
    print("\n🔍 Test Case 1: Basic Understanding")
    print("-" * 30)
    
    test_files = ["src/smart_tools/understand_tool.py", "README.md"]
    
    result = await understand_tool.execute(
        files=test_files,
        question="How does the understand tool work?"
    )
    
    print(f"Success: {result.success}")
    print(f"Engines Used: {result.engines_used}")
    print(f"Routing Decision: {result.routing_decision}")
    print("\nResult:")
    print(result.result[:500] + "..." if len(result.result) > 500 else result.result)
    
    # Test case 2: Architecture focus
    print("\n\n🏗️ Test Case 2: Architecture Focus")
    print("-" * 30)
    
    result2 = await understand_tool.execute(
        files=["src/"],
        focus="architecture"
    )
    
    print(f"Success: {result2.success}")
    print(f"Engines Used: {result2.engines_used}")
    print(f"Routing Strategy: {result2.routing_decision}")
    
    # Test routing strategy
    print("\n\n🎯 Test Case 3: Routing Strategy")
    print("-" * 30)
    
    strategy = understand_tool.get_routing_strategy(
        files=["src/smart_tools/", "README.md", "docs/API.md"],
        question="How does routing work?"
    )
    
    print(f"Engines: {strategy['engines']}")
    print(f"Reasoning: {strategy['reasoning']}")
    print(f"Strategy: {strategy['strategy']}")
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_understand_tool())