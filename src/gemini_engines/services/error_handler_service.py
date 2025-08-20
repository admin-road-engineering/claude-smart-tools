"""
ErrorHandlerService - Format structured errors into actionable user messages
Addresses user feedback: Enhanced error messages with actionable suggestions
"""
import logging
from typing import Dict, List, Optional, Any
from ..exceptions import (
    ToolingError, SearchError, NoResultsFoundError, InvalidQuerySyntaxError,
    PathError, PathNotFoundError, PermissionError, AnalysisError, TimeoutError
)


class ErrorHandlerService:
    """Service for formatting structured errors into actionable user messages"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Error code to emoji mapping for visual distinction
        self.error_icons = {
            "NO_RESULTS_FOUND": "🔍",
            "INVALID_QUERY_SYNTAX": "❓", 
            "PATH_NOT_FOUND": "📁",
            "PERMISSION_DENIED": "⚠️",
            "OPERATION_TIMEOUT": "⏱️"
        }
        
        # Context-aware suggestion templates
        self.suggestion_templates = {
            "search_broadening": [
                "Try broader terms (e.g., '{suggestion}')",
                "Use partial matching instead of exact terms",
                "Check spelling and try alternative terms"
            ],
            "query_syntax": [
                "For boolean search, use 'term1 OR term2'",
                "For regex patterns, use search_type='regex'", 
                "For exact words, use search_type='word'"
            ],
            "path_resolution": [
                "Check current directory with 'pwd' command",
                "Use absolute paths if relative paths fail",
                "Verify directory exists with file browser"
            ],
            "timeout_mitigation": [
                "Reduce scope by specifying fewer files",
                "Use verbose=False for quicker analysis",
                "Try analyzing smaller directories first"
            ]
        }
    
    def format_error(self, error: Exception, context: Optional[Dict] = None) -> str:
        """
        Format any error into a user-friendly message with suggestions
        
        Args:
            error: The exception that occurred
            context: Additional context about the operation
            
        Returns:
            Formatted error message with suggestions
        """
        if isinstance(error, ToolingError):
            return self._format_tooling_error(error, context)
        else:
            return self._format_generic_error(error, context)
    
    def _format_tooling_error(self, error: ToolingError, context: Optional[Dict] = None) -> str:
        """Format structured tooling errors with specific guidance"""
        
        # Get error icon
        icon = self.error_icons.get(error.error_code, "❌")
        
        # Build message components
        message_parts = [f"{icon} {str(error)}"]
        
        # Add context information if available
        if hasattr(error, 'files_checked') and error.files_checked > 0:
            message_parts.append(f"\n📊 Files checked: {error.files_checked}")
        
        # Add error-specific context
        if isinstance(error, NoResultsFoundError):
            message_parts.extend(self._format_no_results_context(error, context))
        elif isinstance(error, InvalidQuerySyntaxError):
            message_parts.extend(self._format_syntax_error_context(error))
        elif isinstance(error, PathNotFoundError):
            message_parts.extend(self._format_path_error_context(error))
        elif isinstance(error, TimeoutError):
            message_parts.extend(self._format_timeout_context(error))
        
        # Add suggestions
        if error.suggestions:
            message_parts.append(self._format_suggestions(error.suggestions))
        
        return "\n".join(message_parts)
    
    def _format_no_results_context(self, error: NoResultsFoundError, context: Optional[Dict]) -> List[str]:
        """Format context for no results found errors"""
        parts = []
        
        # Show sample content if available to prove we read files
        if context and context.get('sample_content'):
            sample = context['sample_content'][:100]
            parts.append(f"\n📄 Sample content (proving files were read): {sample}...")
        
        # Analyze query for better suggestions
        query = error.query.lower()
        enhanced_suggestions = []
        
        # Query-specific suggestions
        if len(query.split()) > 2:
            first_word = query.split()[0]
            enhanced_suggestions.append(f"Try simpler term: '{first_word}'")
        
        if any(char in query for char in ['|', '&']):
            enhanced_suggestions.append("Check boolean operator syntax (use 'OR' instead of '|')")
        
        if query.isupper():
            enhanced_suggestions.append(f"Try lowercase: '{query.lower()}'")
        
        if enhanced_suggestions:
            parts.append(f"\n💡 Enhanced suggestions:")
            for i, suggestion in enumerate(enhanced_suggestions[:3], 1):
                parts.append(f"  {i}. {suggestion}")
        
        return parts
    
    def _format_syntax_error_context(self, error: InvalidQuerySyntaxError) -> List[str]:
        """Format context for syntax errors"""
        parts = []
        
        # Show what went wrong
        parts.append(f"\n🔍 Syntax issue: {error.syntax_error}")
        
        # Provide examples based on query
        query = error.query
        if '|' in query:
            fixed_query = query.replace('|', ' OR ')
            parts.append(f"\n✅ Try this instead: '{fixed_query}'")
        
        return parts
    
    def _format_path_error_context(self, error: PathNotFoundError) -> List[str]:
        """Format context for path errors"""
        parts = []
        
        # Show current working directory
        import os
        parts.append(f"\n📍 Current directory: {os.getcwd()}")
        
        # Suggest common alternatives
        common_paths = ['src/', 'lib/', 'app/', '.']
        existing_paths = [p for p in common_paths if os.path.exists(p)]
        if existing_paths:
            parts.append(f"\n📁 Available directories: {', '.join(existing_paths)}")
        
        return parts
    
    def _format_timeout_context(self, error: TimeoutError) -> List[str]:
        """Format context for timeout errors"""
        parts = []
        
        parts.append(f"\n⏰ Operation timed out after {error.timeout_seconds} seconds")
        
        # Suggest scope reduction
        parts.append(f"\n💡 The {error.operation} operation was too complex for the time limit")
        
        return parts
    
    def _format_suggestions(self, suggestions: List[str]) -> str:
        """Format suggestions list into readable format"""
        if not suggestions:
            return ""
        
        if len(suggestions) == 1:
            return f"\n💡 Suggestion: {suggestions[0]}"
        
        lines = ["\n💡 Suggestions:"]
        for i, suggestion in enumerate(suggestions[:5], 1):  # Limit to top 5
            lines.append(f"  {i}. {suggestion}")
        
        return "\n".join(lines)
    
    def _format_generic_error(self, error: Exception, context: Optional[Dict] = None) -> str:
        """Format non-structured errors with basic context"""
        message = f"❌ {type(error).__name__}: {str(error)}"
        
        # Add generic suggestions based on error type
        if "timeout" in str(error).lower():
            message += self._format_suggestions(self.suggestion_templates["timeout_mitigation"])
        elif "permission" in str(error).lower():
            message += "\n💡 Try running with elevated permissions or check file access rights"
        elif "not found" in str(error).lower():
            message += "\n💡 Verify the path exists and is accessible"
        
        return message
    
    def format_search_error(self, error: SearchError, search_context: Optional[Dict] = None) -> str:
        """
        Specialized formatting for search errors with enhanced suggestions
        
        Args:
            error: Search-specific error
            search_context: Search operation context (files checked, sample content, etc.)
            
        Returns:
            Enhanced error message with search-specific guidance
        """
        if isinstance(error, NoResultsFoundError):
            return self._format_enhanced_no_results(error, search_context)
        else:
            return self.format_error(error, search_context)
    
    def _format_enhanced_no_results(self, error: NoResultsFoundError, search_context: Optional[Dict]) -> str:
        """Enhanced formatting for no results with intelligent suggestions"""
        
        message_parts = [f"🔍 No results found for '{error.query}'"]
        
        # Search statistics
        if search_context:
            files_checked = search_context.get('files_checked', 0)
            message_parts.append(f"\n📊 Search details:")
            message_parts.append(f"  • Files checked: {files_checked}")
            
            # Show paths that were searched
            if 'paths_searched' in search_context:
                paths = search_context['paths_searched'][:3]  # Show first 3
                message_parts.append(f"  • Paths searched: {', '.join(paths)}")
        
        # Intelligent suggestions based on query analysis
        suggestions = self._generate_intelligent_suggestions(error.query, search_context)
        
        if suggestions:
            message_parts.append(self._format_suggestions(suggestions))
        
        # Show sample content if we have it
        if search_context and search_context.get('sample_content'):
            sample = search_context['sample_content'][:150]
            message_parts.append(f"\n📄 Sample from searched files:\n  {sample}...")
            
            # Check if query might be in sample with different case
            if error.query.lower() in sample.lower():
                message_parts.append(f"\n⚠️ Note: Query appears in sample but wasn't matched - possible case sensitivity issue")
        
        return "\n".join(message_parts)
    
    def _generate_intelligent_suggestions(self, query: str, context: Optional[Dict]) -> List[str]:
        """Generate intelligent suggestions based on query and context"""
        suggestions = []
        
        # Query structure analysis
        words = query.split()
        
        # Boolean operator suggestions
        if '|' in query:
            suggestions.append(f"Try: {query.replace('|', ' OR ')}")
        
        if len(words) > 1:
            # Multi-word query suggestions
            suggestions.append(f"Try broader term: '{words[0]}'")
            suggestions.append(f"Try different combination: '{' '.join(words[:2])}'")
        
        # Case variations
        if query != query.lower():
            suggestions.append(f"Try lowercase: '{query.lower()}'")
        
        # Partial matching
        if len(query) > 8:
            mid_point = len(query) // 2
            suggestions.append(f"Try partial: '{query[:mid_point]}'")
        
        # Context-based suggestions
        if context:
            if context.get('files_checked', 0) == 0:
                suggestions.append("Verify search paths exist: ['src/', 'lib/', 'app/']")
            
            # File type suggestions
            if 'common_extensions' in context:
                extensions = context['common_extensions']
                suggestions.append(f"Files found: {', '.join(extensions)} - ensure query matches file contents")
        
        # Search type suggestions
        if any(char in query for char in ['.', '*', '+', '?', '^', '$']):
            suggestions.append("Try search_type='regex' for pattern matching")
        
        if ' ' in query:
            suggestions.append("Try search_type='word' for exact word matching")
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def get_actionable_suggestions(self, error_type: str, context: Dict) -> List[str]:
        """
        Get actionable suggestions for specific error types
        
        Args:
            error_type: Type of error ("search", "path", "timeout", etc.)
            context: Context information about the error
            
        Returns:
            List of actionable suggestions
        """
        if error_type in self.suggestion_templates:
            base_suggestions = self.suggestion_templates[error_type].copy()
            
            # Customize suggestions based on context
            customized = []
            for suggestion in base_suggestions:
                if '{suggestion}' in suggestion and 'query' in context:
                    # Generate contextual suggestion
                    query = context['query']
                    if len(query.split()) > 1:
                        contextual = query.split()[0]  # First word
                        customized.append(suggestion.format(suggestion=contextual))
                    else:
                        customized.append(suggestion.replace(' (e.g., \'{suggestion}\')', ''))
                else:
                    customized.append(suggestion)
            
            return customized
        
        return ["Check the operation parameters and try again"]
    
    def format_with_alternatives(self, message: str, alternatives: List[str]) -> str:
        """
        Format a message with alternative suggestions
        
        Args:
            message: Base error message
            alternatives: List of alternative approaches
            
        Returns:
            Formatted message with alternatives
        """
        if not alternatives:
            return message
        
        formatted_message = message
        formatted_message += "\n\n💡 Try these alternatives:"
        
        for i, alternative in enumerate(alternatives[:4], 1):  # Limit to 4 alternatives
            formatted_message += f"\n  {i}. {alternative}"
        
        return formatted_message