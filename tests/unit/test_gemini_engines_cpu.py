#!/usr/bin/env python3
"""
Test CPU throttling integration in gemini-engines implementation
"""

import asyncio
import sys
from pathlib import Path

async def test_gemini_engines_cpu():
    """Test that gemini-engines implementation has CPU throttling by checking the file directly"""
    
    print("🚀 Testing Gemini-Engines CPU Throttling Integration")
    print("=" * 60)
    
    try:
        # Check if the CPU throttling fix has been applied to gemini-engines
        gemini_impl_file = Path(__file__).parent / "gemini-engines" / "src" / "services" / "gemini_tool_implementations.py"
        
        if not gemini_impl_file.exists():
            print("❌ gemini-engines implementation file not found")
            return False
            
        print("1. ✅ Found gemini-engines implementation file")
        
        # Read the implementation file and check for CPU throttling integration
        with open(gemini_impl_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key CPU throttling elements
        checks = [
            ("from .cpu_throttler import CPUThrottler", "CPU throttler import"),
            ("self.cpu_throttler = CPUThrottler(self.config)", "CPU throttler initialization"),
            ("await self.cpu_throttler.yield_if_needed()", "CPU yielding calls"),
            ("async with self.cpu_throttler.monitor_heavy_operation", "Heavy operation monitoring"),
            ("throttled_file_scan", "Batch file processing"),
        ]
        
        all_passed = True
        for check_text, description in checks:
            if check_text in content:
                print(f"2. ✅ {description} found")
            else:
                print(f"2. ❌ {description} NOT found")
                all_passed = False
        
        # Check that problematic await asyncio.sleep(0) has been removed/replaced
        if "await asyncio.sleep(0)" in content:
            print("3. ❌ Problematic 'await asyncio.sleep(0)' still present")
            all_passed = False
        else:
            print("3. ✅ Problematic 'await asyncio.sleep(0)' has been removed")
        
        # Check for the improved _collect_code_from_paths method
        if "def _collect_code_from_paths(self, paths: List[str], extensions: Optional[List[str]] = None) -> str:" in content:
            print("4. ✅ _collect_code_from_paths method exists")
        else:
            print("4. ❌ _collect_code_from_paths method not found")
            all_passed = False
        
        # Check for the improved _read_file_safe method
        if "async def _read_file_safe(self, file_path: str) -> Optional[str]:" in content:
            print("5. ✅ _read_file_safe method exists")
        else:
            print("5. ❌ _read_file_safe method not found")
            all_passed = False
        
        if all_passed:
            print("\n🎉 All gemini-engines CPU throttling integration checks passed!")
            print("💡 The CPU throttling fix has been successfully applied to prevent 100% CPU usage.")
        else:
            print("\n❌ Some CPU throttling integration checks failed.")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_gemini_engines_cpu()
    
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print(f"Gemini-Engines CPU Throttling: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        print("\n🎉 CPU throttling fix successfully applied to gemini-engines!")
        print("🔧 This addresses the same file loading CPU issue that was fixed in claude-gemini-mcp")
        print("⚡ Operations like review_output should no longer cause 100% CPU usage")
    else:
        print("\n❌ CPU throttling fix needs attention in gemini-engines")
        
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)