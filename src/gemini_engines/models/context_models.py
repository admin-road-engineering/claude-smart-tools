"""
Context models for cross-tool context sharing in Claude Code sessions.

These models enable tools to share insights, findings, and patterns with each other,
creating a cohesive analysis experience rather than isolated tool executions.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from enum import Enum


class CodeLocus(BaseModel):
    """
    Precise code location for granular context targeting.
    
    This enables tools to specify exactly what code they're referring to,
    allowing for more precise context sharing and avoiding ambiguity.
    """
    file_path: str = Field(..., description="Full path to the file")
    start_line: int = Field(..., description="Starting line number (1-indexed)")
    end_line: int = Field(..., description="Ending line number (inclusive)")
    function_name: Optional[str] = Field(None, description="Function/method name if applicable")
    class_name: Optional[str] = Field(None, description="Class name if applicable")
    symbol: Optional[str] = Field(None, description="Specific symbol (variable, constant, etc.)")
    
    @validator('end_line')
    def validate_line_range(cls, v, values):
        """Ensure end_line is >= start_line"""
        if 'start_line' in values and v < values['start_line']:
            raise ValueError('end_line must be >= start_line')
        return v
    
    @property
    def is_single_line(self) -> bool:
        """Check if this refers to a single line"""
        return self.start_line == self.end_line
    
    @property
    def line_count(self) -> int:
        """Get number of lines covered"""
        return self.end_line - self.start_line + 1
    
    def contains_line(self, line_number: int) -> bool:
        """Check if a line number falls within this locus"""
        return self.start_line <= line_number <= self.end_line
    
    def overlaps_with(self, other: 'CodeLocus') -> bool:
        """Check if this locus overlaps with another"""
        if self.file_path != other.file_path:
            return False
        return not (self.end_line < other.start_line or self.start_line > other.end_line)


class ContextType(str, Enum):
    """Types of context that can be shared between tools"""
    # Findings and issues
    FINDING = "finding"                    # General finding or issue
    SECURITY_FINDING = "security_finding"  # Security vulnerability or risk
    PERFORMANCE_ISSUE = "performance_issue"# Performance bottleneck or inefficiency
    BUG = "bug"                           # Identified bug or defect
    
    # Patterns and structures
    ARCHITECTURE_PATTERN = "architecture_pattern"  # Design pattern or architectural element
    CODE_PATTERN = "code_pattern"                 # Recurring code pattern
    ANTI_PATTERN = "anti_pattern"                 # Identified anti-pattern
    
    # Metrics and measurements
    METRIC = "metric"                      # General metric or measurement
    PERFORMANCE_METRIC = "performance_metric"     # Performance-related metric
    COMPLEXITY_METRIC = "complexity_metric"       # Code complexity metric
    COVERAGE_METRIC = "coverage_metric"           # Test coverage metric
    
    # Locations and references
    CODE_HOTSPOT = "code_hotspot"         # Frequently changed or critical code area
    AUTH_MODULE = "auth_module"           # Authentication/authorization module location
    CRITICAL_PATH = "critical_path"       # Critical execution path
    ENTRY_POINT = "entry_point"           # Application entry point
    
    # Dependencies and relationships
    DEPENDENCY = "dependency"              # Dependency information
    CIRCULAR_DEPENDENCY = "circular_dependency"  # Circular dependency detected
    INTERFACE = "interface"                # Interface or API definition
    
    # Recommendations and insights
    RECOMMENDATION = "recommendation"      # General recommendation
    REFACTOR_SUGGESTION = "refactor_suggestion"  # Refactoring suggestion
    OPTIMIZATION = "optimization"          # Optimization opportunity
    
    # Meta information
    TOOL_CAPABILITY = "tool_capability"   # What a tool can analyze
    ANALYSIS_SCOPE = "analysis_scope"     # Scope of analysis performed


class ContextCategory(str, Enum):
    """High-level categories for organizing context"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    QUALITY = "quality"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEPENDENCIES = "dependencies"
    CONFIGURATION = "configuration"


