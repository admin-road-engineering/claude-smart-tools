"""
Pydantic validation models for all MCP tool requests.

Provides type-safe input validation for all 13 Gemini MCP tools,
replacing raw dictionary argument handling with validated models.
"""
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional, Union, Dict, Any
from enum import Enum
from pathlib import Path


# Enums for better type safety
class AnalysisType(str, Enum):
    """Analysis types for analyze_code tool"""
    OVERVIEW = "overview"
    DEPENDENCIES = "dependencies" 
    REFACTOR_PREP = "refactor_prep"
    ARCHITECTURE = "architecture"
    RESEARCH = "research"


class OutputFormat(str, Enum):
    """Output format options"""
    TEXT = "text"
    MARKDOWN = "markdown"


class SearchType(str, Enum):
    """Search types for search_code tool"""
    TEXT = "text"
    REGEX = "regex"
    WORD = "word"


class CheckType(str, Enum):
    """Quality check types"""
    ALL = "all"
    TESTS = "tests"
    SECURITY = "security"
    PERFORMANCE = "performance"


class SynthesisType(str, Enum):
    """Documentation synthesis types"""
    SUMMARY = "summary"
    COMPARISON = "comparison"
    IMPLEMENTATION_GUIDE = "implementation_guide"
    API_REFERENCE = "api_reference"


class LogFocus(str, Enum):
    """Log analysis focus areas"""
    ERRORS = "errors"
    PERFORMANCE = "performance"
    PATTERNS = "patterns"
    TIMELINE = "timeline"
    ALL = "all"


class DatabaseAnalysisType(str, Enum):
    """Database analysis types"""
    SCHEMA = "schema"
    MIGRATIONS = "migrations"
    RELATIONSHIPS = "relationships"
    OPTIMIZATION = "optimization"


