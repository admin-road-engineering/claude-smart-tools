#!/usr/bin/env python3
"""
Test script to verify path resolution works correctly when invoked from VENV
Run this from DEM Backend directory to test
"""

import os
import sys
from pathlib import Path

print("=" * 60)
print("PATH RESOLUTION TEST")
print("=" * 60)

# Show current context
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {__file__}")
print(f"Python executable: {sys.executable}")
print()

# Add Smart Tools to path
smart_tools_dir = Path(__file__).parent
sys.path.insert(0, str(smart_tools_dir / "src"))

# Import the path resolver
try:
    from services.path_resolver import PathResolver
    print("✅ Successfully imported PathResolver")
except ImportError as e:
    print(f"❌ Failed to import PathResolver: {e}")
    sys.exit(1)

# Test path resolution
resolver = PathResolver()

# Test files to resolve (adjust based on your DEM Backend structure)
test_paths = [
    "src/main.py",
    "main.py",
    "requirements.txt",
    "README.md",
    "./src/main.py"
]

print("\nTesting path resolution:")
print("-" * 40)

for test_path in test_paths:
    resolved_paths, messages = resolver.resolve_file_paths([test_path])
    
    if resolved_paths:
        print(f"✅ '{test_path}' -> {resolved_paths[0]}")
    else:
        print(f"❌ '{test_path}' -> Not found")
    
    for msg in messages:
        print(f"   {msg}")
    print()

# Test with absolute path
abs_test = Path.cwd() / "src" / "main.py"
if abs_test.exists():
    resolved_paths, messages = resolver.resolve_file_paths([str(abs_test)])
    print(f"Absolute path test: {abs_test}")
    if resolved_paths:
        print(f"✅ Resolved to: {resolved_paths[0]}")
    else:
        print("❌ Failed to resolve absolute path")

print("=" * 60)
print("PATH RESOLUTION TEST COMPLETE")
print("=" * 60)