class ContextPriority(str, Enum):
    """Priority levels for context entries"""
    CRITICAL = "critical"  # Must be addressed immediately
    HIGH = "high"         # Important, should be addressed soon
    MEDIUM = "medium"     # Normal priority
    LOW = "low"          # Nice to have, can be deferred
    INFO = "info"        # Informational only


class ContextEntry(BaseModel):
    """
    Individual context entry that can be shared between tools.
    
    This represents a single piece of information that one tool discovers
    and other tools can use to enhance their analysis.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the context entry")
    type: ContextType = Field(..., description="Type of context")
    category: ContextCategory = Field(..., description="High-level category")
    priority: ContextPriority = Field(ContextPriority.MEDIUM, description="Priority level")
    
    # Core content
    title: str = Field(..., description="Brief title or summary")
    content: Dict[str, Any] = Field(..., description="Detailed context content")
    description: Optional[str] = Field(None, description="Human-readable description")
    
    # Source information
    source_tool: str = Field(..., description="Tool that created this context")
    source_file: Optional[str] = Field(None, description="File where context was found")
    source_line: Optional[int] = Field(None, description="Line number if applicable")
    code_locus: Optional[CodeLocus] = Field(None, description="Precise code location")
    
    # Metadata
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence score")
    tags: List[str] = Field(default_factory=list, description="Additional tags")
    related_contexts: List[str] = Field(default_factory=list, description="IDs of related context entries")
    related_context_ids: List[str] = Field(default_factory=list, description="Explicit relationships to other context entries")
    
    # Lifecycle
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When this context expires")
    session_id: Optional[str] = Field(None, description="Claude Code session ID")
    
    @validator('expires_at')
    def set_default_expiry(cls, v, values):
        """Set default expiry to 24 hours if not specified"""
        if v is None and 'created_at' in values:
            return values['created_at'] + timedelta(hours=24)
        return v
    
    @property
    def is_expired(self) -> bool:
        """Check if context has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def age_minutes(self) -> float:
        """Get age of context in minutes"""
        age = datetime.now(timezone.utc) - self.created_at
        return age.total_seconds() / 60
    
    def matches_requirements(self, required_types: Set[ContextType], 
                           required_categories: Set[ContextCategory]) -> bool:
        """Check if this context matches given requirements"""
        type_match = not required_types or self.type in required_types
        category_match = not required_categories or self.category in required_categories
        return type_match and category_match and not self.is_expired
    
    def relates_to(self, other: 'ContextEntry') -> bool:
        """Check if this context relates to another entry"""
        # Direct relationship
        if other.id in self.related_context_ids or self.id in other.related_context_ids:
            return True
        
        # Code location overlap
        if self.code_locus and other.code_locus:
            return self.code_locus.overlaps_with(other.code_locus)
        
        # Same file and close lines
        if self.source_file and other.source_file:
            if self.source_file == other.source_file:
                if self.source_line and other.source_line:
                    return abs(self.source_line - other.source_line) <= 10
        
        return False


