"""
Universal path normalization utilities for Smart Tools and Gemini Engines
Resolves the WindowsPath object is not iterable error across all tools
Enhanced with intelligent path resolution for VENV compatibility
"""
import os
import logging
from pathlib import Path
from typing import List, Union, Any

# Import path resolver for intelligent context detection
try:
    from ..services.path_resolver import get_path_resolver
except ImportError:
    # Add parent directory to path for script execution
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from services.path_resolver import get_path_resolver

logger = logging.getLogger(__name__)


def normalize_paths(paths_input: Any, filter_dependencies: bool = False) -> List[str]:
    """
    Universal path normalization that handles all path input types
    Enhanced with intelligent path resolution for VENV compatibility
    
    Args:
        paths_input: Can be:
            - A single string path
            - A single Path object (file or directory)  
            - A list of string paths
            - A list of Path objects
            - None or empty
        filter_dependencies: If True, exclude common dependency/build directories
            Default False maintains backward compatibility
            
    Returns:
        List of string paths that engines can iterate over safely
    """
    # Handle None or empty input
    if not paths_input:
        return []
    
    # Get user's original directory from environment or current
    base_dir = Path(os.environ.get('SMART_TOOLS_USER_DIR', os.getcwd()))
    logger.debug(f"Using base directory for path resolution: {base_dir}")
    
    # Process paths
    if isinstance(paths_input, (list, tuple)):
        normalized_paths = []
        for path_item in paths_input:
            normalized_paths.extend(normalize_single_path_with_base(path_item, base_dir))
    else:
        normalized_paths = normalize_single_path_with_base(paths_input, base_dir)
    
    # Only filter if explicitly requested - maintains backward compatibility
    if filter_dependencies:
        normalized_paths = detect_project_root(normalized_paths)
        logger.debug(f"Filtered {len(normalized_paths)} paths after dependency exclusion")
    
    return normalized_paths


def normalize_single_path_with_base(path_input: Any, base_dir: Path) -> List[str]:
    """
    Normalize a single path using the specified base directory
    
    Args:
        path_input: Single path as string, Path object, or other type
        base_dir: Base directory to resolve relative paths against
        
    Returns:
        List of string paths
    """
    # Convert to Path object if it's a string
    if isinstance(path_input, str):
        path_obj = Path(path_input)
    elif hasattr(path_input, '__fspath__') or isinstance(path_input, Path):
        path_obj = Path(path_input)
    else:
        logger.warning(f"Unknown path type {type(path_input)}, treating as string: {path_input}")
        return [str(path_input)]
    
    # Convert to absolute path relative to user's directory
    if path_obj.is_absolute():
        full_path = path_obj
    else:
        full_path = base_dir / path_obj
    
    try:
        full_path = full_path.resolve()
        logger.debug(f"Resolved path to: {full_path}")
    except Exception as e:
        logger.warning(f"Could not resolve path {full_path}: {e}")
    
    # Check if path exists
    if not full_path.exists():
        logger.warning(f"Path does not exist: {full_path}")
        return [str(full_path)]  # Return as-is, let engine handle the error
    
    return process_resolved_path(full_path)


def process_resolved_path(path_obj: Path) -> List[str]:
    """
    Process a resolved Path object (expand directories, return files)
    
    Args:
        path_obj: Resolved Path object
        
    Returns:
        List of string file paths
    """
    # If it's a file, return it as a single-item list
    if path_obj.is_file():
        return [str(path_obj)]
    
    # If it's a directory, find all relevant files
    if path_obj.is_dir():
        return get_files_from_directory(path_obj)
    
    # For any other path type, return as string
    return [str(path_obj)]


def normalize_single_path_legacy(path_input: Any) -> List[str]:
    """
    Legacy path normalization (fallback when intelligent resolution fails)
    
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
    
    # LEGACY: Convert to absolute path based on MCP server directory
    try:
        path_obj = path_obj.resolve()
        logger.debug(f"Legacy: Resolved path to absolute: {path_obj}")
    except Exception as e:
        logger.warning(f"Could not resolve path {path_obj}: {e}")
        # Continue with original path
    
    # Check if path exists
    if not path_obj.exists():
        logger.warning(f"Path does not exist: {path_obj}")
        return [str(path_obj)]  # Return as-is, let engine handle the error
    
    return process_resolved_path(path_obj)


def normalize_single_path(path_input: Any) -> List[str]:
    """
    Normalize a single path input - wrapper for backward compatibility
    Now uses intelligent resolution via normalize_paths function
    
    Args:
        path_input: Single path as string, Path object, or other type
        
    Returns:
        List of string paths (single file = 1-item list, directory = multiple files)
    """
    # Use the main normalize_paths function for consistency
    return normalize_paths(path_input)


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


def detect_project_root(paths: List[str]) -> List[str]:
    """
    Simple project boundary detection to fix context awareness issues
    Find .git folder to identify project boundary and filter out dependency directories
    
    Args:
        paths: List of file paths to validate
        
    Returns:
        List of validated paths within project boundary
    """
    if not paths:
        return []
    
    # Common dependency/build directories to exclude
    EXCLUDE_PATTERNS = [
        '.venv', 'venv', 'env',           # Python virtual environments
        'node_modules',                    # Node.js dependencies
        'site-packages',                   # Python site packages
        '__pycache__', '.pytest_cache',    # Python cache
        'dist', 'build', 'target',         # Build outputs
        '.git', '.svn', '.hg',            # Version control internals
        'vendor',                          # Go/Ruby dependencies
        '.cargo', '.rustup',              # Rust directories
    ]
    
    validated_paths = []
    
    for path_str in paths:
        try:
            path = Path(path_str)
            
            # Skip if path doesn't exist
            if not path.exists():
                logger.warning(f"Skipping non-existent path: {path}")
                continue
            
            # Check if path is within excluded patterns
            path_parts = str(path).split(os.sep)
            is_excluded = any(exclude in path_parts for exclude in EXCLUDE_PATTERNS)
            
            if is_excluded:
                logger.info(f"Excluding dependency path: {path}")
                continue
            
            # Try to find project root by looking for .git
            current = path if path.is_dir() else path.parent
            project_root = None
            
            # Walk up directory tree looking for .git
            for parent in [current] + list(current.parents):
                if (parent / '.git').exists():
                    project_root = parent
                    break
            
            if project_root:
                # Verify path is within project
                try:
                    path.resolve().relative_to(project_root.resolve())
                    validated_paths.append(str(path))
                    logger.debug(f"Validated path within project {project_root}: {path}")
                except ValueError:
                    logger.warning(f"Path outside project root, excluding: {path}")
            else:
                # No .git found, include path but warn
                logger.warning(f"No project root found for path, including anyway: {path}")
                validated_paths.append(str(path))
                
        except Exception as e:
            logger.error(f"Error validating path {path_str}: {e}")
            # Include path anyway, let engines handle the error
            validated_paths.append(path_str)
    
    if validated_paths:
        logger.info(f"Project validation: {len(validated_paths)}/{len(paths)} paths validated")
    else:
        logger.warning("No valid paths found after project validation")
    
    return validated_paths


# Backward compatibility aliases
normalize_path = normalize_paths  # For single path normalization
resolve_paths = normalize_paths   # Alternative name