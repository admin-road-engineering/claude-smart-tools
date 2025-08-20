"""
Dependency Mapper - Phase 2 Enhanced Tool Suite
Architectural visualization and refactoring impact analysis with summary-first approach
"""

import ast
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict, deque
import json

from .base_tool import FileAnalysisTool, ToolResult
from .ai_interpreter import DependencyAIInterpreter
from ..integration.file_freshness_decorator import with_file_freshness_check


@dataclass
class DependencyNode:
    """Represents a module node in the dependency graph"""
    id: str
    type: str  # "internal", "standard_library", "third_party"
    file_path: Optional[str] = None
    imports: List[str] = None
    
    def __post_init__(self):
        if self.imports is None:
            self.imports = []


@dataclass
class DependencyEdge:
    """Represents a dependency relationship between modules"""
    from_module: str
    to_module: str
    import_type: str  # "import", "from_import"
    line_number: int


@dataclass
class CircularDependency:
    """Represents a circular dependency cycle"""
    cycle: List[str]
    severity: str  # "low", "medium", "high"
    cycle_length: int
    
    def __post_init__(self):
        self.cycle_length = len(self.cycle)


@dataclass
class CouplingMetrics:
    """Coupling metrics for a module"""
    module: str
    incoming_count: int  # Fan-in
    outgoing_count: int  # Fan-out
    coupling_score: float  # Combined coupling metric
    stability: float  # Outgoing / (Incoming + Outgoing)


@dataclass
class RefactoringImpact:
    """Refactoring impact analysis for a module"""
    module: str
    dependent_modules: int
    blast_radius: str  # "low", "medium", "high"
    risk_score: float
    suggested_actions: List[str]


