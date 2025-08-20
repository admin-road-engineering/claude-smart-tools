"""
Complexity scoring logic for model selection and tool timeout assessment
Enhanced to handle tool-specific timeout calculations
"""
import logging
from typing import Union, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from ..config import (
    COMPLEXITY_INDICATORS, 
    LENGTH_THRESHOLDS, 
    COMPLEX_FOCUS_AREAS,
    GEMINI_REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)


class ToolComplexity(Enum):
    """Tool operation complexity levels"""
    SIMPLE = 1      # Basic operations, small scope
    MODERATE = 2    # Medium operations, multiple files  
    COMPLEX = 3     # Large scope, boolean queries, regex
    INTENSIVE = 4   # Comprehensive analysis, large datasets


@dataclass
class ToolAssessment:
    """Assessment result for tool operations"""
    tool_name: str
    complexity: ToolComplexity
    timeout_seconds: int
    escalation_levels: List[int]
    factors: Dict[str, Any]


class ComplexityScorer:
    """Assess task complexity to choose appropriate Gemini model"""
    
    def __init__(self, base_timeout: float = None):
        self.base_timeout = base_timeout or GEMINI_REQUEST_TIMEOUT
        self.complexity_indicators = COMPLEXITY_INDICATORS
        self.length_thresholds = LENGTH_THRESHOLDS
        self.complex_focus_areas = COMPLEX_FOCUS_AREAS
    
    def assess_complexity(self, output: str, is_plan: bool, focus: str, detail_level: str = "detailed") -> int:
        """Assess task complexity to choose appropriate model"""
        complexity_score = 0
        
        # Detail level factor
        if detail_level == "comprehensive":
            complexity_score += 2  # Comprehensive reviews are inherently complex
        elif detail_level == "detailed":
            complexity_score += 1  # Detailed reviews are moderately complex
        
        # Length (longer = more complex)
        content_length = len(output)
        if content_length > self.length_thresholds['large']:
            complexity_score += 2
        elif content_length > self.length_thresholds['medium']:
            complexity_score += 1
            
        # Focus area complexity
        if focus in self.complex_focus_areas:
            complexity_score += 1
            
        # Code vs plan (code review is more complex)
        if not is_plan:
            complexity_score += 1
            
        # Code complexity indicators
        output_lower = output.lower()
        complexity_keywords = sum(1 for keyword in self.complexity_indicators 
                                if keyword in output_lower)
        complexity_score += min(complexity_keywords // 3, 2)  # Max 2 points from keywords
        
        logger.debug(f"Complexity assessment: score={complexity_score}, length={content_length}, "
                    f"focus={focus}, is_plan={is_plan}, keywords={complexity_keywords}")
        
        return complexity_score
    
    def calculate_dynamic_timeout(self, output: str, is_plan: bool, focus: str, detail_level: str = "detailed") -> float:
        """Calculate dynamic timeout based on content size and complexity"""
        timeout = self.base_timeout
        
        # Detail level factor - comprehensive reviews take much longer
        if detail_level == "comprehensive":
            timeout += 60  # Extra minute for comprehensive analysis
        elif detail_level == "detailed":
            timeout += 30  # Extra 30 seconds for detailed analysis
        
        # Content size factor (add time for longer content)
        content_length = len(output)
        if content_length > 5000:  # Large documentation or complex code
            timeout += 30  # Extra 30 seconds for large content
        elif content_length > 2000:  # Medium content
            timeout += 15  # Extra 15 seconds
        elif content_length > 1000:  # Small-medium content
            timeout += 5   # Extra 5 seconds
        
        # Focus area complexity (documentation reviews take longer)
        if focus == "all":
            timeout += 10  # Comprehensive reviews take more time
        elif focus in ["security", "architecture"]:
            timeout += 5   # Complex focus areas need more time
        
        # Plan vs code (documentation is typically plans and takes longer to analyze)
        if is_plan and content_length > 1000:
            timeout += 10  # Documentation/plan reviews typically take longer
        
        # Cap maximum timeout based on detail level and focus
        # Comprehensive reviews need much longer timeouts
        if detail_level == "comprehensive" or focus == "all":
            max_timeout = 180  # 3 minutes for comprehensive reviews
        elif focus in ["security", "architecture"] or detail_level == "detailed":
            max_timeout = 150  # 2.5 minutes for focused/detailed reviews
        else:
            max_timeout = 120  # 2 minutes for standard reviews
            
        final_timeout = min(timeout, max_timeout)
        
        if final_timeout != self.base_timeout:
            logger.info(f"Dynamic timeout: {final_timeout}s (base: {self.base_timeout}s, "
                       f"content: {content_length} chars)")
        
        return final_timeout
    
    def select_model_by_complexity(self, complexity_score: int, is_first_review: bool = True) -> str:
        """Select appropriate model based on complexity score"""
        if is_first_review:
            # First review: prioritize quality for complex tasks
            if complexity_score >= 4:
                return "pro"  # Complex tasks get the most capable model
            elif complexity_score >= 2:
                return "flash"  # Medium complexity
            else:
                return "flash-lite"  # Simple tasks
        else:
            # Subsequent reviews: prioritize speed and cost
            if complexity_score >= 4:
                return "flash"  # Even complex tasks can use flash for follow-up
            else:
                return "flash-lite"  # Most follow-ups are simple
    
    def get_model_fallback_order(self, primary_model: str) -> list:
        """Get fallback model order when primary model fails"""
        fallback_orders = {
            "pro": ["flash", "flash-lite"],
            "flash": ["flash-lite", "pro"],  
            "flash-lite": ["flash", "pro"]
        }
        return fallback_orders.get(primary_model, ["flash-lite", "flash", "pro"])
    
    def calculate_dialogue_rounds(self, output: str, is_plan: bool, focus: str, 
                                detail_level: str, model: str, user_specified: int = None) -> int:
        """
        Calculate suggested dialogue rounds based on complexity factors
        
        This provides a GUIDE for the expected number of rounds, not a hard limit.
        Claude can exceed this if the dialogue genuinely requires more rounds.
        
        Args:
            output: Content to review
            is_plan: Whether content is a plan or code
            focus: Review focus area
            detail_level: Level of detail requested
            model: Selected model name
            user_specified: User-specified rounds (takes precedence if provided)
            
        Returns:
            Suggested dialogue rounds (1-15, soft guidance)
        """
        if user_specified is not None:
            # User override takes precedence - respect their preference
            return max(user_specified, 1)
        
        base_rounds = 3
        complexity_score = self.assess_complexity(output, is_plan, focus, detail_level)
        
        # Complexity bonus based on existing scoring
        if complexity_score >= 6:
            complexity_bonus = 3  # Very complex
        elif complexity_score >= 4:
            complexity_bonus = 2  # Complex
        elif complexity_score >= 2:
            complexity_bonus = 1  # Medium
        else:
            complexity_bonus = 0  # Simple
        
        # Detail level bonus
        detail_bonus = {
            "summary": 0,
            "detailed": 1, 
            "comprehensive": 2
        }.get(detail_level, 1)
        
        # Focus area bonus - security and architecture need more rounds
        focus_bonus = {
            "security": 2,
            "architecture": 2, 
            "all": 2,
            "performance": 1
        }.get(focus, 0)
        
        # Model bonus - more capable models benefit from more dialogue
        model_bonus = {
            "pro": 2,
            "flash": 1,
            "flash-lite": 0
        }.get(model, 0)
        
        calculated_rounds = base_rounds + complexity_bonus + detail_bonus + focus_bonus + model_bonus
        suggested_rounds = min(calculated_rounds, 15)  # Soft guidance cap (raised from 10)
        
        logger.info(f"Suggested dialogue rounds: {suggested_rounds} "
                   f"(base:{base_rounds} + complexity:{complexity_bonus} + detail:{detail_bonus} + "
                   f"focus:{focus_bonus} + model:{model_bonus}) - Claude can exceed if needed")
        
        return suggested_rounds
    
    def assess_tool_complexity(self, tool_name: str, params: Dict[str, Any]) -> ToolAssessment:
        """
        Assess complexity of a tool operation for timeout calculation
        
        Args:
            tool_name: Name of the tool being executed
            params: Tool parameters/arguments
            
        Returns:
            ToolAssessment with complexity and timeout information
        """
        if tool_name == "search_code":
            return self._assess_search_complexity(params)
        elif tool_name == "analyze_code":
            return self._assess_analyze_complexity(params)
        elif tool_name == "check_quality":
            return self._assess_quality_check_complexity(params)
        elif tool_name == "review_output":
            return self._assess_review_complexity(params)
        elif tool_name == "analyze_docs":
            return self._assess_docs_complexity(params)
        elif tool_name == "analyze_logs":
            return self._assess_logs_complexity(params)
        elif tool_name == "analyze_database":
            return self._assess_database_complexity(params)
        else:
            return self._assess_generic_tool_complexity(tool_name, params)
    
    def _assess_search_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of search_code operations"""
        complexity = ToolComplexity.SIMPLE
        factors = {}
        
        # Query complexity
        query = params.get("query", "")
        search_type = params.get("search_type", "text")
        
        if search_type == "regex":
            complexity = ToolComplexity.COMPLEX
            factors["regex_search"] = True
        elif "|" in query or " OR " in query.upper() or " AND " in query.upper():
            complexity = ToolComplexity.MODERATE
            factors["boolean_query"] = True
        
        # Path scope
        paths = params.get("paths", [])
        if len(paths) > 3:
            complexity = max(complexity, ToolComplexity.MODERATE)
            factors["multiple_paths"] = len(paths)
        
        # Output format (markdown requires more processing)
        if params.get("output_format") == "markdown":
            factors["markdown_formatting"] = True
        
        # Context question complexity
        context_question = params.get("context_question", "")
        if context_question and len(context_question) > 50:
            complexity = max(complexity, ToolComplexity.MODERATE)
            factors["complex_context"] = True
        
        return self._create_tool_assessment("search_code", complexity, factors)
    
    def _assess_analyze_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of analyze_code operations"""
        complexity = ToolComplexity.MODERATE  # Analysis is inherently more complex
        factors = {}
        
        # Analysis type
        analysis_type = params.get("analysis_type", "overview")
        if analysis_type in ["architecture", "dependencies", "refactor_prep"]:
            complexity = ToolComplexity.COMPLEX
            factors["complex_analysis"] = analysis_type
        
        # Verbosity
        verbose = params.get("verbose", True)
        if not verbose:
            complexity = ToolComplexity.SIMPLE  # Summary mode is faster
            factors["summary_mode"] = True
        
        # Path count and size estimation
        paths = params.get("paths", [])
        if len(paths) > 5:
            complexity = ToolComplexity.COMPLEX
            factors["large_scope"] = len(paths)
        
        # Output format
        if params.get("output_format") == "markdown":
            factors["markdown_formatting"] = True
        
        # Custom question
        if params.get("question"):
            factors["custom_question"] = True
        
        return self._create_tool_assessment("analyze_code", complexity, factors)
    
    def _assess_quality_check_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of check_quality operations"""
        complexity = ToolComplexity.MODERATE
        factors = {}
        
        # Check type
        check_type = params.get("check_type", "all")
        if check_type == "all":
            complexity = ToolComplexity.COMPLEX
            factors["comprehensive_check"] = True
        elif check_type == "security":
            complexity = ToolComplexity.COMPLEX
            factors["security_analysis"] = True
        
        # Verbosity
        verbose = params.get("verbose", True)
        if not verbose:
            factors["summary_mode"] = True
        else:
            complexity = max(complexity, ToolComplexity.COMPLEX)
        
        # Path scope
        paths = params.get("paths", [])
        test_paths = params.get("test_paths", [])
        total_paths = len(paths) + len(test_paths)
        
        if total_paths > 10:
            complexity = ToolComplexity.INTENSIVE
            factors["large_codebase"] = total_paths
        elif total_paths > 5:
            complexity = max(complexity, ToolComplexity.COMPLEX)
            factors["medium_codebase"] = total_paths
        
        return self._create_tool_assessment("check_quality", complexity, factors)
    
    def _assess_review_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of review_output operations"""
        complexity = ToolComplexity.MODERATE
        factors = {}
        
        # Detail level
        detail_level = params.get("detail_level", "detailed")
        if detail_level == "comprehensive":
            complexity = ToolComplexity.INTENSIVE
            factors["comprehensive_review"] = True
        elif detail_level == "summary":
            complexity = ToolComplexity.SIMPLE
            factors["summary_review"] = True
        
        # Focus area
        focus = params.get("focus", "all")
        if focus in ["security", "architecture", "all"]:
            complexity = max(complexity, ToolComplexity.COMPLEX)
            factors["complex_focus"] = focus
        
        # Content length estimation
        output = params.get("output", "")
        content_length = len(output)
        if content_length > 5000:
            complexity = max(complexity, ToolComplexity.COMPLEX)
            factors["large_content"] = content_length
        
        # Claude response indicates continuation
        if params.get("claude_response"):
            factors["dialogue_continuation"] = True
        
        return self._create_tool_assessment("review_output", complexity, factors)
    
    def _assess_docs_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of analyze_docs operations"""
        complexity = ToolComplexity.SIMPLE
        factors = {}
        
        sources = params.get("sources", [])
        
        # Web sources add complexity
        web_sources = [s for s in sources if s.startswith(('http://', 'https://'))]
        if web_sources:
            complexity = ToolComplexity.MODERATE
            factors["web_sources"] = len(web_sources)
        
        # Multiple sources
        if len(sources) > 3:
            complexity = max(complexity, ToolComplexity.MODERATE)
            factors["multiple_sources"] = len(sources)
        
        # Complex questions
        questions = params.get("questions", [])
        if len(questions) > 2:
            complexity = max(complexity, ToolComplexity.MODERATE)
            factors["multiple_questions"] = len(questions)
        
        return self._create_tool_assessment("analyze_docs", complexity, factors)
    
    def _assess_logs_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of analyze_logs operations"""
        complexity = ToolComplexity.SIMPLE
        factors = {}
        
        log_paths = params.get("log_paths", [])
        
        # Multiple log files
        if len(log_paths) > 3:
            complexity = ToolComplexity.MODERATE
            factors["multiple_logs"] = len(log_paths)
        
        # Focus complexity
        focus = params.get("focus", "all")
        if focus == "all":
            complexity = max(complexity, ToolComplexity.MODERATE)
            factors["comprehensive_log_analysis"] = True
        
        # Time range filtering adds complexity
        if params.get("time_range"):
            factors["time_filtering"] = True
        
        return self._create_tool_assessment("analyze_logs", complexity, factors)
    
    def _assess_database_complexity(self, params: Dict[str, Any]) -> ToolAssessment:
        """Assess complexity of analyze_database operations"""
        complexity = ToolComplexity.MODERATE  # DB analysis is inherently complex
        factors = {}
        
        # Analysis type
        analysis_type = params.get("analysis_type", "schema")
        if analysis_type in ["relationships", "optimization"]:
            complexity = ToolComplexity.COMPLEX
            factors["complex_db_analysis"] = analysis_type
        
        # Multiple repositories
        repo_paths = params.get("repo_paths", [])
        if len(repo_paths) > 1:
            complexity = max(complexity, ToolComplexity.COMPLEX)
            factors["cross_repo_analysis"] = len(repo_paths)
        
        return self._create_tool_assessment("analyze_database", complexity, factors)
    
    def _assess_generic_tool_complexity(self, tool_name: str, params: Dict[str, Any]) -> ToolAssessment:
        """Fallback assessment for unknown tools"""
        return self._create_tool_assessment(tool_name, ToolComplexity.SIMPLE, {"generic_tool": True})
    
    def _create_tool_assessment(self, tool_name: str, complexity: ToolComplexity, factors: Dict[str, Any]) -> ToolAssessment:
        """Create a ToolAssessment with appropriate timeout and escalation levels"""
        
        # Base timeouts by complexity level
        base_timeouts = {
            ToolComplexity.SIMPLE: 30,     # 30 seconds
            ToolComplexity.MODERATE: 60,   # 1 minute
            ToolComplexity.COMPLEX: 120,   # 2 minutes
            ToolComplexity.INTENSIVE: 180  # 3 minutes
        }
        
        base_timeout = base_timeouts[complexity]
        
        # Tool-specific adjustments
        tool_multipliers = {
            "search_code": 0.8,      # Search is generally fast
            "analyze_code": 1.2,     # Analysis takes longer
            "check_quality": 1.5,    # Quality checks are thorough
            "review_output": 2.0,    # Reviews involve API calls and can be slow
            "analyze_docs": 1.0,     # Standard
            "analyze_logs": 0.9,     # Log analysis is usually straightforward
            "analyze_database": 1.3  # DB analysis can be complex
        }
        
        multiplier = tool_multipliers.get(tool_name, 1.0)
        adjusted_timeout = int(base_timeout * multiplier)
        
        # Create escalation levels (progressive timeout)
        escalation_levels = [
            adjusted_timeout,                    # First attempt
            min(adjusted_timeout * 2, 300),     # Second attempt (max 5 min)
            min(adjusted_timeout * 3, 600)      # Third attempt (max 10 min)
        ]
        
        factors["base_timeout"] = base_timeout
        factors["multiplier"] = multiplier
        factors["complexity_level"] = complexity.name
        
        logger.debug(f"Tool assessment - {tool_name}: complexity={complexity.name}, "
                    f"timeout={adjusted_timeout}s, escalation={escalation_levels}")
        
        return ToolAssessment(
            tool_name=tool_name,
            complexity=complexity,
            timeout_seconds=adjusted_timeout,
            escalation_levels=escalation_levels,
            factors=factors
        )
    
    def get_tool_timeout(self, tool_name: str, params: Dict[str, Any], attempt: int = 1) -> int:
        """
        Get timeout for a tool operation, with escalation support
        
        Args:
            tool_name: Name of the tool
            params: Tool parameters
            attempt: Attempt number (1-3) for escalation
            
        Returns:
            Timeout in seconds for this attempt
        """
        assessment = self.assess_tool_complexity(tool_name, params)
        
        if attempt <= len(assessment.escalation_levels):
            timeout = assessment.escalation_levels[attempt - 1]
        else:
            # Use max escalation for attempts beyond planned levels
            timeout = assessment.escalation_levels[-1]
        
        logger.info(f"Tool timeout - {tool_name} attempt #{attempt}: {timeout}s "
                   f"(complexity: {assessment.complexity.name})")
        
        return timeout