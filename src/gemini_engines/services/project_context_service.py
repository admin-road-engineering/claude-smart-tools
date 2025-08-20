"""
ProjectContextService - Intelligent project structure detection and path suggestions
Addresses user feedback: Path detection should auto-detect src/, lib/, app/ when paths=[]
"""
import os
import glob
import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ProjectType(Enum):
    """Detected project types based on structure and files"""
    PYTHON = "python"
    JAVASCRIPT = "javascript" 
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class ProjectContext:
    """Complete project context information"""
    root_path: str
    project_type: ProjectType
    primary_source_dirs: List[str]
    test_dirs: List[str]
    doc_dirs: List[str]
    config_files: List[str]
    confidence_score: float  # 0.0 to 1.0


class ProjectContextService:
    """Service for understanding project structure and providing intelligent defaults"""
    
    def __init__(self, root_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.root_path = root_path or os.getcwd()
        self._project_context_cache = None
        
        # Common directory patterns by project type
        self.source_dir_patterns = {
            ProjectType.PYTHON: ["src", "lib", "app", "api", "backend", "server"],
            ProjectType.JAVASCRIPT: ["src", "lib", "app", "client", "frontend", "public"],
            ProjectType.TYPESCRIPT: ["src", "lib", "app", "client", "frontend"],
            ProjectType.JAVA: ["src/main/java", "src", "lib", "app"],
            ProjectType.GO: [".", "cmd", "internal", "pkg"],
            ProjectType.RUST: ["src", "lib"],
            ProjectType.CPP: ["src", "lib", "include"],
            ProjectType.MIXED: ["src", "lib", "app", "api", "client", "server"]
        }
        
        self.test_dir_patterns = {
            ProjectType.PYTHON: ["tests", "test", "spec", "src/tests"],
            ProjectType.JAVASCRIPT: ["test", "tests", "__tests__", "spec"],
            ProjectType.TYPESCRIPT: ["test", "tests", "__tests__", "spec"], 
            ProjectType.JAVA: ["src/test/java", "test", "tests"],
            ProjectType.GO: [".", "test", "tests"],  # Go tests often alongside source
            ProjectType.RUST: ["tests", "src"],
            ProjectType.CPP: ["test", "tests", "spec"],
            ProjectType.MIXED: ["tests", "test", "__tests__", "spec"]
        }
        
        # File patterns for project type detection
        self.project_indicators = {
            ProjectType.PYTHON: {
                "files": ["*.py", "requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
                "dirs": ["__pycache__", "*.egg-info"]
            },
            ProjectType.JAVASCRIPT: {
                "files": ["package.json", "*.js", "*.jsx"],
                "dirs": ["node_modules", "dist", "build"]
            },
            ProjectType.TYPESCRIPT: {
                "files": ["package.json", "tsconfig.json", "*.ts", "*.tsx"],
                "dirs": ["node_modules", "dist", "build"]
            },
            ProjectType.JAVA: {
                "files": ["pom.xml", "build.gradle", "*.java"],
                "dirs": ["target", "build", ".gradle"]
            },
            ProjectType.GO: {
                "files": ["go.mod", "go.sum", "*.go"],
                "dirs": ["vendor"]
            },
            ProjectType.RUST: {
                "files": ["Cargo.toml", "Cargo.lock", "*.rs"],
                "dirs": ["target"]
            },
            ProjectType.CPP: {
                "files": ["CMakeLists.txt", "Makefile", "*.cpp", "*.c", "*.h", "*.hpp"],
                "dirs": ["build", "cmake-build-*"]
            }
        }
    
    def get_project_context(self, refresh_cache: bool = False) -> ProjectContext:
        """Get complete project context with caching"""
        if self._project_context_cache is None or refresh_cache:
            self._project_context_cache = self._analyze_project_structure()
        return self._project_context_cache
    
    def get_default_paths(self, context_hint: str = None) -> List[str]:
        """
        Get smart default search paths based on project structure
        
        Args:
            context_hint: Optional hint about what kind of analysis ('security', 'tests', etc.)
            
        Returns:
            List of paths to search, ordered by relevance
        """
        project_context = self.get_project_context()
        paths = []
        
        # Primary source directories first
        paths.extend(project_context.primary_source_dirs)
        
        # Context-specific additions
        if context_hint:
            if context_hint.lower() in ['test', 'tests', 'testing']:
                paths.extend(project_context.test_dirs)
            elif context_hint.lower() in ['doc', 'docs', 'documentation']:
                paths.extend(project_context.doc_dirs)
            elif context_hint.lower() in ['config', 'configuration', 'settings']:
                # Add root for config files
                paths.append('.')
        
        # Add test directories for comprehensive analysis
        if not context_hint or context_hint.lower() not in ['test', 'tests']:
            paths.extend(project_context.test_dirs)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in paths:
            if path not in seen and os.path.exists(os.path.join(self.root_path, path)):
                seen.add(path)
                unique_paths.append(path)
        
        # Fallback if no paths detected
        if not unique_paths:
            fallback_paths = ['src', 'lib', 'app', '.']
            for path in fallback_paths:
                if os.path.exists(os.path.join(self.root_path, path)):
                    unique_paths.append(path)
                    break
        
        self.logger.debug(f"Default paths for context '{context_hint}': {unique_paths}")
        return unique_paths
    
    def detect_project_type(self) -> ProjectType:
        """Detect the primary project type based on files and structure"""
        scores = {ptype: 0.0 for ptype in ProjectType if ptype != ProjectType.UNKNOWN}
        
        # Check for indicator files and directories
        for project_type, indicators in self.project_indicators.items():
            # Score based on files
            for file_pattern in indicators["files"]:
                matches = glob.glob(os.path.join(self.root_path, "**", file_pattern), recursive=True)
                scores[project_type] += len(matches) * 2.0
                
                # Bonus for root-level indicator files
                root_matches = glob.glob(os.path.join(self.root_path, file_pattern))
                scores[project_type] += len(root_matches) * 3.0
            
            # Score based on directories
            for dir_pattern in indicators["dirs"]:
                if '*' in dir_pattern:
                    matches = glob.glob(os.path.join(self.root_path, dir_pattern))
                else:
                    matches = [os.path.join(self.root_path, dir_pattern)] if os.path.exists(os.path.join(self.root_path, dir_pattern)) else []
                scores[project_type] += len(matches) * 1.5
        
        # Normalize scores by total file count to avoid bias toward large projects
        total_files = sum(len(list(Path(self.root_path).rglob("*"))) for _ in [1])  # Count once
        if total_files > 100:  # Only normalize for larger projects
            for ptype in scores:
                scores[ptype] = scores[ptype] / (total_files / 100)
        
        # Find the highest scoring type
        if not any(scores.values()):
            return ProjectType.UNKNOWN
        
        max_score = max(scores.values())
        if max_score < 1.0:  # Very low confidence
            return ProjectType.UNKNOWN
        
        # Check if multiple types have similar scores (mixed project)
        high_scores = [ptype for ptype, score in scores.items() if score >= max_score * 0.7]
        if len(high_scores) > 2:
            return ProjectType.MIXED
        
        return max(scores, key=scores.get)
    
    def suggest_search_paths(self, context: str, file_types: List[str] = None) -> List[str]:
        """
        Suggest search paths based on context and file types
        
        Args:
            context: Context description ('authentication code', 'test files', etc.)
            file_types: Optional list of file extensions to focus on
            
        Returns:
            List of suggested paths
        """
        project_context = self.get_project_context()
        suggestions = []
        
        context_lower = context.lower()
        
        # Context-based suggestions
        if any(term in context_lower for term in ['auth', 'login', 'user', 'security', 'permission']):
            auth_paths = self._find_paths_containing(['auth', 'login', 'user', 'security', 'permission'])
            suggestions.extend(auth_paths)
        
        if any(term in context_lower for term in ['test', 'spec', 'unit', 'integration']):
            suggestions.extend(project_context.test_dirs)
        
        if any(term in context_lower for term in ['api', 'endpoint', 'route', 'controller']):
            api_paths = self._find_paths_containing(['api', 'route', 'controller', 'endpoint'])
            suggestions.extend(api_paths)
        
        if any(term in context_lower for term in ['config', 'setting', 'env']):
            suggestions.append('.')  # Root for config files
            config_paths = self._find_paths_containing(['config', 'setting'])
            suggestions.extend(config_paths)
        
        # File type based suggestions
        if file_types:
            for file_type in file_types:
                type_paths = self._find_paths_with_extension(file_type)
                suggestions.extend(type_paths)
        
        # Add primary source directories if no specific suggestions
        if not suggestions:
            suggestions.extend(project_context.primary_source_dirs)
        
        return self._deduplicate_paths(suggestions)
    
    def _analyze_project_structure(self) -> ProjectContext:
        """Analyze the complete project structure"""
        project_type = self.detect_project_type()
        
        # Find source directories
        primary_source_dirs = self._find_source_directories(project_type)
        
        # Find test directories  
        test_dirs = self._find_test_directories(project_type)
        
        # Find documentation directories
        doc_dirs = self._find_documentation_directories()
        
        # Find important config files
        config_files = self._find_config_files()
        
        # Calculate confidence score
        confidence = self._calculate_confidence_score(project_type, primary_source_dirs, config_files)
        
        return ProjectContext(
            root_path=self.root_path,
            project_type=project_type,
            primary_source_dirs=primary_source_dirs,
            test_dirs=test_dirs,
            doc_dirs=doc_dirs,
            config_files=config_files,
            confidence_score=confidence
        )
    
    def _find_source_directories(self, project_type: ProjectType) -> List[str]:
        """Find primary source code directories"""
        candidates = self.source_dir_patterns.get(project_type, ["src", "lib", "app"])
        found_dirs = []
        
        for candidate in candidates:
            full_path = os.path.join(self.root_path, candidate)
            if os.path.isdir(full_path):
                # Check if directory contains relevant files
                if self._directory_contains_code(full_path, project_type):
                    found_dirs.append(candidate)
        
        # If no specific directories found, check common patterns
        if not found_dirs:
            common_dirs = ["src", "lib", "app", "source", "code"]
            for common_dir in common_dirs:
                full_path = os.path.join(self.root_path, common_dir) 
                if os.path.isdir(full_path) and self._directory_contains_code(full_path, project_type):
                    found_dirs.append(common_dir)
        
        # If still nothing, check if root contains code
        if not found_dirs and self._directory_contains_code(self.root_path, project_type):
            found_dirs.append('.')
        
        return found_dirs
    
    def _find_test_directories(self, project_type: ProjectType) -> List[str]:
        """Find test directories"""
        candidates = self.test_dir_patterns.get(project_type, ["tests", "test"])
        found_dirs = []
        
        for candidate in candidates:
            full_path = os.path.join(self.root_path, candidate)
            if os.path.isdir(full_path):
                found_dirs.append(candidate)
        
        return found_dirs
    
    def _find_documentation_directories(self) -> List[str]:
        """Find documentation directories"""
        doc_patterns = ["docs", "doc", "documentation", "README*", "*.md"]
        found_dirs = []
        
        for pattern in doc_patterns:
            if '*' in pattern:
                matches = glob.glob(os.path.join(self.root_path, pattern))
                found_dirs.extend([os.path.relpath(m, self.root_path) for m in matches if os.path.isfile(m)])
            else:
                full_path = os.path.join(self.root_path, pattern)
                if os.path.isdir(full_path):
                    found_dirs.append(pattern)
        
        return found_dirs
    
    def _find_config_files(self) -> List[str]:
        """Find important configuration files"""
        config_patterns = [
            "*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.conf",
            "package.json", "requirements.txt", "Cargo.toml", "pom.xml",
            ".env*", "config.*", "settings.*"
        ]
        
        config_files = []
        for pattern in config_patterns:
            matches = glob.glob(os.path.join(self.root_path, pattern))
            config_files.extend([os.path.relpath(m, self.root_path) for m in matches if os.path.isfile(m)])
        
        return config_files
    
    def _directory_contains_code(self, directory: str, project_type: ProjectType) -> bool:
        """Check if directory contains code files relevant to project type"""
        if project_type == ProjectType.UNKNOWN:
            # Check for any common code file extensions
            extensions = ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.rs", "*.cpp", "*.c", "*.h"]
        else:
            extensions = self.project_indicators.get(project_type, {}).get("files", [])
        
        for ext in extensions:
            if glob.glob(os.path.join(directory, "**", ext), recursive=True):
                return True
        
        return False
    
    def _find_paths_containing(self, terms: List[str]) -> List[str]:
        """Find directories whose names contain any of the given terms"""
        found_paths = []
        
        for root, dirs, files in os.walk(self.root_path):
            for dir_name in dirs:
                if any(term.lower() in dir_name.lower() for term in terms):
                    rel_path = os.path.relpath(os.path.join(root, dir_name), self.root_path)
                    found_paths.append(rel_path)
        
        return found_paths
    
    def _find_paths_with_extension(self, extension: str) -> List[str]:
        """Find directories containing files with specific extension"""
        if not extension.startswith('.'):
            extension = '.' + extension
        
        found_paths = set()
        pattern = f"**/*{extension}"
        
        for match in glob.glob(os.path.join(self.root_path, pattern), recursive=True):
            dir_path = os.path.dirname(match)
            rel_dir = os.path.relpath(dir_path, self.root_path)
            if rel_dir != '.':
                found_paths.add(rel_dir)
        
        return list(found_paths)
    
    def _calculate_confidence_score(self, project_type: ProjectType, source_dirs: List[str], config_files: List[str]) -> float:
        """Calculate confidence in project analysis"""
        score = 0.0
        
        # Base score for detected project type
        if project_type != ProjectType.UNKNOWN:
            score += 0.3
        
        # Score for found source directories
        if source_dirs:
            score += min(0.4, len(source_dirs) * 0.1)
        
        # Score for config files
        if config_files:
            score += min(0.3, len(config_files) * 0.05)
        
        return min(1.0, score)
    
    def _deduplicate_paths(self, paths: List[str]) -> List[str]:
        """Remove duplicate paths while preserving order"""
        seen = set()
        unique = []
        
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique.append(path)
        
        return unique