class ProfileType(str, Enum):
    """Performance profiling types"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    COMPREHENSIVE = "comprehensive"


class ValidationType(str, Enum):
    """Configuration validation types"""
    SECURITY = "security"
    COMPLETENESS = "completeness"
    SYNTAX = "syntax"
    ALL = "all"


class ComparisonMode(str, Enum):
    """API contract comparison modes"""
    STANDALONE = "standalone"
    COMPARE_VERSIONS = "compare_versions"
    BREAKING_CHANGES = "breaking_changes"


class MappingStrategy(str, Enum):
    """Test mapping strategies"""
    CONVENTION = "convention"
    DIRECTORY = "directory"
    DOCSTRING = "docstring"


class AnalysisDepth(str, Enum):
    """Dependency analysis depth"""
    IMMEDIATE = "immediate"
    TRANSITIVE = "transitive"
    FULL = "full"


class PatternType(str, Enum):
    """Interface pattern types"""
    NAMING = "naming"
    PARAMETERS = "parameters"
    RETURN_TYPES = "return_types"
    DOCUMENTATION = "documentation"


class Focus(str, Enum):
    """Review focus areas"""
    ALL = "all"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    DEBUGGING = "debugging"
    COMPLIANCE = "compliance"
    ARCHITECTURE = "architecture"
    USABILITY = "usability"


# Validation Models for Each Tool

class AnalyzeCodeRequest(BaseModel):
    """Validation model for analyze_code tool"""
    paths: List[str] = Field(..., description="File or directory paths to analyze")
    analysis_type: AnalysisType = Field(AnalysisType.OVERVIEW, description="Type of analysis to perform")
    output_format: OutputFormat = Field(OutputFormat.TEXT, description="Output format")
    question: Optional[str] = Field(None, description="Specific question to answer about the code")
    verbose: bool = Field(True, description="Enable verbose output")

    @validator('paths')
    def validate_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one path must be provided")
        return v


class SearchCodeRequest(BaseModel):
    """Validation model for search_code tool"""
    query: str = Field(..., min_length=1, description="Search query")
    paths: Optional[List[str]] = Field(None, description="Paths to search within")
    search_type: SearchType = Field(SearchType.TEXT, description="Type of search to perform")
    case_sensitive: bool = Field(False, description="Case sensitive search")
    context_question: Optional[str] = Field(None, description="What you want to understand about the results")
    output_format: OutputFormat = Field(OutputFormat.TEXT, description="Output format")


class CheckQualityRequest(BaseModel):
    """Validation model for check_quality tool"""
    paths: List[str] = Field(..., description="Code paths to analyze")
    check_type: CheckType = Field(CheckType.ALL, description="Type of quality check")
    test_paths: Optional[List[str]] = Field(None, description="Test file paths")
    output_format: OutputFormat = Field(OutputFormat.TEXT, description="Output format")
    verbose: bool = Field(True, description="Enable verbose output")

    @validator('paths')
    def validate_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one path must be provided")
        return v


class AnalyzeDocsRequest(BaseModel):
    """Validation model for analyze_docs tool"""
    sources: List[Union[str, HttpUrl]] = Field(..., description="Local file paths or URLs to analyze")
    questions: Optional[List[str]] = Field(None, description="Specific questions to answer from the documentation")
    synthesis_type: SynthesisType = Field(SynthesisType.SUMMARY, description="Type of synthesis to perform")

    @validator('sources')
    def validate_sources_not_empty(cls, v):
        if not v:
            raise ValueError("At least one source must be provided")
        return v


class AnalyzeLogsRequest(BaseModel):
    """Validation model for analyze_logs tool"""
    log_paths: List[str] = Field(..., description="Log file or directory paths")
    focus: LogFocus = Field(LogFocus.ALL, description="Focus area for analysis")
    time_range: Optional[str] = Field(None, description="Optional time range to focus on")

    @validator('log_paths')
    def validate_log_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one log path must be provided")
        return v


class AnalyzeDatabaseRequest(BaseModel):
    """Validation model for analyze_database tool"""
    schema_paths: List[str] = Field(..., description="Schema, migration, or model file paths")
    analysis_type: DatabaseAnalysisType = Field(DatabaseAnalysisType.SCHEMA, description="Type of database analysis")
    repo_paths: Optional[List[str]] = Field(None, description="Repository paths for cross-repo analysis")

    @validator('schema_paths')
    def validate_schema_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one schema path must be provided")
        return v


class PerformanceProfilerRequest(BaseModel):
    """Validation model for performance_profiler tool"""
    target_operation: str = Field(
        ..., 
        description="Operation or script to profile",
        min_length=1,
        # Basic pattern to prevent obvious accidents - trust the user for complex cases
        pattern=r'^[a-zA-Z0-9\s\-_\.\(\);"=,\/\\:]+$'
    )
    profile_type: ProfileType = Field(ProfileType.COMPREHENSIVE, description="Type of profiling to perform")


class ConfigValidatorRequest(BaseModel):
    """Validation model for config_validator tool"""
    config_paths: List[str] = Field(..., description="Configuration file paths to validate")
    validation_type: ValidationType = Field(ValidationType.ALL, description="Type of validation to perform")

    @validator('config_paths')
    def validate_config_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one config path must be provided")
        return v


class ApiContractCheckerRequest(BaseModel):
    """Validation model for api_contract_checker tool"""
    spec_paths: List[str] = Field(..., description="OpenAPI/Swagger specification file paths")
    comparison_mode: ComparisonMode = Field(ComparisonMode.STANDALONE, description="Comparison mode")

    @validator('spec_paths')
    def validate_spec_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one spec path must be provided")
        return v


class AnalyzeTestCoverageRequest(BaseModel):
    """Validation model for analyze_test_coverage tool"""
    source_paths: List[str] = Field(..., description="Source code paths to analyze for test coverage")
    mapping_strategy: MappingStrategy = Field(MappingStrategy.CONVENTION, description="Strategy for mapping tests to source")

    @validator('source_paths')
    def validate_source_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one source path must be provided")
        return v


class MapDependenciesRequest(BaseModel):
    """Validation model for map_dependencies tool"""
    project_paths: List[str] = Field(..., description="Project directories to analyze for dependencies")
    analysis_depth: AnalysisDepth = Field(AnalysisDepth.TRANSITIVE, description="Depth of dependency analysis")

    @validator('project_paths')
    def validate_project_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one project path must be provided")
        return v


class InterfaceInconsistencyDetectorRequest(BaseModel):
    """Validation model for interface_inconsistency_detector tool"""
    source_paths: List[str] = Field(..., description="Source code paths to analyze for inconsistencies")
    pattern_types: List[PatternType] = Field(
        [PatternType.NAMING, PatternType.PARAMETERS], 
        description="Types of patterns to analyze"
    )

    @validator('source_paths')
    def validate_source_paths_not_empty(cls, v):
        if not v:
            raise ValueError("At least one source path must be provided")
        return v


class FullAnalysisRequest(BaseModel):
    """Validation model for full_analysis tool"""
    task_id: Optional[str] = Field(None, description="Session task ID (None for new session)")
    files: Optional[List[str]] = Field(None, description="Files to analyze")
    focus: Focus = Field(Focus.ALL, description="Focus area for comprehensive review")
    claude_response: Optional[str] = Field(None, description="Claude's response in ongoing dialogue")
    context: Optional[str] = Field(None, description="Additional context for review")
    autonomous: bool = Field(False, description="Run in autonomous mode (True) or dialogue mode (False). Default is dialogue mode.")


# Mapping of tool names to their validation models
TOOL_REQUEST_MODELS = {
    "analyze_code": AnalyzeCodeRequest,
    "search_code": SearchCodeRequest,
    "check_quality": CheckQualityRequest,
    "analyze_docs": AnalyzeDocsRequest,
    "analyze_logs": AnalyzeLogsRequest,
    "analyze_database": AnalyzeDatabaseRequest,
    "performance_profiler": PerformanceProfilerRequest,
    "config_validator": ConfigValidatorRequest,
    "api_contract_checker": ApiContractCheckerRequest,
    "analyze_test_coverage": AnalyzeTestCoverageRequest,
    "map_dependencies": MapDependenciesRequest,
    "interface_inconsistency_detector": InterfaceInconsistencyDetectorRequest,
    "full_analysis": FullAnalysisRequest,
}


def validate_tool_request(tool_name: str, arguments: Dict[str, Any]) -> BaseModel:
    """
    Validate tool request arguments using the appropriate Pydantic model.
    
    Args:
        tool_name: Name of the tool being called
        arguments: Raw arguments dictionary from MCP
        
    Returns:
        Validated model instance
        
    Raises:
        ValueError: If tool_name is unknown or validation fails
    """
    if tool_name not in TOOL_REQUEST_MODELS:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    model_class = TOOL_REQUEST_MODELS[tool_name]
    return model_class(**arguments)