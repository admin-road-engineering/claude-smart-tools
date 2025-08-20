"""
Centralized tool name constants to prevent orchestration lookup failures.
All tool names are standardized to snake_case for consistency.
"""

# Core Analysis Tools (Original 7 Gemini tools)
ANALYZE_CODE = "analyze_code"
SEARCH_CODE = "search_code" 
CHECK_QUALITY = "check_quality"
ANALYZE_DOCS = "analyze_docs"
ANALYZE_LOGS = "analyze_logs"
ANALYZE_DATABASE = "analyze_database"

# Enhanced Tools Phase 1 & 2 (6 additional tools)
PERFORMANCE_PROFILER = "performance_profiler"
CONFIG_VALIDATOR = "config_validator"
API_CONTRACT_CHECKER = "api_contract_checker"
TEST_COVERAGE_ANALYZER = "test_coverage_analyzer"
DEPENDENCY_MAPPER = "dependency_mapper"
INTERFACE_INCONSISTENCY_DETECTOR = "interface_inconsistency_detector"

# Additional Tools
ACCESSIBILITY_CHECKER = "accessibility_checker"

# Orchestration Tools
FULL_ANALYSIS = "full_analysis"
REVIEW_OUTPUT = "review_output"

# All tool names for validation
ALL_TOOL_NAMES = {
    ANALYZE_CODE,
    SEARCH_CODE,
    CHECK_QUALITY,
    ANALYZE_DOCS,
    ANALYZE_LOGS,
    ANALYZE_DATABASE,
    PERFORMANCE_PROFILER,
    CONFIG_VALIDATOR,
    API_CONTRACT_CHECKER,
    TEST_COVERAGE_ANALYZER,
    DEPENDENCY_MAPPER,
    INTERFACE_INCONSISTENCY_DETECTOR,
    ACCESSIBILITY_CHECKER,
    FULL_ANALYSIS,
    REVIEW_OUTPUT
}

# Tool name validation function
def validate_tool_name(tool_name: str) -> bool:
    """Validate that a tool name is in the approved set"""
    return tool_name in ALL_TOOL_NAMES

# Tool name normalization function
def normalize_tool_name(tool_name: str) -> str:
    """Normalize tool name to standard snake_case format"""
    return tool_name.lower().replace('-', '_').replace(' ', '_')