class ToolContextRequirements(BaseModel):
    """
    Specification of what context a tool needs and can provide.
    
    This allows tools to declare their context dependencies and contributions,
    enabling intelligent context routing.
    """
    tool_name: str = Field(..., description="Name of the tool")
    
    # What the tool needs
    required_context_types: Set[ContextType] = Field(
        default_factory=set, 
        description="Context types this tool requires"
    )
    optional_context_types: Set[ContextType] = Field(
        default_factory=set,
        description="Context types that enhance but aren't required"
    )
    required_categories: Set[ContextCategory] = Field(
        default_factory=set,
        description="Categories of context this tool needs"
    )
    
    # What the tool provides
    provides_context_types: Set[ContextType] = Field(
        default_factory=set,
        description="Context types this tool can provide"
    )
    provides_categories: Set[ContextCategory] = Field(
        default_factory=set,
        description="Categories this tool contributes to"
    )
    
    # Processing hints
    max_context_age_minutes: Optional[float] = Field(
        None,
        description="Maximum age of context this tool will use"
    )
    prefers_high_confidence: bool = Field(
        False,
        description="Whether tool prefers high confidence context only"
    )
    
    def can_use_context(self, context: ContextEntry) -> bool:
        """Check if this tool can use a given context entry"""
        # Check type requirements
        type_match = (
            context.type in self.required_context_types or
            context.type in self.optional_context_types
        )
        
        # Check category requirements
        category_match = (
            not self.required_categories or
            context.category in self.required_categories
        )
        
        # Check age requirements
        age_ok = (
            self.max_context_age_minutes is None or
            context.age_minutes <= self.max_context_age_minutes
        )
        
        # Check confidence requirements
        confidence_ok = (
            not self.prefers_high_confidence or
            context.confidence >= 0.7
        )
        
        return type_match and category_match and age_ok and confidence_ok


