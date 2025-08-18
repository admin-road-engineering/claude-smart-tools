#!/usr/bin/env python3
"""
Fix relative imports in smart tools for MCP server execution
"""
import os
import re
from pathlib import Path

def fix_relative_imports_in_file(file_path: Path):
    """Fix relative imports in a single Python file"""
    if not file_path.exists() or file_path.suffix != '.py':
        return
    
    print(f"Checking {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Add import fallback pattern for files that use relative imports
    if '..services.cpu_throttler' in content and 'import sys' not in content:
        # Add import handling for cpu_throttler
        pattern = r'from \.\.services\.cpu_throttler import ([^\n]+)'
        replacement = '''import sys
import os
try:
    from ..services.cpu_throttler import \\1
except ImportError:
    # Handle direct script execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from services.cpu_throttler import \\1'''
        
        content = re.sub(pattern, replacement, content)
        
    # Fix engine_wrapper relative import
    if 'from .engine_wrapper import' in content:
        content = content.replace(
            'from .engine_wrapper import EngineWrapper',
            '''try:
    from .engine_wrapper import EngineWrapper
except ImportError:
    from engine_wrapper import EngineWrapper'''
        )
    
    # Write back if changed
    if content != original_content:
        print(f"  → Fixed imports in {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

def main():
    """Fix all relative imports in the project"""
    src_dir = Path(__file__).parent / 'src'
    
    # Find all Python files that might need fixing
    python_files = list(src_dir.rglob('*.py'))
    
    for py_file in python_files:
        fix_relative_imports_in_file(py_file)
    
    print("Import fixes complete!")

if __name__ == "__main__":
    main()