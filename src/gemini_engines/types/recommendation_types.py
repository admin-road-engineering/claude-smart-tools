"""
Recommendation Types - Data models for the enhanced tool recommendation system
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class RecommendationContext:
    """
    Encapsulates all context needed for generating tool recommendations.
    
    This dataclass provides a clean, extensible way to pass context through
    the recommendation pipeline without parameter proliferation.
    """
    # Core analysis context
    analysis_text: str
    focus: str  # security, performance, architecture, all
    detail_level: str  # summary, detailed, comprehensive
    content_type: str  # plan or code
    
    # Session context
    task_id: Optional[str] = None
    
    # Dialogue context (populated from session history)
    dialogue_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Extracted context from analysis
    mentioned_files: List[str] = field(default_factory=list)  # Validated file paths
    mentioned_but_missing: List[str] = field(default_factory=list)  # Potential hallucinations
    all_questions: List[str] = field(default_factory=list)  # All extracted questions
    
    # Hybrid mapping results
    rule_mapped_tools: List[Dict[str, Any]] = field(default_factory=list)  # From rule-based mapping
    unmapped_questions: List[str] = field(default_factory=list)  # For AI to handle
    
    # Metadata
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)  # Parsing statistics
    
    def get_summary(self) -> str:
        """Get a summary of the context for logging"""
        return (
            f"RecommendationContext("
            f"focus={self.focus}, "
            f"detail={self.detail_level}, "
            f"files={len(self.mentioned_files)}, "
            f"questions={len(self.all_questions)}, "
            f"dialogue_history={len(self.dialogue_history)} exchanges)"
        )
    
    def has_dialogue_context(self) -> bool:
        """Check if this is a continuation of an existing dialogue"""
        return bool(self.dialogue_history)
    
    def has_unmapped_questions(self) -> bool:
        """Check if there are questions that need AI mapping"""
        return bool(self.unmapped_questions)


@dataclass
class ToolRecommendation:
    """
    Represents a single tool recommendation with all necessary metadata.
    """
    tool_name: str
    parameters: Dict[str, Any]
    reason: str  # Why this tool is recommended
    answers_question: Optional[str] = None  # Specific question being answered
    expected_insights: Optional[str] = None  # What we expect to learn
    mapping_type: str = "ai"  # "rule_based" or "ai"
    confidence: float = 0.5  # 0.0 to 1.0 confidence score
    priority: int = 2  # 1=high, 2=medium, 3=low
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "tool": self.tool_name,
            "parameters": self.parameters,
            "reason": self.reason,
            "answers_question": self.answers_question,
            "expected_insights": self.expected_insights,
            "mapping_type": self.mapping_type,
            "confidence": self.confidence,
            "priority": self.priority
        }
    
    def to_executable(self) -> str:
        """Generate executable MCP command"""
        params_list = []
        for key, value in self.parameters.items():
            if isinstance(value, list):
                import json
                value_str = json.dumps(value)
            elif isinstance(value, str):
                value_str = f'"{value}"'
            else:
                value_str = str(value)
            params_list.append(f'{key}={value_str}')
        
        return f"mcp__gemini-review__{self.tool_name}({', '.join(params_list)})"


@dataclass 
class RecommendationResult:
    """
    Complete result from the recommendation system.
    """
    success: bool
    recommendations: List[ToolRecommendation]
    summary: str
    meta: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def get_tool_count_by_type(self) -> Dict[str, int]:
        """Get count of tools by mapping type"""
        counts = {"rule_based": 0, "ai": 0}
        for rec in self.recommendations:
            counts[rec.mapping_type] = counts.get(rec.mapping_type, 0) + 1
        return counts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "recommendations": {
                "tools": [r.to_dict() for r in self.recommendations],
                "summary": self.summary,
                "total_recommendations": len(self.recommendations)
            },
            "meta": self.meta,
            "error": self.error
        }