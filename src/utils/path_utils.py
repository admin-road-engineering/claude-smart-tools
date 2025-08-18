"""
Universal path normalization utilities for Smart Tools and Gemini Engines
Resolves the WindowsPath object is not iterable error across all tools
"""
import os
import logging
from pathlib import Path
from typing import List, Union, Any

logger = logging.getLogger(__name__)


def normalize_paths(paths_input: Any) -> List[str]:
    """
    Universal path normalization that handles all path input types
    
    Args:
        paths_input: Can be:
            - A single string path
            - A single Path object (file or directory)  
            - A list of string paths
            - A list of Path objects
            - None or empty
            
    Returns:
        List of string paths that engines can iterate over safely
    """
    # Handle None or empty input
    if not paths_input:
        return []
    
    # If it's already a list, process each item
    if isinstance(paths_input, (list, tuple)):
        normalized_paths = []
        for path_item in paths_input:
            normalized_paths.extend(normalize_single_path(path_item))
        return normalized_paths
    
    # If it's a single item, normalize it
    return normalize_single_path(paths_input)


def normalize_single_path(path_input: Any) -> List[str]:
    """
    Normalize a single path input (string or Path object) to a list of string paths
    
    Args:
        path_input: Single path as string, Path object, or other type
        
    Returns:
        List of string paths (single file = 1-item list, directory = multiple files)
    """
    # Convert to Path object if it's a string
    if isinstance(path_input, str):
        path_obj = Path(path_input)
    elif hasattr(path_input, '__fspath__') or isinstance(path_input, Path):
        path_obj = Path(path_input)
    else:
        # If it's already a string path or unknown type, return as-is in a list
        logger.warning(f"Unknown path type {type(path_input)}, treating as string: {path_input}")
        return [str(path_input)]
    
    # CRITICAL FIX: Convert to absolute path to handle working directory changes
    # This ensures paths remain valid even when engines change working directory
    try:
        path_obj = path_obj.resolve()
        logger.debug(f"Resolved path to absolute: {path_obj}")
    except Exception as e:
        logger.warning(f"Could not resolve path {path_obj}: {e}")
        # Continue with original path
    
    # Check if path exists
    if not path_obj.exists():
        logger.warning(f"Path does not exist: {path_obj}")
        return [str(path_obj)]  # Return as-is, let engine handle the error
    
    # If it's a file, return it as a single-item list
    if path_obj.is_file():
        return [str(path_obj)]
    
    # If it's a directory, find all relevant files
    if path_obj.is_dir():
        return get_files_from_directory(path_obj)
    
    # For any other path type, return as string
    return [str(path_obj)]


def get_files_from_directory(directory_path: Path) -> List[str]:
    """
    Get all relevant code files from a directory recursively
    
    Args:
        directory_path: Path object pointing to a directory
        
    Returns:
        List of string file paths found in the directory
    """
    # Define common code file extensions to look for
    code_extensions = [
        # Programming languages
        '*.py', '*.js', '*.ts', '*.tsx', '*.jsx', '*.java', '*.cpp', '*.c', '*.cs', 
        '*.go', '*.rs', '*.rb', '*.php', '*.swift', '*.kt', '*.scala', '*.clj',
        '*.pl', '*.sh', '*.bash', '*.ps1', '*.bat', '*.cmd',
        
        # Configuration and data files
        '*.json', '*.yaml', '*.yml', '*.toml', '*.ini', '*.cfg', '*.conf',
        '*.xml', '*.html', '*.css', '*.scss', '*.less',
        
        # Database and SQL files
        '*.sql', '*.ddl', '*.dml',
        
        # Documentation files
        '*.md', '*.rst', '*.txt', '*.adoc',
        
        # Build and project files
        '*.gradle', '*.sbt', '*.pom', '*.mvn', '*.make', '*.cmake',
        'Dockerfile*', 'docker-compose*', '*.dockerignore',
        'package.json', 'requirements.txt', 'Pipfile', 'setup.py', 'pyproject.toml',
        '*.csproj', '*.vbproj', '*.fsproj', '*.sln',
        '*.gemspec', 'Gemfile', 'Rakefile',
        'build.gradle', 'settings.gradle',
        'pom.xml', 'build.xml'
    ]
    
    found_files = []
    
    try:
        # Use rglob to recursively find files matching each pattern
        for extension in code_extensions:
            matching_files = directory_path.rglob(extension)
            for file_path in matching_files:
                if file_path.is_file():
                    # Convert to absolute path to handle working directory changes
                    absolute_path = str(file_path.resolve())
                    found_files.append(absolute_path)
        
        # Remove duplicates and sort for consistent ordering
        unique_files = sorted(list(set(found_files)))
        
        # Log the discovery
        logger.info(f"Found {len(unique_files)} code files in directory: {directory_path}")
        
        # If no code files found, return the directory path itself
        # Some engines might be able to handle directories directly
        if not unique_files:
            logger.info(f"No code files found in directory: {directory_path}, returning directory path")
            return [str(directory_path)]
        
        return unique_files
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory_path}: {e}")
        # Return directory path as fallback
        return [str(directory_path)]


def safe_path_iteration(paths_input: Any):
    """
    Context manager for safe path iteration
    Ensures paths are always iterable regardless of input type
    
    Usage:
        for file_path in safe_path_iteration(paths):
            # file_path is always a string, paths is always iterable
            process_file(file_path)
    """
    return normalize_paths(paths_input)


# Backward compatibility aliases
normalize_path = normalize_paths  # For single path normalization
resolve_paths = normalize_paths   # Alternative name