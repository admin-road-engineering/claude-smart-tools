"""
Understand Tool - Deep Comprehension Smart Tool
Helps Claude quickly grasp unfamiliar codebases, architectures, patterns
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Union
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer


class UnderstandTool(BaseSmartTool):
    """
    Smart tool for understanding codebases, architectures, and patterns
    Routes to: analyze_code + search_code + analyze_docs
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    # Common documentation file patterns
    DOC_EXTENSIONS = ('.md', '.rst', '.txt', '.markdown', '.adoc', '.org')
    DOC_KEYWORDS = ('readme', 'changelog', 'contributing', 'license', 'install',
                   'history', 'upgrade', 'security', 'authors', 'credits',
                   'notice', 'copyright', 'todo', 'roadmap', 'faq')
    
    def _find_documentation_files(self, paths: List[Union[str, Path]]) -> List[str]:
        """
        Finds documentation files from a list of paths (files or directories).
        Handles both individual files and directory traversal with depth limits.
        """
        found_files = set()
        MAX_DEPTH = 3  # Limit directory traversal depth
        MAX_FILES = 50  # Limit total files to avoid overwhelming the tool
        EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                       'dist', 'build', '.pytest_cache', '.mypy_cache'}
        
        def should_exclude_dir(dir_path: Path) -> bool:
            """Check if directory should be excluded"""
            return any(part in EXCLUDE_DIRS for part in dir_path.parts)
        
        def search_directory(dir_path: Path, current_depth: int = 0):
            """Search directory with depth limit"""
            if current_depth > MAX_DEPTH or len(found_files) >= MAX_FILES:
                return
            
            try:
                for item in dir_path.iterdir():
                    if len(found_files) >= MAX_FILES:
                        break
                        
                    if item.is_dir():
                        if not should_exclude_dir(item):
                            # Check if this is a docs directory
                            if item.name.lower() == 'docs':
                                # Search docs directories more thoroughly
                                search_directory(item, current_depth + 1)
                            elif current_depth < MAX_DEPTH:
                                # Continue searching other directories
                                search_directory(item, current_depth + 1)
                    elif item.is_file():
                        lower_name = item.name.lower()
                        # Check if it's a doc file by extension or name
                        if (lower_name.endswith(self.DOC_EXTENSIONS) or 
                            any(keyword in lower_name for keyword in self.DOC_KEYWORDS)):
                            found_files.add(str(item))
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass
        
        for path in paths:
            if len(found_files) >= MAX_FILES:
                break
                
            try:
                p = Path(path)
                
                if p.is_dir():
                    if not should_exclude_dir(p):
                        search_directory(p, 0)
                elif p.is_file():
                    lower_name = p.name.lower()
                    # Check if it's a doc file by extension or name
                    if (lower_name.endswith(self.DOC_EXTENSIONS) or 
                        any(keyword in lower_name for keyword in self.DOC_KEYWORDS)):
                        found_files.add(str(p))
            except Exception:
                # Skip paths that cause errors
                continue
        
        return sorted(list(found_files))[:MAX_FILES]  # Ensure we don't exceed limit
    
    async def execute(self, files: List[str], question: str = None, **kwargs) -> SmartToolResult:
        """
        Execute understanding analysis with intelligent routing
        """
        routing_strategy = self.get_routing_strategy(files=files, question=question, **kwargs)
        engines_used = []
        results = {}
        
        try:
            # Phase 1: Get architectural overview
            if 'analyze_code' in routing_strategy['engines']:
                code_result = await self.execute_engine(
                    'analyze_code',
                    paths=files,
                    analysis_type='architecture',
                    question=question,
                    verbose=True
                )
                results['architecture'] = code_result
                engines_used.append('analyze_code')
            
            # Phase 2: Find specific patterns if question provided
            if question and 'search_code' in routing_strategy['engines']:
                search_result = await self.execute_engine(
                    'search_code',
                    query=question,
                    paths=files,
                    context_question=f"How does this relate to: {question}",
                    output_format='text'
                )
                results['patterns'] = search_result
                engines_used.append('search_code')
            
            # Phase 3: Include documentation context
            if 'analyze_docs' in routing_strategy['engines']:
                # Use consistent file finding logic
                doc_files = self._find_documentation_files(files)
                if doc_files:
                    doc_result = await self.execute_engine(
                        'analyze_docs',
                        sources=doc_files,
                        synthesis_type='summary',
                        questions=[question] if question else None
                    )
                    results['documentation'] = doc_result
                    engines_used.append('analyze_docs')
            
            # Synthesize results
            synthesized_result = self._synthesize_understanding(results, question)
            
            # Apply executive synthesis for better consolidated response
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'question': question,
                    **kwargs
                }
                synthesized_result = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=synthesized_result,
                    original_request=original_request
                )
            
            return SmartToolResult(
                tool_name=self.tool_name,
                success=True,
                result=synthesized_result,
                engines_used=engines_used,
                routing_decision=routing_strategy['reasoning'],
                metadata={
                    'files_analyzed': len(files),
                    'question': question,
                    'phases_completed': len(results)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name=self.tool_name,
                success=False,
                result=f"Understanding analysis failed: {str(e)}",
                engines_used=engines_used,
                routing_decision=routing_strategy.get('reasoning', 'Error during execution'),
                metadata={'error': str(e)}
            )
    
    def get_routing_strategy(self, files: List[str] = None, question: str = None, **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use for understanding
        """
        engines = ['analyze_code']  # Always start with code analysis
        reasoning_parts = ["Starting with architectural analysis"]
        
        # Add search if we have a specific question
        if question and len(question.strip()) > 0:
            engines.append('search_code')
            reasoning_parts.append("Adding pattern search for specific question")
        
        # Add docs if documentation files are present
        if files:
            doc_files = self._find_documentation_files(files)
            if doc_files:
                engines.append('analyze_docs')
                reasoning_parts.append(f"Including documentation analysis ({len(doc_files)} docs found)")
        
        # Prioritize based on file count
        if files and len(files) > 20:
            reasoning_parts.append("Large codebase - focusing on high-level architecture first")
        
        return {
            'engines': engines,
            'reasoning': '; '.join(reasoning_parts),
            'strategy': 'sequential_synthesis'
        }
    
    def _synthesize_understanding(self, results: Dict[str, Any], question: str = None) -> str:
        """
        Synthesize results from multiple engines into coherent understanding
        """
        synthesis = ["# 🎯 Code Understanding Analysis\n"]
        
        if question:
            synthesis.append(f"**Question**: {question}\n")
        
        # Architecture section
        if 'architecture' in results:
            synthesis.append("## 🏗️ Architecture Overview")
            synthesis.append(str(results['architecture']))
            synthesis.append("")
        
        # Pattern analysis section
        if 'patterns' in results:
            synthesis.append("## 🔍 Pattern Analysis")
            synthesis.append(str(results['patterns']))
            synthesis.append("")
        
        # Documentation insights
        if 'documentation' in results:
            synthesis.append("## 📚 Documentation Insights") 
            synthesis.append(str(results['documentation']))
            synthesis.append("")
        
        # Summary and key takeaways
        synthesis.append("## 💡 Key Understanding Points")
        synthesis.append(self._extract_key_points(results))
        
        return '\n'.join(synthesis)
    
    def _extract_key_points(self, results: Dict[str, Any]) -> str:
        """
        Extract key understanding points from analysis results
        """
        points = []
        
        # This is a simplified extraction - in production, you'd want
        # more sophisticated parsing of the Gemini analysis results
        if 'architecture' in results:
            points.append("- **Architecture**: System structure and component relationships analyzed")
        
        if 'patterns' in results:
            points.append("- **Patterns**: Specific code patterns and implementations identified")
        
        if 'documentation' in results:
            points.append("- **Documentation**: Context and design decisions from docs reviewed")
        
        if not points:
            points.append("- Analysis completed - see detailed results above")
        
        return '\n'.join(points)