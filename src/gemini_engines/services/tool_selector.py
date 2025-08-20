"""
Enhanced tool selection service with DialogueState integration and context awareness.

Intelligently selects appropriate analysis tools based on context, file types,
previous execution results, and dialogue history for optimal comprehensive reviews.
"""
import logging
import os
from collections import Counter
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import datetime, timezone

from ..tools.interfaces import IToolSelector
from ..models.dialogue_models import DialogueState, ToolOutput, ErrorType, IntentResult

logger = logging.getLogger(__name__)


class ToolSelector(IToolSelector):
    """
    Intelligent tool selector with enhanced heuristics for comprehensive reviews.
    Uses file types, focus areas, and content analysis to prioritize tools.
    """
    
    def __init__(self):
        """Initialize ToolSelector with predefined mappings and rules"""
        
        # Enhanced review type to tool mappings
        self.review_mappings = {
            'functional': ['test_coverage_analyzer', 'api_contract_checker'],
            'security': ['config_validator'],  # Will expand with security_scanner
            'maintainability': ['interface_inconsistency_detector', 'dependency_mapper'],
            'performance': ['performance_profiler'],
            'debugging': ['test_coverage_analyzer'],  # Will expand with log_analyzer
            'compliance': ['api_contract_checker', 'config_validator'], 
            'architecture': ['dependency_mapper', 'config_validator', 'interface_inconsistency_detector'],
            'usability': ['accessibility_checker']
        }
        
        # File extension to tool mappings with priority scores
        self.file_type_mappings = {
            # Python files
            '.py': [
                ('test_coverage_analyzer', 0.9),
                ('dependency_mapper', 0.8),
                ('interface_inconsistency_detector', 0.7)
            ],
            # Configuration files
            '.yaml': [('config_validator', 1.0)],
            '.yml': [('config_validator', 1.0)],
            '.json': [('config_validator', 0.9), ('api_contract_checker', 0.8)],
            '.env': [('config_validator', 1.0)],
            '.ini': [('config_validator', 0.8)],
            '.toml': [('config_validator', 0.8)],
            '.conf': [('config_validator', 0.7)],
            # Web files
            '.html': [('accessibility_checker', 1.0)],
            '.htm': [('accessibility_checker', 1.0)],
            '.jsx': [('accessibility_checker', 0.8), ('interface_inconsistency_detector', 0.6)],
            '.tsx': [('accessibility_checker', 0.8), ('interface_inconsistency_detector', 0.6)],
            '.vue': [('accessibility_checker', 0.8)],
            '.svelte': [('accessibility_checker', 0.8)],
            # API specification files
            '.swagger': [('api_contract_checker', 1.0)],
            # JavaScript/TypeScript
            '.js': [('interface_inconsistency_detector', 0.7), ('dependency_mapper', 0.6)],
            '.ts': [('interface_inconsistency_detector', 0.7), ('dependency_mapper', 0.6)],
            # Documentation
            '.md': [('interface_inconsistency_detector', 0.3)],
            '.rst': [('interface_inconsistency_detector', 0.3)]
        }
        
        # Path pattern to tool mappings
        self.path_pattern_mappings = {
            'test': ['test_coverage_analyzer'],
            'tests': ['test_coverage_analyzer'], 
            'spec': ['test_coverage_analyzer'],
            'specs': ['test_coverage_analyzer'],
            'config': ['config_validator'],
            'configuration': ['config_validator'],
            'settings': ['config_validator'],
            'api': ['api_contract_checker'],
            'swagger': ['api_contract_checker'],
            'openapi': ['api_contract_checker'],
            'docs': ['interface_inconsistency_detector'],
            'documentation': ['interface_inconsistency_detector'],
            'components': ['accessibility_checker', 'interface_inconsistency_detector'],
            'ui': ['accessibility_checker'],
            'frontend': ['accessibility_checker'],
            'templates': ['accessibility_checker']
        }
        
        # Content-based heuristics (would need file reading to implement)
        self.content_heuristics = {
            'imports_patterns': {
                'flask': ['api_contract_checker'],
                'fastapi': ['api_contract_checker'],
                'django': ['api_contract_checker'],
                'pytest': ['test_coverage_analyzer'],
                'unittest': ['test_coverage_analyzer'],
                'react': ['accessibility_checker'],
                'vue': ['accessibility_checker']
            }
        }
    
    def determine_priority_tools(self, 
                                file_paths: List[str], 
                                focus: str = "all") -> List[str]:
        """
        Select priority tools based on file types, paths, and focus area.
        
        Args:
            file_paths: Files to be analyzed
            focus: Review focus area
            
        Returns:
            List of tool names in priority order
        """
        if not file_paths:
            # Return default tools for focus area
            return self.get_tools_for_focus(focus)
        
        logger.info(f"Determining priority tools for {len(file_paths)} files with focus '{focus}'")
        
        # Score tools based on multiple criteria
        tool_scores = Counter()
        
        # 1. File extension scoring
        ext_scores = self._score_by_file_extensions(file_paths)
        tool_scores.update(ext_scores)
        
        # 2. Path pattern scoring
        path_scores = self._score_by_path_patterns(file_paths)
        tool_scores.update(path_scores)
        
        # 3. Focus area scoring
        focus_scores = self._score_by_focus_area(focus)
        tool_scores.update(focus_scores)
        
        # 4. Apply file count multipliers
        file_count_multipliers = self._calculate_file_count_multipliers(file_paths)
        for tool, multiplier in file_count_multipliers.items():
            if tool in tool_scores:
                tool_scores[tool] *= multiplier
        
        # 5. Filter out tools that don't make sense for this file set
        filtered_scores = self._filter_irrelevant_tools(tool_scores, file_paths)
        
        # 6. Sort by score and return top tools
        priority_tools = [tool for tool, score in filtered_scores.most_common()]
        
        # Ensure we have at least some default tools
        if not priority_tools:
            default_tools = ['config_validator', 'dependency_mapper']
            logger.info(f"No specific tools selected, using defaults: {default_tools}")
            return default_tools
        
        logger.info(f"Selected priority tools: {priority_tools[:5]} (top 5)")
        return priority_tools
    
    def get_tools_for_focus(self, focus: str) -> List[str]:
        """
        Get all tools relevant for a specific focus area.
        
        Args:
            focus: Focus area (security, performance, etc.)
            
        Returns:
            List of relevant tool names
        """
        if focus == "all":
            # Return a balanced set from each category
            all_tools = set()
            for tools in self.review_mappings.values():
                all_tools.update(tools)
            return list(all_tools)
        
        return self.review_mappings.get(focus, ['config_validator', 'dependency_mapper'])
    
    def _score_by_file_extensions(self, file_paths: List[str]) -> Counter:
        """Score tools based on file extensions in the file set"""
        scores = Counter()
        
        for file_path in file_paths:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.file_type_mappings:
                for tool_name, score in self.file_type_mappings[ext]:
                    scores[tool_name] += score
        
        logger.debug(f"Extension-based scores: {dict(scores.most_common(3))}")
        return scores
    
    def _score_by_path_patterns(self, file_paths: List[str]) -> Counter:
        """Score tools based on path patterns"""
        scores = Counter()
        
        for file_path in file_paths:
            path_lower = file_path.lower()
            for pattern, tools in self.path_pattern_mappings.items():
                if pattern in path_lower:
                    for tool_name in tools:
                        scores[tool_name] += 0.8  # Fixed score for path matches
        
        logger.debug(f"Path-based scores: {dict(scores.most_common(3))}")
        return scores
    
    def _score_by_focus_area(self, focus: str) -> Counter:
        """Score tools based on focus area relevance"""
        scores = Counter()
        
        if focus == "all":
            # Give equal weighting to all focus areas
            for tools in self.review_mappings.values():
                for tool_name in tools:
                    scores[tool_name] += 0.5
        elif focus in self.review_mappings:
            # High score for focus-specific tools
            for tool_name in self.review_mappings[focus]:
                scores[tool_name] += 2.0
        
        logger.debug(f"Focus-based scores for '{focus}': {dict(scores.most_common(3))}")
        return scores
    
    def _calculate_file_count_multipliers(self, file_paths: List[str]) -> Dict[str, float]:
        """Calculate multipliers based on file count and diversity"""
        file_count = len(file_paths)
        
        multipliers = {
            'dependency_mapper': min(1.0 + (file_count - 1) * 0.1, 2.0),  # More files = more complex dependencies
            'interface_inconsistency_detector': min(1.0 + (file_count - 1) * 0.05, 1.5),  # Benefits from multiple files
        }
        
        # Count file types for diversity bonus
        extensions = {os.path.splitext(f)[1].lower() for f in file_paths}
        diversity_bonus = len(extensions) * 0.1
        
        if diversity_bonus > 0:
            multipliers['config_validator'] = multipliers.get('config_validator', 1.0) + diversity_bonus
        
        return multipliers
    
    def _filter_irrelevant_tools(self, tool_scores: Counter, file_paths: List[str]) -> Counter:
        """Filter out tools that don't make sense for the given file set"""
        filtered_scores = Counter()
        
        # Get file extensions present
        extensions = {os.path.splitext(f)[1].lower() for f in file_paths}
        
        for tool_name, score in tool_scores.items():
            # Skip accessibility checker if no web files
            if tool_name == 'accessibility_checker':
                web_extensions = {'.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte'}
                if not extensions.intersection(web_extensions):
                    logger.debug(f"Filtering out {tool_name} - no web files detected")
                    continue
            
            # Skip API contract checker if no API spec files
            if tool_name == 'api_contract_checker':
                api_extensions = {'.json', '.yaml', '.yml', '.swagger'}
                has_api_files = extensions.intersection(api_extensions)
                has_api_paths = any('api' in path.lower() or 'swagger' in path.lower() 
                                  for path in file_paths)
                if not (has_api_files or has_api_paths):
                    logger.debug(f"Filtering out {tool_name} - no API files detected")
                    continue
            
            # Skip test coverage analyzer if no code files
            if tool_name == 'test_coverage_analyzer':
                code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx'}
                if not extensions.intersection(code_extensions):
                    logger.debug(f"Filtering out {tool_name} - no code files detected")
                    continue
            
            filtered_scores[tool_name] = score
        
        return filtered_scores
    
    def get_tool_recommendations(self, 
                                file_paths: List[str], 
                                focus: str = "all",
                                max_tools: int = 5) -> List[Dict[str, Any]]:
        """
        Get detailed tool recommendations with explanations.
        
        Args:
            file_paths: Files to analyze
            focus: Review focus area
            max_tools: Maximum number of tools to recommend
            
        Returns:
            List of tool recommendation dictionaries with rationale
        """
        priority_tools = self.determine_priority_tools(file_paths, focus)
        
        recommendations = []
        for i, tool_name in enumerate(priority_tools[:max_tools]):
            
            # Determine rationale
            rationale = self._get_tool_rationale(tool_name, file_paths, focus)
            
            # Estimate execution time (rough estimates)
            execution_estimates = {
                'config_validator': 'Fast (30-60s)',
                'accessibility_checker': 'Fast (15-45s)',
                'test_coverage_analyzer': 'Medium (60-120s)',
                'dependency_mapper': 'Medium (45-90s)',
                'interface_inconsistency_detector': 'Medium (60-90s)',
                'api_contract_checker': 'Fast (20-40s)',
                'performance_profiler': 'Slow (120-300s)'
            }
            
            recommendation = {
                'tool_name': tool_name,
                'priority': i + 1,
                'rationale': rationale,
                'estimated_time': execution_estimates.get(tool_name, 'Unknown'),
                'focus_areas': self._get_tool_focus_areas(tool_name),
                'file_types': self._get_supported_file_types(tool_name)
            }
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_tool_rationale(self, tool_name: str, file_paths: List[str], focus: str) -> str:
        """Generate rationale for why a tool was selected"""
        
        reasons = []
        
        # File type reasons
        extensions = {os.path.splitext(f)[1].lower() for f in file_paths}
        for ext in extensions:
            if ext in self.file_type_mappings:
                for mapped_tool, score in self.file_type_mappings[ext]:
                    if mapped_tool == tool_name and score > 0.7:
                        reasons.append(f"High relevance for {ext} files")
                        break
        
        # Path reasons
        path_keywords = []
        for file_path in file_paths:
            path_lower = file_path.lower()
            for pattern, tools in self.path_pattern_mappings.items():
                if pattern in path_lower and tool_name in tools:
                    path_keywords.append(pattern)
        
        if path_keywords:
            reasons.append(f"Matches path patterns: {', '.join(set(path_keywords))}")
        
        # Focus reasons
        if focus != "all" and focus in self.review_mappings:
            if tool_name in self.review_mappings[focus]:
                reasons.append(f"Primary tool for {focus} focus")
        
        # File count reasons
        if tool_name == 'dependency_mapper' and len(file_paths) > 5:
            reasons.append("Complex dependency analysis needed for large codebase")
        
        return "; ".join(reasons) if reasons else f"General-purpose tool for {focus} review"
    
    def _get_tool_focus_areas(self, tool_name: str) -> List[str]:
        """Get focus areas that this tool supports"""
        focus_areas = []
        for focus, tools in self.review_mappings.items():
            if tool_name in tools:
                focus_areas.append(focus)
        return focus_areas
    
    def _get_supported_file_types(self, tool_name: str) -> List[str]:
        """Get file extensions that this tool can analyze"""
        supported_types = []
        for ext, tool_mappings in self.file_type_mappings.items():
            for mapped_tool, score in tool_mappings:
                if mapped_tool == tool_name:
                    supported_types.append(ext)
                    break
        return supported_types
    
    def analyze_file_set_complexity(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze the complexity of the file set to guide tool selection.
        
        Args:
            file_paths: Files to analyze
            
        Returns:
            Complexity analysis dictionary
        """
        extensions = Counter(os.path.splitext(f)[1].lower() for f in file_paths)
        
        # Categorize files
        config_files = sum(1 for ext in extensions if ext in ['.yaml', '.yml', '.json', '.env', '.ini', '.toml'])
        code_files = sum(1 for ext in extensions if ext in ['.py', '.js', '.ts', '.jsx', '.tsx'])
        web_files = sum(1 for ext in extensions if ext in ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte'])
        
        # Calculate complexity metrics
        total_files = len(file_paths)
        file_diversity = len(extensions)
        
        complexity = {
            'total_files': total_files,
            'file_diversity': file_diversity,
            'file_types': dict(extensions.most_common()),
            'categorization': {
                'config_files': config_files,
                'code_files': code_files,
                'web_files': web_files,
                'other_files': total_files - config_files - code_files - web_files
            },
            'complexity_score': min((total_files * 0.1) + (file_diversity * 0.2), 10.0),
            'recommended_parallelism': min(max(total_files // 10, 2), 6)
        }
        
        return complexity
    
    def determine_priority_tools_enhanced(self,
                                         file_paths: List[str],
                                         focus: str = "all",
                                         dialogue_state: Optional[DialogueState] = None,
                                         user_intent: Optional[IntentResult] = None) -> List[str]:
        """
        Enhanced tool selection with DialogueState context awareness.
        
        Args:
            file_paths: Files to be analyzed
            focus: Review focus area
            dialogue_state: Current dialogue state with execution history
            user_intent: Parsed user intent from current turn
            
        Returns:
            List of tool names in priority order with context awareness
        """
        # Start with base tool selection
        base_tools = self.determine_priority_tools(file_paths, focus)
        
        if not dialogue_state:
            return base_tools
        
        logger.info(f"Enhanced tool selection with dialogue context (round {dialogue_state.current_round})")
        
        # Apply context-aware adjustments
        context_adjusted_tools = self._apply_dialogue_context(base_tools, dialogue_state, user_intent)
        
        return context_adjusted_tools
    
    def _apply_dialogue_context(self,
                               base_tools: List[str],
                               dialogue_state: DialogueState,
                               user_intent: Optional[IntentResult]) -> List[str]:
        """
        Apply dialogue context to adjust tool selection.
        
        Args:
            base_tools: Base tool selection from file analysis
            dialogue_state: Current dialogue state
            user_intent: Current user intent
            
        Returns:
            Context-adjusted tool list
        """
        adjusted_tools = base_tools.copy()
        
        # 1. Handle user-specified tools
        if user_intent and user_intent.tool_name:
            specific_tool = user_intent.tool_name
            if specific_tool not in adjusted_tools:
                # Add user-requested tool at high priority
                adjusted_tools.insert(0, specific_tool)
                logger.info(f"Added user-requested tool: {specific_tool}")
            elif adjusted_tools.index(specific_tool) > 2:
                # Move user-requested tool to higher priority
                adjusted_tools.remove(specific_tool)
                adjusted_tools.insert(0, specific_tool)
                logger.info(f"Prioritized user-requested tool: {specific_tool}")
        
        # 2. Handle previously failed tools with error type context
        failed_tools = set(dialogue_state.failed_tools.keys())
        retryable_failed_tools = self._get_retryable_failed_tools(dialogue_state)
        
        # Remove non-retryable failed tools
        non_retryable_failed = failed_tools - retryable_failed_tools
        for tool in non_retryable_failed:
            if tool in adjusted_tools:
                adjusted_tools.remove(tool)
                logger.info(f"Removed non-retryable failed tool: {tool}")
        
        # Deprioritize retryable failed tools unless user specifically requests retry
        if user_intent and user_intent.action.value != "retry_failed":
            for tool in retryable_failed_tools:
                if tool in adjusted_tools and adjusted_tools.index(tool) < 3:
                    # Move recently failed tools to lower priority
                    adjusted_tools.remove(tool)
                    adjusted_tools.append(tool)
                    logger.info(f"Deprioritized recently failed tool: {tool}")
        
        # 3. Avoid redundancy with already successful tools
        successful_tools = set(dialogue_state.get_successful_tools().keys())
        if len(successful_tools) > 0 and user_intent and user_intent.action.value != "run_tool":
            # For non-specific requests, prefer tools not already run successfully
            new_tools = [tool for tool in adjusted_tools if tool not in successful_tools]
            already_run = [tool for tool in adjusted_tools if tool in successful_tools]
            adjusted_tools = new_tools + already_run
            logger.info(f"Prioritized new tools over already successful: {len(new_tools)} new, {len(already_run)} already run")
        
        # 4. Consider dialogue progression
        if dialogue_state.current_round > 5:
            # In later rounds, focus on tools that complement what's been done
            adjusted_tools = self._suggest_complementary_tools(adjusted_tools, dialogue_state)
        
        return adjusted_tools
    
    def _get_retryable_failed_tools(self, dialogue_state: DialogueState) -> Set[str]:
        """
        Get failed tools that are retryable based on their error types.
        
        Args:
            dialogue_state: Current dialogue state
            
        Returns:
            Set of tool names that are retryable
        """
        retryable_tools = set()
        
        # Now we have direct access to error types in failed_tools
        for tool_name, error_type in dialogue_state.failed_tools.items():
            # Check if error type is retryable
            if error_type in [ErrorType.TRANSIENT, ErrorType.INTERNAL]:
                retryable_tools.add(tool_name)
        
        return retryable_tools
    
    def _suggest_complementary_tools(self, tools: List[str], dialogue_state: DialogueState) -> List[str]:
        """
        Suggest tools that complement already executed tools.
        
        Args:
            tools: Current tool list
            dialogue_state: Dialogue state with execution history
            
        Returns:
            Reordered tool list with complementary tools prioritized
        """
        executed_tools = set(dialogue_state.executed_tools.keys())
        
        # Define complementary tool relationships
        complementary_mapping = {
            'config_validator': ['dependency_mapper', 'api_contract_checker'],
            'dependency_mapper': ['interface_inconsistency_detector', 'test_coverage_analyzer'],
            'test_coverage_analyzer': ['interface_inconsistency_detector', 'dependency_mapper'],
            'api_contract_checker': ['interface_inconsistency_detector', 'config_validator'],
            'interface_inconsistency_detector': ['test_coverage_analyzer', 'dependency_mapper'],
            'performance_profiler': ['config_validator', 'dependency_mapper'],
            'accessibility_checker': ['interface_inconsistency_detector']
        }
        
        # Find complementary tools for executed tools
        suggested_complements = set()
        for executed_tool in executed_tools:
            if executed_tool in complementary_mapping:
                suggested_complements.update(complementary_mapping[executed_tool])
        
        # Reorder tools to prioritize complements not yet executed
        complementary_tools = []
        other_tools = []
        
        for tool in tools:
            if tool in suggested_complements and tool not in executed_tools:
                complementary_tools.append(tool)
            else:
                other_tools.append(tool)
        
        if complementary_tools:
            logger.info(f"Prioritized complementary tools: {complementary_tools}")
        
        return complementary_tools + other_tools
    
    def get_next_recommended_tools(self,
                                  dialogue_state: DialogueState,
                                  max_tools: int = 3) -> List[Dict[str, Any]]:
        """
        Get next recommended tools based on dialogue state and execution history.
        
        Args:
            dialogue_state: Current dialogue state
            max_tools: Maximum number of tools to recommend
            
        Returns:
            List of tool recommendations with context-aware rationale
        """
        # Determine what tools to recommend next
        remaining_tools = self.determine_priority_tools_enhanced(
            dialogue_state.file_paths,
            dialogue_state.focus,
            dialogue_state
        )
        
        # Filter out already successful tools unless they provide ongoing value
        successful_tools = set(dialogue_state.get_successful_tools().keys())
        new_tools = [tool for tool in remaining_tools if tool not in successful_tools]
        
        # If we have enough new tools, use them; otherwise include some successful ones
        if len(new_tools) >= max_tools:
            selected_tools = new_tools[:max_tools]
        else:
            # Include some already successful tools that might provide additional value
            valuable_repeats = [tool for tool in successful_tools if tool in remaining_tools[:5]]
            selected_tools = new_tools + valuable_repeats[:max_tools - len(new_tools)]
        
        recommendations = []
        for i, tool_name in enumerate(selected_tools):
            # Generate context-aware rationale
            rationale = self._get_context_aware_rationale(tool_name, dialogue_state)
            
            # Determine if this is a retry
            is_retry = tool_name in dialogue_state.failed_tools
            
            recommendation = {
                'tool_name': tool_name,
                'priority': i + 1,
                'rationale': rationale,
                'is_retry': is_retry,
                'estimated_time': self._get_execution_estimate(tool_name),
                'expected_value': self._assess_expected_value(tool_name, dialogue_state),
                'dependencies': self._get_tool_dependencies(tool_name),
                'complements': self._get_tool_complements(tool_name)
            }
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_context_aware_rationale(self, tool_name: str, dialogue_state: DialogueState) -> str:
        """
        Generate context-aware rationale for tool selection.
        
        Args:
            tool_name: Name of the tool
            dialogue_state: Current dialogue state
            
        Returns:
            Rationale string explaining why this tool is recommended
        """
        reasons = []
        
        # Base rationale from file analysis
        base_rationale = self._get_tool_rationale(tool_name, dialogue_state.file_paths, dialogue_state.focus)
        if base_rationale:
            reasons.append(base_rationale)
        
        # Context-specific reasons
        successful_tools = set(dialogue_state.get_successful_tools().keys())
        
        if tool_name in dialogue_state.failed_tools:
            if tool_name in dialogue_state.executed_tools:
                tool_output = dialogue_state.executed_tools[tool_name]
                if tool_output.is_retryable:
                    reasons.append(f"Retry - previous failure was retryable ({tool_output.error_type.value})")
                else:
                    reasons.append("Not recommended - previous failure was non-retryable")
        
        # Complementary analysis
        complementary_executed = self._find_complementary_executed_tools(tool_name, successful_tools)
        if complementary_executed:
            reasons.append(f"Complements already successful: {', '.join(complementary_executed)}")
        
        # Progression reasons
        if dialogue_state.current_round > 3:
            reasons.append(f"Advanced analysis for round {dialogue_state.current_round}")
        
        # Coverage reasons
        if len(successful_tools) < 2:
            reasons.append("Baseline coverage needed")
        
        return "; ".join(reasons) if reasons else f"Standard tool for {dialogue_state.focus} review"
    
    def _find_complementary_executed_tools(self, tool_name: str, executed_tools: Set[str]) -> List[str]:
        """Find executed tools that complement the given tool"""
        complements = {
            'config_validator': ['dependency_mapper', 'api_contract_checker'],
            'dependency_mapper': ['interface_inconsistency_detector', 'test_coverage_analyzer', 'config_validator'],
            'test_coverage_analyzer': ['interface_inconsistency_detector', 'dependency_mapper'],
            'api_contract_checker': ['interface_inconsistency_detector', 'config_validator'],
            'interface_inconsistency_detector': ['test_coverage_analyzer', 'dependency_mapper', 'api_contract_checker'],
            'performance_profiler': ['config_validator', 'dependency_mapper'],
            'accessibility_checker': ['interface_inconsistency_detector']
        }
        
        tool_complements = complements.get(tool_name, [])
        return [tool for tool in tool_complements if tool in executed_tools]
    
    def _assess_expected_value(self, tool_name: str, dialogue_state: DialogueState) -> str:
        """
        Assess the expected value of running this tool in the current context.
        
        Args:
            tool_name: Name of the tool
            dialogue_state: Current dialogue state
            
        Returns:
            Expected value assessment
        """
        successful_tools = set(dialogue_state.get_successful_tools().keys())
        
        # High value if not run yet
        if tool_name not in dialogue_state.executed_tools:
            return "High - new analysis"
        
        # Medium value if retry of retryable failure
        if tool_name in dialogue_state.failed_tools:
            tool_output = dialogue_state.executed_tools.get(tool_name)
            if tool_output and tool_output.is_retryable:
                return "Medium - retryable failure"
            else:
                return "Low - non-retryable failure"
        
        # Low value if already successful unless it provides ongoing insights
        ongoing_value_tools = {'performance_profiler', 'test_coverage_analyzer'}
        if tool_name in successful_tools:
            if tool_name in ongoing_value_tools:
                return "Medium - ongoing insights"
            else:
                return "Low - already completed"
        
        return "Medium - standard analysis"
    
    def _get_execution_estimate(self, tool_name: str) -> str:
        """Get execution time estimate for a tool"""
        estimates = {
            'config_validator': 'Fast (30-60s)',
            'accessibility_checker': 'Fast (15-45s)',
            'test_coverage_analyzer': 'Medium (60-120s)',
            'dependency_mapper': 'Medium (45-90s)',
            'interface_inconsistency_detector': 'Medium (60-90s)',
            'api_contract_checker': 'Fast (20-40s)',
            'performance_profiler': 'Slow (120-300s)'
        }
        return estimates.get(tool_name, 'Unknown')
    
    def _get_tool_dependencies(self, tool_name: str) -> List[str]:
        """Get tools that should ideally run before this tool"""
        dependencies = {
            'interface_inconsistency_detector': ['config_validator'],
            'test_coverage_analyzer': ['dependency_mapper'],
            'performance_profiler': ['config_validator', 'dependency_mapper']
        }
        return dependencies.get(tool_name, [])
    
    def _get_tool_complements(self, tool_name: str) -> List[str]:
        """Get tools that work well with this tool"""
        complements = {
            'config_validator': ['dependency_mapper', 'api_contract_checker'],
            'dependency_mapper': ['interface_inconsistency_detector', 'test_coverage_analyzer'],
            'test_coverage_analyzer': ['interface_inconsistency_detector'],
            'api_contract_checker': ['interface_inconsistency_detector'],
            'interface_inconsistency_detector': ['test_coverage_analyzer', 'dependency_mapper'],
            'performance_profiler': ['config_validator'],
            'accessibility_checker': ['interface_inconsistency_detector']
        }
        return complements.get(tool_name, [])
    
    def analyze_execution_patterns(self, dialogue_state: DialogueState) -> Dict[str, Any]:
        """
        Analyze execution patterns to provide insights for tool selection.
        
        Args:
            dialogue_state: Current dialogue state
            
        Returns:
            Analysis of execution patterns and recommendations
        """
        executed_tools = dialogue_state.executed_tools
        
        if not executed_tools:
            return {
                'status': 'initial',
                'message': 'No tools executed yet',
                'recommendations': ['Start with config_validator or dependency_mapper']
            }
        
        # Analyze success/failure patterns
        successful = [name for name, output in executed_tools.items() if output.is_success]
        failed = [name for name, output in executed_tools.items() if output.is_failure]
        retryable_failed = [name for name, output in executed_tools.items() 
                           if output.is_failure and output.is_retryable]
        
        # Calculate execution statistics
        total_execution_time = sum(output.execution_time_seconds for output in executed_tools.values())
        avg_execution_time = total_execution_time / len(executed_tools) if executed_tools else 0
        
        # Assess coverage
        all_available_tools = set()
        for tools in self.review_mappings.values():
            all_available_tools.update(tools)
        
        coverage_percentage = len(successful) / len(all_available_tools) * 100
        
        # Generate insights
        insights = []
        if len(successful) == 0:
            insights.append("No successful tool executions yet")
        elif len(successful) < 3:
            insights.append("Limited tool coverage - consider broader analysis")
        else:
            insights.append(f"Good tool coverage ({len(successful)} successful)")
        
        if retryable_failed:
            insights.append(f"{len(retryable_failed)} tools can be retried")
        
        if len(failed) > len(successful):
            insights.append("High failure rate - check file paths and configuration")
        
        return {
            'execution_stats': {
                'total_tools_run': len(executed_tools),
                'successful': len(successful),
                'failed': len(failed),
                'retryable_failed': len(retryable_failed),
                'success_rate': len(successful) / len(executed_tools) * 100 if executed_tools else 0,
                'total_execution_time_seconds': total_execution_time,
                'average_execution_time_seconds': avg_execution_time
            },
            'coverage': {
                'tools_executed': successful,
                'tools_failed': failed,
                'coverage_percentage': coverage_percentage,
                'missing_focus_areas': self._find_missing_focus_coverage(successful, dialogue_state.focus)
            },
            'insights': insights,
            'next_recommendations': [
                tool['tool_name'] for tool in 
                self.get_next_recommended_tools(dialogue_state, max_tools=3)
            ]
        }
    
    def _find_missing_focus_coverage(self, successful_tools: List[str], focus: str) -> List[str]:
        """
        Find focus areas that haven't been adequately covered by successful tools.
        
        Args:
            successful_tools: List of successfully executed tool names
            focus: Current review focus area
            
        Returns:
            List of focus areas that need more coverage
        """
        missing_areas = []
        
        if focus == "all":
            # Check coverage across all focus areas
            for focus_area, required_tools in self.review_mappings.items():
                # Check if this focus area has at least one tool executed
                covered = any(tool in successful_tools for tool in required_tools)
                if not covered:
                    missing_areas.append(focus_area)
        else:
            # For specific focus, check if we have good coverage
            required_tools = self.review_mappings.get(focus, [])
            covered_tools = [tool for tool in required_tools if tool in successful_tools]
            
            # If less than 50% of focus tools are covered, consider it missing
            coverage_ratio = len(covered_tools) / len(required_tools) if required_tools else 0
            if coverage_ratio < 0.5:
                missing_areas.append(focus)
        
        return missing_areas