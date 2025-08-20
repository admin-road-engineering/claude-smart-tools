"""
Project Context Reader - Reads project-specific CLAUDE.md and other context files
Critical fix for Smart Tools using wrong context
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProjectContextReader:
    """Reads and provides project-specific context for Smart Tools analysis"""
    
    # Priority order for context files
    CONTEXT_FILES = [
        'CLAUDE.md',
        'claude.md',
        'GEMINI.md',
        'gemini.md',
        'README.md',
        'readme.md',
        'CONTEXT.md',
        'context.md',
        '.claude/CLAUDE.md',
        '.gemini/GEMINI.md',
        'docs/CLAUDE.md',
        'docs/README.md'
    ]
    
    # Files that indicate project type
    PROJECT_INDICATORS = {
        'package.json': 'Node.js/JavaScript',
        'requirements.txt': 'Python',
        'Cargo.toml': 'Rust',
        'go.mod': 'Go',
        'pom.xml': 'Java/Maven',
        'build.gradle': 'Java/Gradle',
        'composer.json': 'PHP',
        'Gemfile': 'Ruby',
        '.csproj': 'C#/.NET'
    }
    
    def __init__(self):
        self._context_cache = {}
        
    def read_project_context(self, project_paths: List[str]) -> Dict[str, Any]:
        """
        Read all context files from the project being analyzed
        
        Args:
            project_paths: List of paths (files or directories) being analyzed
            
        Returns:
            Dictionary containing project context information
        """
        context = {
            'project_type': None,
            'project_description': None,
            'claude_md_content': None,
            'readme_content': None,
            'gemini_md_content': None,
            'context_files_found': [],
            'project_root': None,
            'key_requirements': [],
            'security_requirements': [],
            'architecture_notes': []
        }
        
        # Find project root from provided paths
        project_root = self._find_project_root(project_paths)
        if project_root:
            context['project_root'] = str(project_root)
            logger.info(f"Detected project root: {project_root}")
            
            # Read context files from project root
            for context_file in self.CONTEXT_FILES:
                file_path = project_root / context_file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        context['context_files_found'].append(str(file_path))
                        
                        # Store specific context files
                        if 'CLAUDE' in context_file.upper():
                            context['claude_md_content'] = content
                            logger.info(f"Found project CLAUDE.md at {file_path}")
                        elif 'README' in context_file.upper():
                            context['readme_content'] = content
                        elif 'GEMINI' in context_file.upper():
                            context['gemini_md_content'] = content
                            
                        # Extract key information from content
                        self._extract_context_info(content, context)
                        
                    except Exception as e:
                        logger.warning(f"Could not read context file {file_path}: {e}")
            
            # Detect project type
            context['project_type'] = self._detect_project_type(project_root)
            
        else:
            logger.warning("Could not determine project root from provided paths")
            
        # Log what we found
        if context['context_files_found']:
            logger.info(f"Found {len(context['context_files_found'])} context files")
            logger.info(f"Project type: {context['project_type']}")
            if context['project_description']:
                logger.info(f"Project description: {context['project_description'][:100]}...")
        else:
            logger.warning("No project context files found - analysis may use incorrect assumptions")
            
        return context
    
    def _find_project_root(self, paths: List[str]) -> Optional[Path]:
        """Find the project root directory from provided paths"""
        # Convert all paths to Path objects and find common root
        path_objects = []
        for path_str in paths:
            path = Path(path_str).resolve()
            if path.exists():
                if path.is_file():
                    path_objects.append(path.parent)
                else:
                    path_objects.append(path)
        
        if not path_objects:
            return None
            
        # Find common ancestor
        common_root = path_objects[0]
        for path in path_objects[1:]:
            # Find common parts
            try:
                common_root = Path(os.path.commonpath([common_root, path]))
            except ValueError:
                # Paths on different drives on Windows
                continue
        
        # Walk up to find project root indicators
        current = common_root
        for _ in range(5):  # Max 5 levels up
            # Check for git root
            if (current / '.git').exists():
                return current
            # Check for context files
            for context_file in self.CONTEXT_FILES[:8]:  # Check main context files
                if (current / context_file).exists():
                    return current
            # Check for project indicator files
            for indicator in self.PROJECT_INDICATORS.keys():
                if (current / indicator).exists():
                    return current
            
            # Move up one level
            parent = current.parent
            if parent == current:  # Reached root
                break
            current = parent
            
        return common_root
    
    def _detect_project_type(self, project_root: Path) -> str:
        """Detect the type of project from indicator files"""
        project_types = []
        
        for indicator, proj_type in self.PROJECT_INDICATORS.items():
            if list(project_root.glob(indicator)) or list(project_root.glob(f'**/{indicator}')):
                project_types.append(proj_type)
        
        if project_types:
            return ', '.join(project_types)
        return 'Unknown'
    
    def _extract_context_info(self, content: str, context: Dict[str, Any]):
        """Extract key information from context file content"""
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Extract project description (usually in first few lines)
            if i < 10 and not context['project_description'] and len(line) > 20:
                if not line.startswith('#') and not line.startswith('```'):
                    context['project_description'] = line.strip()
            
            # Look for security requirements
            if any(keyword in line_lower for keyword in ['security', 'authentication', 'authorization', 'encryption', 'compliance']):
                if line.strip() and not line.startswith('#'):
                    context['security_requirements'].append(line.strip())
            
            # Look for key requirements
            if any(keyword in line_lower for keyword in ['requirement', 'must', 'critical', 'essential', 'important']):
                if line.strip() and not line.startswith('#'):
                    context['key_requirements'].append(line.strip())
            
            # Look for architecture notes
            if any(keyword in line_lower for keyword in ['architecture', 'design', 'pattern', 'structure', 'component']):
                if line.strip() and not line.startswith('#'):
                    context['architecture_notes'].append(line.strip())
        
        # Limit lists to most relevant items
        context['security_requirements'] = context['security_requirements'][:10]
        context['key_requirements'] = context['key_requirements'][:10]
        context['architecture_notes'] = context['architecture_notes'][:10]
    
    def format_context_for_analysis(self, context: Dict[str, Any]) -> str:
        """Format the context into a string for passing to analysis engines"""
        formatted = []
        
        formatted.append("=== PROJECT CONTEXT ===")
        formatted.append(f"Project Root: {context.get('project_root', 'Unknown')}")
        formatted.append(f"Project Type: {context.get('project_type', 'Unknown')}")
        
        if context.get('project_description'):
            formatted.append(f"Description: {context['project_description']}")
        
        if context.get('context_files_found'):
            formatted.append(f"Context Files: {', '.join([Path(f).name for f in context['context_files_found']])}")
        
        if context.get('key_requirements'):
            formatted.append("\n=== KEY REQUIREMENTS ===")
            for req in context['key_requirements'][:5]:
                formatted.append(f"- {req[:200]}")
        
        if context.get('security_requirements'):
            formatted.append("\n=== SECURITY REQUIREMENTS ===")
            for req in context['security_requirements'][:5]:
                formatted.append(f"- {req[:200]}")
        
        if context.get('architecture_notes'):
            formatted.append("\n=== ARCHITECTURE NOTES ===")
            for note in context['architecture_notes'][:5]:
                formatted.append(f"- {note[:200]}")
        
        # Include actual CLAUDE.md content if found
        if context.get('claude_md_content'):
            formatted.append("\n=== PROJECT CLAUDE.MD ===")
            # Include first 1000 chars of CLAUDE.md
            formatted.append(context['claude_md_content'][:1000])
            if len(context['claude_md_content']) > 1000:
                formatted.append("... (truncated)")
        
        # Include actual GEMINI.md content if found
        if context.get('gemini_md_content'):
            formatted.append("\n=== PROJECT GEMINI.MD ===")
            # Include first 1000 chars of GEMINI.md
            formatted.append(context['gemini_md_content'][:1000])
            if len(context['gemini_md_content']) > 1000:
                formatted.append("... (truncated)")
        
        return '\n'.join(formatted)


# Singleton instance
_context_reader = None

def get_project_context_reader() -> ProjectContextReader:
    """Get the singleton ProjectContextReader instance"""
    global _context_reader
    if _context_reader is None:
        _context_reader = ProjectContextReader()
    return _context_reader