"""
Patch to add the missing _collect_code_from_paths method to GeminiToolImplementations
This fixes the WindowsPath iteration error
"""
from pathlib import Path
from typing import List, Optional, Set
import logging

logger = logging.getLogger(__name__)

async def _collect_code_from_paths(self, paths: List[str], extensions: Optional[List[str]] = None) -> str:
    """
    Collect code content from specified paths (files or directories)
    Handles WindowsPath objects properly by ensuring paths is always iterable
    """
    # CRITICAL FIX: Ensure paths is always a list
    if not paths:
        return ""
    
    # Handle single path that might be a WindowsPath object
    if isinstance(paths, (str, Path)):
        paths = [str(paths)]
    elif not isinstance(paths, (list, tuple)):
        # Handle WindowsPath or other path-like objects
        paths = [str(paths)]
    else:
        # Ensure all items in the list are strings
        paths = [str(p) for p in paths]
    
    collected_content = []
    processed_files = set()
    
    # Default code extensions if not specified
    if extensions is None:
        extensions = [
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.cs',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj',
            '.sh', '.bash', '.ps1', '.bat', '.cmd',
            '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.xml', '.html', '.css', '.scss', '.less',
            '.sql', '.md', '.rst', '.txt'
        ]
    
    for path_str in paths:
        path = Path(path_str)
        
        if path.is_file():
            # Single file
            if any(path.suffix == ext for ext in extensions) or not extensions:
                if str(path) not in processed_files:
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            collected_content.append(f"### File: {path}\n```\n{content}\n```\n")
                            processed_files.add(str(path))
                    except Exception as e:
                        logger.warning(f"Could not read file {path}: {e}")
        
        elif path.is_dir():
            # Directory - collect all matching files
            for ext in extensions:
                for file_path in path.rglob(f"*{ext}"):
                    if str(file_path) not in processed_files:
                        try:
                            # Skip common non-code directories
                            skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                                       'dist', 'build', '.pytest_cache', '.mypy_cache'}
                            if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                                continue
                            
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                collected_content.append(f"### File: {file_path}\n```\n{content}\n```\n")
                                processed_files.add(str(file_path))
                        except Exception as e:
                            logger.warning(f"Could not read file {file_path}: {e}")
    
    return '\n\n'.join(collected_content)

# Monkey patch function to add this method to GeminiToolImplementations
def apply_collect_code_patch():
    """Apply the patch to add _collect_code_from_paths to GeminiToolImplementations"""
    from .gemini_tool_implementations import GeminiToolImplementations
    GeminiToolImplementations._collect_code_from_paths = _collect_code_from_paths
    logger.info("Applied _collect_code_from_paths patch to GeminiToolImplementations")