class ContextCollection(BaseModel):
    """
    Collection of context entries for a session or analysis.
    
    This represents all the shared context available during a Claude Code session.
    """
    session_id: str = Field(..., description="Session identifier")
    entries: List[ContextEntry] = Field(default_factory=list, description="All context entries")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_context(self, entry: ContextEntry) -> None:
        """Add a new context entry to the collection"""
        entry.session_id = self.session_id
        self.entries.append(entry)
    
    def get_context_for_tool(self, requirements: ToolContextRequirements) -> List[ContextEntry]:
        """Get relevant context for a tool based on its requirements"""
        relevant = []
        for entry in self.entries:
            if requirements.can_use_context(entry):
                relevant.append(entry)
        
        # Sort by priority and confidence
        priority_order = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.MEDIUM: 2,
            ContextPriority.LOW: 3,
            ContextPriority.INFO: 4
        }
        
        relevant.sort(key=lambda e: (priority_order[e.priority], -e.confidence))
        return relevant
    
    def get_by_type(self, context_type: ContextType) -> List[ContextEntry]:
        """Get all context entries of a specific type"""
        return [e for e in self.entries if e.type == context_type and not e.is_expired]
    
    def get_by_category(self, category: ContextCategory) -> List[ContextEntry]:
        """Get all context entries in a specific category"""
        return [e for e in self.entries if e.category == category and not e.is_expired]
    
    def get_by_source_tool(self, tool_name: str) -> List[ContextEntry]:
        """Get all context entries created by a specific tool"""
        return [e for e in self.entries if e.source_tool == tool_name]
    
    def remove_expired(self) -> int:
        """Remove expired context entries and return count removed"""
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if not e.is_expired]
        return original_count - len(self.entries)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics about the context collection"""
        type_counts = {}
        category_counts = {}
        tool_counts = {}
        
        for entry in self.entries:
            if not entry.is_expired:
                type_counts[entry.type] = type_counts.get(entry.type, 0) + 1
                category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
                tool_counts[entry.source_tool] = tool_counts.get(entry.source_tool, 0) + 1
        
        return {
            'total_entries': len(self.entries),
            'active_entries': len([e for e in self.entries if not e.is_expired]),
            'types': type_counts,
            'categories': category_counts,
            'source_tools': tool_counts,
            'high_priority_count': len([e for e in self.entries 
                                      if e.priority in [ContextPriority.CRITICAL, ContextPriority.HIGH]
                                      and not e.is_expired])
        }
    
    def merge_related_contexts(self, merge_strategy: str = "consensus") -> List[ContextEntry]:
        """
        Merge related context entries using specified strategy.
        
        Strategies:
        - consensus: Keep entry with highest confidence when multiple tools report on same code
        - union: Combine findings from all tools into comprehensive entry
        - latest: Keep most recent entry when conflicts exist
        
        Args:
            merge_strategy: Strategy to use for merging
            
        Returns:
            List of merged context entries
        """
        # Group related contexts
        context_groups = []
        processed = set()
        
        for entry in self.entries:
            if entry.id in processed or entry.is_expired:
                continue
                
            # Find all related entries
            group = [entry]
            processed.add(entry.id)
            
            for other in self.entries:
                if other.id in processed or other.is_expired:
                    continue
                    
                if entry.relates_to(other):
                    group.append(other)
                    processed.add(other.id)
            
            if len(group) > 1:
                context_groups.append(group)
            else:
                # Single entry, no merging needed
                context_groups.append(group)
        
        # Merge each group according to strategy
        merged_entries = []
        
        for group in context_groups:
            if len(group) == 1:
                merged_entries.append(group[0])
                continue
            
            if merge_strategy == "consensus":
                # Keep highest confidence entry
                best_entry = max(group, key=lambda e: (e.confidence, e.priority == ContextPriority.CRITICAL))
                # Add related context IDs from other entries
                for other in group:
                    if other.id != best_entry.id:
                        best_entry.related_context_ids.append(other.id)
                merged_entries.append(best_entry)
                
            elif merge_strategy == "union":
                # Create comprehensive entry combining all findings
                union_entry = group[0].copy()
                union_entry.title = f"[Merged] {union_entry.title}"
                union_entry.content['merged_from'] = [e.source_tool for e in group]
                union_entry.content['all_findings'] = [e.content for e in group]
                union_entry.confidence = max(e.confidence for e in group)
                union_entry.priority = min(group, key=lambda e: [ContextPriority.CRITICAL, ContextPriority.HIGH, 
                                                                 ContextPriority.MEDIUM, ContextPriority.LOW, 
                                                                 ContextPriority.INFO].index(e.priority)).priority
                for other in group[1:]:
                    union_entry.related_context_ids.append(other.id)
                    union_entry.tags.extend(other.tags)
                union_entry.tags = list(set(union_entry.tags))  # Remove duplicates
                merged_entries.append(union_entry)
                
            elif merge_strategy == "latest":
                # Keep most recent entry
                latest_entry = max(group, key=lambda e: e.created_at)
                for other in group:
                    if other.id != latest_entry.id:
                        latest_entry.related_context_ids.append(other.id)
                merged_entries.append(latest_entry)
                
            else:
                # Unknown strategy, keep all
                merged_entries.extend(group)
        
        return merged_entries


class ContextFlow(BaseModel):
    """
    Represents the flow of context between tools during analysis.
    
    This helps visualize and understand how information flows through
    the analysis pipeline.
    """
    session_id: str = Field(..., description="Session identifier")
    flows: List[Dict[str, Any]] = Field(default_factory=list, description="Context flow records")
    
    def record_flow(self, from_tool: str, to_tool: str, context_id: str, 
                   context_type: ContextType) -> None:
        """Record a context flow from one tool to another"""
        self.flows.append({
            'from_tool': from_tool,
            'to_tool': to_tool,
            'context_id': context_id,
            'context_type': context_type,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def get_tool_dependencies(self) -> Dict[str, Set[str]]:
        """Get which tools depend on which other tools for context"""
        dependencies = {}
        for flow in self.flows:
            to_tool = flow['to_tool']
            from_tool = flow['from_tool']
            if to_tool not in dependencies:
                dependencies[to_tool] = set()
            dependencies[to_tool].add(from_tool)
        return dependencies
    
    def get_most_connected_tools(self) -> List[tuple[str, int]]:
        """Get tools sorted by how many connections they have"""
        connections = {}
        for flow in self.flows:
            for tool in [flow['from_tool'], flow['to_tool']]:
                connections[tool] = connections.get(tool, 0) + 1
        
        return sorted(connections.items(), key=lambda x: x[1], reverse=True)