class DependencyMapper(FileAnalysisTool):
    """
    Maps and analyzes dependency relationships in Python codebases
    Follows the 4-stage Tool-as-a-Service pattern with summary-first output
    """
    
    def __init__(self, ai_interpreter: Optional[DependencyAIInterpreter] = None):
        """
        Initialize Dependency Mapper
        
        Args:
            ai_interpreter: AI interpreter for generating insights (defaults to mock)
        """
        super().__init__()
        self.ai_interpreter = ai_interpreter or DependencyAIInterpreter()
        
        # Standard library modules (Python 3.9+)
        self.stdlib_modules = {
            'os', 'sys', 'json', 're', 'math', 'datetime', 'collections',
            'itertools', 'functools', 'typing', 'pathlib', 'asyncio',
            'logging', 'unittest', 'pytest', 'pickle', 'csv', 'sqlite3',
            'http', 'urllib', 'xml', 'email', 'html', 'io', 'threading',
            'multiprocessing', 'subprocess', 'socket', 'ssl', 'hashlib',
            'base64', 'uuid', 'random', 'time', 'copy', 'gc'
        }
        
        # Configuration
        self.max_summary_nodes = 20
        self.max_summary_edges = 50
        self.coupling_threshold = 0.7
        self.high_impact_threshold = 0.8
    
    @with_file_freshness_check
    async def analyze(self, paths: List[str], summary_only: bool = True, **kwargs) -> str:
        """
        Public-facing method for dependency analysis
        Decorator injects verified_files into kwargs
        
        Args:
            paths: List of source code file/directory paths
            summary_only: Return summary view (default) or full graph
            **kwargs: Contains verified_files from decorator
            
        Returns:
            JSON string with analysis results and AI insights
        """
        # Extract verified files from decorator
        verified_data = kwargs.get('verified_files', {})
        verified_paths = verified_data.get('paths', [])
        
        # Core analysis
        core_results = self._core_utility(verified_paths, summary_only=summary_only)
        
        # AI interpretation
        context = {
            "files_analyzed": len(verified_paths),
            "analysis_type": "dependency_mapping",
            "summary_only": summary_only
        }
        ai_insights = await self.ai_interpreter.interpret(core_results, context)
        
        # Format final results
        result = ToolResult(
            tool_name="DependencyMapper",
            status="success",
            data={**core_results, **ai_insights},
            metadata={
                "files_analyzed": len(verified_paths),
                "parsing_errors": len(core_results.get("parsing_errors", [])),
                "summary_only": summary_only
            }
        )
        
        return result.to_json()
    
    def _core_utility(self, source_files: List[str], summary_only: bool = True) -> Dict[str, Any]:
        """
        Core dependency analysis logic (Stage 1)
        Pure analysis without I/O or AI dependencies
        
        Args:
            source_files: Verified source file paths
            summary_only: Generate summary view to prevent large payloads
            
        Returns:
            Structured dependency analysis results
        """
        # Initialize results structure
        results = {
            "dependency_graph": {"nodes": [], "edges": []},
            "dependency_categories": {
                "internal": [],
                "standard_library": [],
                "third_party": []
            },
            "circular_dependencies": [],
            "coupling_metrics": {},
            "refactoring_impacts": {},
            "parsing_errors": [],
            "summary": {},
            "full_analysis_available": not summary_only
        }
        
        # Parse all files and extract imports
        modules_info = self._parse_source_files(source_files)
        results["parsing_errors"] = modules_info["errors"]
        
        # Build dependency graph
        graph = self._build_dependency_graph(modules_info["modules"])
        
        # Categorize dependencies
        categories = self._categorize_dependencies(graph["nodes"], modules_info["modules"])
        results["dependency_categories"] = categories
        
        # Detect circular dependencies
        circular_deps = self._detect_circular_dependencies(graph)
        results["circular_dependencies"] = [cd.__dict__ for cd in circular_deps]
        
        # Calculate coupling metrics
        coupling_metrics = self._calculate_coupling_metrics(graph)
        results["coupling_metrics"] = {m.module: m.__dict__ for m in coupling_metrics}
        
        # Analyze refactoring impacts
        refactoring_impacts = self._analyze_refactoring_impacts(graph, coupling_metrics)
        results["refactoring_impacts"] = {r.module: r.__dict__ for r in refactoring_impacts}
        
        # Generate summary or full graph
        if summary_only:
            results["dependency_graph"] = self._generate_summary_graph(graph, coupling_metrics)
            results["summary"] = self._generate_analysis_summary(
                graph, circular_deps, coupling_metrics, refactoring_impacts
            )
        else:
            results["dependency_graph"] = {
                "nodes": [node.__dict__ for node in graph["nodes"]],
                "edges": [edge.__dict__ for edge in graph["edges"]]
            }
        
        # Add DOT format export capability
        results["dot_export"] = self._generate_dot_format(graph) if not summary_only else None
        
        return results
    
    def _parse_source_files(self, source_files: List[str]) -> Dict[str, Any]:
        """Parse source files and extract import information"""
        modules = {}
        errors = []
        
        for file_path in source_files:
            if not self._is_python_file(file_path):
                continue
            
            ast_tree, error = self._safe_parse_file(file_path)
            if error:
                errors.append({"file": file_path, "error": error})
                continue
            
            module_info = self._extract_import_info(file_path, ast_tree)
            modules[file_path] = module_info
        
        return {"modules": modules, "errors": errors}
    
    def _safe_parse_file(self, file_path: str) -> Tuple[Optional[ast.AST], Optional[str]]:
        """Parse file with graceful error recovery"""
        try:
            content = self.read_file_safe(file_path)
            if not content.strip():
                return None, "Empty file"
            return ast.parse(content), None
        except SyntaxError as e:
            return None, f"Syntax error: {str(e)}"
        except Exception as e:
            return None, f"Parse error: {str(e)}"
    
    def _extract_import_info(self, file_path: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Extract import statements and dependencies"""
        info = {
            "file_path": file_path,
            "module_name": self._path_to_module_name(file_path),
            "imports": [],
            "from_imports": []
        }
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info["imports"].append({
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno
                    })
            
            elif isinstance(node, ast.ImportFrom):
                # Handle relative imports
                module_name = node.module if node.module else ""
                level = node.level
                
                if level > 0:  # Relative import
                    module_name = self._resolve_relative_import(file_path, module_name, level)
                
                for alias in node.names:
                    info["from_imports"].append({
                        "module": module_name,
                        "imported_name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "is_relative": level > 0
                    })
        
        return info
    
    def _path_to_module_name(self, file_path: str) -> str:
        """Convert file path to Python module name"""
        path = Path(file_path)
        if path.name == "__init__.py":
            return str(path.parent).replace(os.sep, ".")
        else:
            return str(path.with_suffix("")).replace(os.sep, ".")
    
    def _resolve_relative_import(self, file_path: str, module_name: str, level: int) -> str:
        """Resolve relative import to absolute module name"""
        path = Path(file_path)
        parent_parts = path.parts[:-level] if level < len(path.parts) else []
        
        if parent_parts:
            base_module = ".".join(parent_parts)
            if module_name:
                return f"{base_module}.{module_name}"
            else:
                return base_module
        
        return module_name if module_name else "."
    
    def _build_dependency_graph(self, modules_info: Dict[str, Dict]) -> Dict[str, List]:
        """Build dependency graph from module information"""
        nodes = []
        edges = []
        node_ids = set()
        
        # Create nodes for internal modules
        for file_path, info in modules_info.items():
            module_name = info["module_name"]
            if module_name not in node_ids:
                nodes.append(DependencyNode(
                    id=module_name,
                    type="internal",
                    file_path=file_path
                ))
                node_ids.add(module_name)
        
        # Create edges for dependencies
        for file_path, info in modules_info.items():
            from_module = info["module_name"]
            
            # Process direct imports
            for import_info in info["imports"]:
                to_module = import_info["module"]
                self._add_dependency_edge(
                    edges, nodes, node_ids, from_module, to_module, 
                    "import", import_info["line"]
                )
            
            # Process from imports
            for import_info in info["from_imports"]:
                to_module = import_info["module"]
                if to_module:  # Skip empty modules from relative imports
                    self._add_dependency_edge(
                        edges, nodes, node_ids, from_module, to_module,
                        "from_import", import_info["line"]
                    )
        
        return {"nodes": nodes, "edges": edges}
    
    def _add_dependency_edge(self, edges: List, nodes: List, node_ids: Set, 
                           from_module: str, to_module: str, import_type: str, line: int):
        """Add dependency edge and create target node if needed"""
        # Determine target node type
        target_type = self._classify_module_type(to_module)
        
        # Create target node if it doesn't exist
        if to_module not in node_ids:
            nodes.append(DependencyNode(
                id=to_module,
                type=target_type
            ))
            node_ids.add(to_module)
        
        # Create edge
        edges.append(DependencyEdge(
            from_module=from_module,
            to_module=to_module,
            import_type=import_type,
            line_number=line
        ))
    
    def _classify_module_type(self, module_name: str) -> str:
        """Classify module as internal, standard library, or third-party"""
        if not module_name:
            return "internal"
        
        # Get top-level module name
        top_level = module_name.split('.')[0]
        
        # Check if it's a standard library module
        if top_level in self.stdlib_modules:
            return "standard_library"
        
        # Check if it's likely internal (starts with project path components)
        if any(part in ['src', 'lib', 'app'] for part in module_name.split('.')):
            return "internal"
        
        # Default to third-party
        return "third_party"
    
    def _categorize_dependencies(self, nodes: List[DependencyNode], modules_info: Dict) -> Dict[str, List[str]]:
        """Categorize all dependencies by type"""
        categories = {
            "internal": [],
            "standard_library": [],
            "third_party": []
        }
        
        for node in nodes:
            categories[node.type].append(node.id)
        
        return categories
    
    def _detect_circular_dependencies(self, graph: Dict[str, List]) -> List[CircularDependency]:
        """Detect circular dependencies using DFS"""
        edges = graph["edges"]
        nodes = {node.id for node in graph["nodes"]}
        
        # Build adjacency list for internal modules only
        adj_list = defaultdict(list)
        for edge in edges:
            if edge.from_module in nodes and edge.to_module in nodes:
                adj_list[edge.from_module].append(edge.to_module)
        
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> bool:
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                severity = self._assess_cycle_severity(cycle, adj_list)
                cycles.append(CircularDependency(
                    cycle=cycle,
                    severity=severity
                ))
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in adj_list[node]:
                if dfs(neighbor, path + [node]):
                    # Continue searching for more cycles
                    pass
            
            rec_stack.remove(node)
            return False
        
        # Search for cycles starting from each unvisited node
        for node in nodes:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def _assess_cycle_severity(self, cycle: List[str], adj_list: Dict) -> str:
        """Assess the severity of a circular dependency"""
        cycle_length = len(cycle) - 1  # Exclude duplicate node
        
        # Calculate total coupling within the cycle
        total_connections = sum(len(adj_list[node]) for node in cycle[:-1])
        
        if cycle_length <= 2 and total_connections <= 4:
            return "low"
        elif cycle_length <= 4 and total_connections <= 10:
            return "medium"
        else:
            return "high"
    
    def _calculate_coupling_metrics(self, graph: Dict[str, List]) -> List[CouplingMetrics]:
        """Calculate coupling metrics for each module"""
        nodes = {node.id: node for node in graph["nodes"] if node.type == "internal"}
        edges = graph["edges"]
        
        # Count incoming and outgoing dependencies
        incoming = defaultdict(int)
        outgoing = defaultdict(int)
        
        for edge in edges:
            if edge.from_module in nodes:
                outgoing[edge.from_module] += 1
            if edge.to_module in nodes:
                incoming[edge.to_module] += 1
        
        metrics = []
        for module_id in nodes:
            incoming_count = incoming[module_id]
            outgoing_count = outgoing[module_id]
            total = incoming_count + outgoing_count
            
            # Coupling score (0-1, higher is more coupled)
            coupling_score = total / max(len(nodes) - 1, 1) if len(nodes) > 1 else 0
            
            # Stability metric (0-1, higher is more stable)
            stability = outgoing_count / max(total, 1)
            
            metrics.append(CouplingMetrics(
                module=module_id,
                incoming_count=incoming_count,
                outgoing_count=outgoing_count,
                coupling_score=min(coupling_score, 1.0),
                stability=stability
            ))
        
        return metrics
    
    def _analyze_refactoring_impacts(self, graph: Dict[str, List], 
                                   coupling_metrics: List[CouplingMetrics]) -> List[RefactoringImpact]:
        """Analyze potential refactoring impacts"""
        impacts = []
        edges = graph["edges"]
        
        # Build reverse dependency map
        dependents = defaultdict(set)
        for edge in edges:
            dependents[edge.to_module].add(edge.from_module)
        
        for metrics in coupling_metrics:
            module = metrics.module
            dependent_count = len(dependents[module])
            
            # Calculate risk score
            risk_score = (
                (metrics.coupling_score * 0.4) +
                (dependent_count / max(len(coupling_metrics), 1) * 0.4) +
                ((1 - metrics.stability) * 0.2)
            )
            
            # Determine blast radius
            if risk_score > self.high_impact_threshold:
                blast_radius = "high"
            elif risk_score > 0.5:
                blast_radius = "medium"
            else:
                blast_radius = "low"
            
            # Generate suggestions
            suggestions = self._generate_refactoring_suggestions(metrics, dependent_count)
            
            impacts.append(RefactoringImpact(
                module=module,
                dependent_modules=dependent_count,
                blast_radius=blast_radius,
                risk_score=min(risk_score, 1.0),
                suggested_actions=suggestions
            ))
        
        return impacts
    
    def _generate_refactoring_suggestions(self, metrics: CouplingMetrics, dependent_count: int) -> List[str]:
        """Generate refactoring suggestions based on metrics"""
        suggestions = []
        
        if metrics.coupling_score > self.coupling_threshold:
            suggestions.append("High coupling detected - consider breaking into smaller modules")
        
        if dependent_count > 5:
            suggestions.append("Many dependents - ensure comprehensive testing before changes")
        
        if metrics.stability < 0.3:
            suggestions.append("Low stability - consider making dependencies more explicit")
        
        if metrics.incoming_count > 10:
            suggestions.append("High fan-in - consider interface segregation")
        
        if metrics.outgoing_count > 15:
            suggestions.append("High fan-out - consider dependency injection")
        
        if not suggestions:
            suggestions.append("Module has reasonable coupling metrics")
        
        return suggestions
    
    def _generate_summary_graph(self, graph: Dict[str, List], 
                               coupling_metrics: List[CouplingMetrics]) -> Dict[str, Any]:
        """Generate summary view to prevent large payloads"""
        # Get high-impact nodes
        high_impact_modules = [
            m.module for m in coupling_metrics 
            if m.coupling_score > self.coupling_threshold
        ][:self.max_summary_nodes]
        
        # Filter nodes and edges for summary
        summary_nodes = [
            node.__dict__ for node in graph["nodes"] 
            if node.id in high_impact_modules or node.type == "internal"
        ][:self.max_summary_nodes]
        
        summary_edges = [
            edge.__dict__ for edge in graph["edges"]
            if edge.from_module in high_impact_modules or edge.to_module in high_impact_modules
        ][:self.max_summary_edges]
        
        return {
            "nodes": summary_nodes,
            "edges": summary_edges,
            "total_nodes": len(graph["nodes"]),
            "total_edges": len(graph["edges"]),
            "is_summary": True
        }
    
    def _generate_analysis_summary(self, graph: Dict[str, List], 
                                 circular_deps: List[CircularDependency],
                                 coupling_metrics: List[CouplingMetrics],
                                 refactoring_impacts: List[RefactoringImpact]) -> Dict[str, Any]:
        """Generate high-level analysis summary"""
        internal_nodes = [n for n in graph["nodes"] if n.type == "internal"]
        high_coupling = [m for m in coupling_metrics if m.coupling_score > self.coupling_threshold]
        high_risk = [r for r in refactoring_impacts if r.risk_score > self.high_impact_threshold]
        
        return {
            "total_modules": len(internal_nodes),
            "total_dependencies": len(graph["edges"]),
            "circular_dependencies_count": len(circular_deps),
            "high_coupling_modules": len(high_coupling),
            "high_risk_refactoring_targets": len(high_risk),
            "dependency_categories": {
                "internal": len([n for n in graph["nodes"] if n.type == "internal"]),
                "standard_library": len([n for n in graph["nodes"] if n.type == "standard_library"]),
                "third_party": len([n for n in graph["nodes"] if n.type == "third_party"])
            }
        }
    
    def _generate_dot_format(self, graph: Dict[str, List]) -> str:
        """Generate Graphviz DOT format for visualization"""
        lines = ["digraph dependencies {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [shape=box];")
        
        # Add nodes with styling
        for node in graph["nodes"]:
            if node.type == "internal":
                style = 'fillcolor=lightblue, style=filled'
            elif node.type == "standard_library":
                style = 'fillcolor=lightgray, style=filled'
            else:
                style = 'fillcolor=lightyellow, style=filled'
            
            lines.append(f'  "{node.id}" [{style}];')
        
        # Add edges
        for edge in graph["edges"]:
            edge_style = "solid" if edge.import_type == "import" else "dashed"
            lines.append(f'  "{edge.from_module}" -> "{edge.to_module}" [style={edge_style}];')
        
        lines.append("}")
        return "\n".join(lines)
    
    def _is_python_file(self, file_path: str) -> bool:
        """Check if file is a Python file"""
        return file_path.endswith('.py')
    
    async def _get_ai_interpretation(self, core_results: Dict[str, Any], 
                                   context: Optional[Dict[str, Any]] = None) -> str:
        """Get AI interpretation (Stage 3) - delegated to AI interpreter"""
        ai_insights = await self.ai_interpreter.interpret(core_results, context)
        return ai_insights.get("ai_insights", ["No insights generated"])