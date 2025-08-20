"""
Path Security Validator - Critical security component for path traversal protection
Ensures all file access remains within project boundaries
"""
import os
import logging
from pathlib import Path
from typing import Optional, List, Set
from ..exceptions import SecurityError

logger = logging.getLogger(__name__)


class PathSecurityValidator:
    """
    Validates file paths to prevent path traversal attacks.
    Ensures all file operations remain within designated project boundaries.
    
    This is a CRITICAL security component - all file access must go through this validator.
    """
    
    def __init__(self, project_root: Optional[str] = None, allowed_roots: Optional[List[str]] = None):
        """
        Initialize path security validator with project boundaries.
        
        Args:
            project_root: Primary project root directory (defaults to CWD)
            allowed_roots: Additional allowed root directories (e.g., for multi-repo projects)
        """
        # Set primary project root
        self.project_root = Path(project_root or os.getcwd()).resolve()
        
        # Set additional allowed roots if provided
        self.allowed_roots: Set[Path] = {self.project_root}
        if allowed_roots:
            for root in allowed_roots:
                self.allowed_roots.add(Path(root).resolve())
        
        logger.info(f"Path validator initialized with root: {self.project_root}")
        if len(self.allowed_roots) > 1:
            logger.info(f"Additional allowed roots: {self.allowed_roots - {self.project_root}}")
    
    def validate_path(self, file_path: str, operation: str = "access") -> Path:
        """
        Validate a file path for security and return resolved absolute path.
        
        Args:
            file_path: Path to validate (can be relative or absolute)
            operation: Type of operation (for error messages)
            
        Returns:
            Resolved absolute Path object within project boundaries
            
        Raises:
            SecurityError: If path is outside project boundaries or invalid
        """
        if not file_path:
            raise SecurityError("Empty path provided", error_code="EMPTY_PATH")
        
        try:
            # Resolve to absolute path, ensuring it exists and following symlinks
            # Using strict=True provides better security by only allowing existing paths
            resolved_path = Path(file_path).resolve(strict=True)
        except FileNotFoundError:
            # Path doesn't exist - treat as security failure for consistency
            raise SecurityError(
                f"Path validation failed: '{file_path}' does not exist",
                error_code="PATH_NOT_FOUND",
                suggestions=["Check if the file or directory exists", "Verify the path is correct"],
                context={"requested_path": str(file_path), "operation": operation}
            )
        except (OSError, ValueError) as e:
            raise SecurityError(
                f"Invalid path format: {file_path}",
                error_code="INVALID_PATH",
                suggestions=["Check path syntax", "Ensure path doesn't contain invalid characters"],
                context={"original_error": str(e)}
            )
        
        # Check if path is within any allowed root using Pythonic approach
        # This avoids the UnboundLocalError bug and is more concise
        is_within_allowed_roots = any(
            self._is_path_within(resolved_path, root) for root in self.allowed_roots
        )
        
        if not is_within_allowed_roots:
            logger.warning(f"SECURITY: Blocked {operation} attempt outside project boundary: {file_path}")
            raise SecurityError(
                f"Path traversal attempt blocked: {file_path}",
                error_code="PATH_TRAVERSAL",
                suggestions=[
                    "Ensure path is within project directory",
                    f"Project root: {self.project_root}",
                    "Avoid using '..' or absolute paths outside project"
                ],
                context={
                    "requested_path": str(file_path),
                    "resolved_path": str(resolved_path),
                    "project_root": str(self.project_root),
                    "operation": operation
                }
            )
        
        logger.debug(f"Path validated successfully: {resolved_path}")
        return resolved_path
    
    @staticmethod
    def _is_path_within(child: Path, parent: Path) -> bool:
        """
        Check if child path is within parent directory.
        
        Args:
            child: Path to check
            parent: Parent directory path
            
        Returns:
            True if child is within parent, False otherwise
        """
        try:
            # relative_to() will throw ValueError if child is not within parent
            child.relative_to(parent)
            return True
        except ValueError:
            return False
    
    def validate_multiple_paths(self, paths: List[str], operation: str = "access") -> List[Path]:
        """
        Validate multiple paths at once.
        
        Args:
            paths: List of paths to validate
            operation: Type of operation
            
        Returns:
            List of validated Path objects
            
        Raises:
            SecurityError: If any path is invalid (fails fast on first invalid path)
        """
        validated_paths = []
        for path in paths:
            validated_paths.append(self.validate_path(path, operation))
        return validated_paths
    
    def is_safe_path(self, file_path: str) -> bool:
        """
        Check if a path is safe without raising exceptions.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if path is within boundaries, False otherwise
        """
        try:
            self.validate_path(file_path)
            return True
        except SecurityError:
            return False
    
    def get_relative_path(self, file_path: str) -> Path:
        """
        Get path relative to project root (for safe display).
        
        Args:
            file_path: Path to convert
            
        Returns:
            Path relative to project root
            
        Raises:
            SecurityError: If path is invalid
        """
        validated_path = self.validate_path(file_path)
        try:
            return validated_path.relative_to(self.project_root)
        except ValueError:
            # Path is in an additional allowed root, return as-is
            return validated_path
    
    def sanitize_path_for_display(self, file_path: str) -> str:
        """
        Sanitize a path for safe display in error messages.
        Removes absolute path components that might leak system information.
        
        Args:
            file_path: Path to sanitize
            
        Returns:
            Sanitized path string safe for external display
        """
        try:
            relative_path = self.get_relative_path(file_path)
            return str(relative_path).replace("\\", "/")
        except:
            # If we can't get relative path, return just the filename
            return Path(file_path).name


# Global singleton instance for consistent validation across the application
_global_validator: Optional[PathSecurityValidator] = None


def get_path_validator(project_root: Optional[str] = None) -> PathSecurityValidator:
    """
    Get or create the global path validator instance.
    
    Args:
        project_root: Project root directory (only used on first call)
        
    Returns:
        Global PathSecurityValidator instance
    """
    global _global_validator
    if _global_validator is None:
        _global_validator = PathSecurityValidator(project_root)
    return _global_validator


def validate_path(file_path: str, operation: str = "access") -> Path:
    """
    Convenience function to validate a path using the global validator.
    
    Args:
        file_path: Path to validate
        operation: Type of operation
        
    Returns:
        Validated Path object
        
    Raises:
        SecurityError: If path is invalid
    """
    return get_path_validator().validate_path(file_path, operation)