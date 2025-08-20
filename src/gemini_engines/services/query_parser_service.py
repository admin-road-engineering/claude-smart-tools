"""
QueryParserService - Robust query parsing with boolean operators and syntax validation
Addresses user feedback: Boolean operators like 'SECRET|PASSWORD|KEY' not working consistently
"""
import re
import logging
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum

# Conditional import of pyparsing
try:
    from pyparsing import (
        Word, alphanums, alphas, nums, QuotedString, Keyword, 
        infixNotation, opAssoc, pyparsing_common, ParseException,
        Suppress, Optional as PyParsingOptional, oneOf
    )
    PYPARSING_AVAILABLE = True
except ImportError:
    PYPARSING_AVAILABLE = False

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries supported"""
    SIMPLE_TEXT = "text"
    BOOLEAN_EXPRESSION = "boolean" 
    REGEX_PATTERN = "regex"
    WORD_BOUNDARY = "word"


@dataclass
class ParsedQuery:
    """Structured representation of a parsed query"""
    original: str
    query_type: QueryType
    terms: List[str]
    operators: List[str]
    regex_pattern: Optional[str] = None
    case_sensitive: bool = False
    word_boundaries: bool = False
    
    def __str__(self):
        return f"ParsedQuery(type={self.query_type.value}, terms={self.terms})"


class QueryParserService:
    """Service for parsing and validating search queries with boolean operators"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize pyparsing grammar if available
        if PYPARSING_AVAILABLE:
            self._init_pyparsing_grammar()
        else:
            self.logger.warning("pyparsing not available, falling back to regex parsing")
    
    def _init_pyparsing_grammar(self):
        """Initialize pyparsing grammar for boolean expressions"""
        if not PYPARSING_AVAILABLE:
            return
            
        # Define basic elements
        word = Word(alphanums + "_.-")
        quoted_string = QuotedString('"', escChar='\\') | QuotedString("'", escChar='\\')
        term = quoted_string | word
        
        # Define operators
        and_op = Keyword("AND") | Keyword("&")
        or_op = Keyword("OR") | Keyword("|")
        not_op = Keyword("NOT") | Keyword("!")
        
        # Define the grammar using infixNotation for proper precedence
        self.boolean_expr = infixNotation(
            term,
            [
                (not_op, 1, opAssoc.RIGHT),
                (and_op, 2, opAssoc.LEFT),
                (or_op, 2, opAssoc.LEFT),
            ]
        )
    
    def parse_query(self, query: str, search_type: str = "text", case_sensitive: bool = False) -> ParsedQuery:
        """
        Parse a query string into a structured ParsedQuery object
        
        Args:
            query: Raw query string
            search_type: Type hint for parsing ("text", "regex", "word")
            case_sensitive: Whether search should be case-sensitive
            
        Returns:
            ParsedQuery object with parsed structure
        """
        if not query or not query.strip():
            return ParsedQuery(
                original=query,
                query_type=QueryType.SIMPLE_TEXT,
                terms=[],
                operators=[],
                case_sensitive=case_sensitive
            )
        
        query = query.strip()
        
        # Detect query type
        detected_type = self._detect_query_type(query, search_type)
        
        if detected_type == QueryType.BOOLEAN_EXPRESSION:
            return self._parse_boolean_query(query, case_sensitive)
        elif detected_type == QueryType.REGEX_PATTERN:
            return self._parse_regex_query(query, case_sensitive)
        elif detected_type == QueryType.WORD_BOUNDARY:
            return self._parse_word_query(query, case_sensitive)
        else:
            return self._parse_simple_query(query, case_sensitive)
    
    def _detect_query_type(self, query: str, hint: str) -> QueryType:
        """Detect the type of query based on content and hint"""
        
        # Explicit hint takes precedence
        if hint == "regex":
            return QueryType.REGEX_PATTERN
        elif hint == "word":
            return QueryType.WORD_BOUNDARY
        
        # Auto-detect boolean expressions
        boolean_indicators = ['|', ' OR ', ' AND ', ' NOT ', '&', '!']
        if any(indicator in query.upper() for indicator in [' OR ', ' AND ', ' NOT ']):
            return QueryType.BOOLEAN_EXPRESSION
        if any(indicator in query for indicator in ['|', '&']) and len(query.split()) > 1:
            return QueryType.BOOLEAN_EXPRESSION
        
        # Auto-detect regex patterns
        regex_indicators = [r'\(', r'\)', r'\[', r'\]', r'\.', r'\*', r'\+', r'\?', r'\^', r'\$']
        if any(indicator in query for indicator in regex_indicators):
            return QueryType.REGEX_PATTERN
        
        return QueryType.SIMPLE_TEXT
    
    def _parse_boolean_query(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Parse boolean expressions like 'SECRET|PASSWORD|KEY' or 'auth AND token'"""
        
        if PYPARSING_AVAILABLE:
            return self._parse_with_pyparsing(query, case_sensitive)
        else:
            return self._parse_with_regex_fallback(query, case_sensitive)
    
    def _parse_with_pyparsing(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Use pyparsing for robust boolean expression parsing"""
        try:
            # Normalize operators for parsing
            normalized = query.replace('|', ' OR ').replace('&', ' AND ')
            
            # Parse the expression
            parsed = self.boolean_expr.parseString(normalized, parseAll=True)
            
            # Extract terms and operators
            terms = []
            operators = []
            self._extract_terms_and_operators(parsed[0], terms, operators)
            
            return ParsedQuery(
                original=query,
                query_type=QueryType.BOOLEAN_EXPRESSION,
                terms=terms,
                operators=operators,
                case_sensitive=case_sensitive
            )
            
        except ParseException as e:
            self.logger.debug(f"Pyparsing failed for '{query}': {e}")
            # Fallback to regex parsing
            return self._parse_with_regex_fallback(query, case_sensitive)
    
    def _parse_with_regex_fallback(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Fallback regex-based parsing for boolean expressions"""
        
        # Simple split on common boolean operators
        if '|' in query:
            terms = [term.strip() for term in query.split('|') if term.strip()]
            operators = ['OR'] * (len(terms) - 1)
        elif ' OR ' in query.upper():
            terms = [term.strip() for term in re.split(r'\s+OR\s+', query, flags=re.IGNORECASE)]
            operators = ['OR'] * (len(terms) - 1)
        elif ' AND ' in query.upper():
            terms = [term.strip() for term in re.split(r'\s+AND\s+', query, flags=re.IGNORECASE)]
            operators = ['AND'] * (len(terms) - 1)
        elif '&' in query:
            terms = [term.strip() for term in query.split('&') if term.strip()]
            operators = ['AND'] * (len(terms) - 1)
        else:
            # No clear boolean structure, treat as simple text
            return self._parse_simple_query(query, case_sensitive)
        
        return ParsedQuery(
            original=query,
            query_type=QueryType.BOOLEAN_EXPRESSION,
            terms=[t for t in terms if t],  # Remove empty terms
            operators=operators,
            case_sensitive=case_sensitive
        )
    
    def _extract_terms_and_operators(self, parsed_expr, terms: List[str], operators: List[str]):
        """Recursively extract terms and operators from pyparsing result"""
        if isinstance(parsed_expr, str):
            if parsed_expr.upper() not in ['AND', 'OR', 'NOT', '&', '|', '!']:
                terms.append(parsed_expr.strip('"\''))
            else:
                operators.append(parsed_expr.upper())
        elif hasattr(parsed_expr, '__iter__'):
            for item in parsed_expr:
                self._extract_terms_and_operators(item, terms, operators)
    
    def _parse_regex_query(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Parse regex patterns"""
        return ParsedQuery(
            original=query,
            query_type=QueryType.REGEX_PATTERN,
            terms=[query],
            operators=[],
            regex_pattern=query,
            case_sensitive=case_sensitive
        )
    
    def _parse_word_query(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Parse word boundary queries"""
        # Split into individual words for word boundary matching
        words = query.split()
        return ParsedQuery(
            original=query,
            query_type=QueryType.WORD_BOUNDARY,
            terms=words,
            operators=['AND'] * (len(words) - 1) if len(words) > 1 else [],
            case_sensitive=case_sensitive,
            word_boundaries=True
        )
    
    def _parse_simple_query(self, query: str, case_sensitive: bool) -> ParsedQuery:
        """Parse simple text queries"""
        return ParsedQuery(
            original=query,
            query_type=QueryType.SIMPLE_TEXT,
            terms=[query],
            operators=[],
            case_sensitive=case_sensitive
        )
    
    def validate_syntax(self, query: str) -> tuple[bool, str]:
        """
        Validate query syntax and return success status with error message
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query cannot be empty"
        
        try:
            parsed = self.parse_query(query)
            if not parsed.terms:
                return False, "No valid search terms found"
            return True, ""
        except Exception as e:
            return False, f"Invalid query syntax: {str(e)}"
    
    def get_suggestions(self, failed_query: str, context: Optional[Dict] = None) -> List[str]:
        """
        Generate suggestions for failed queries
        
        Args:
            failed_query: Query that returned no results
            context: Additional context like file count, sample content
            
        Returns:
            List of suggested alternative queries
        """
        suggestions = []
        
        # Basic query analysis
        if not failed_query.strip():
            return ["Try entering a search term"]
        
        query = failed_query.strip()
        
        # Boolean operator suggestions
        if '|' in query and ' OR ' not in query.upper():
            suggestions.append(f"Try: {query.replace('|', ' OR ')}")
        
        if '&' in query and ' AND ' not in query.upper():
            suggestions.append(f"Try: {query.replace('&', ' AND ')}")
        
        # Simplification suggestions
        if len(query.split()) > 1:
            first_word = query.split()[0]
            suggestions.append(f"Try broader term: '{first_word}'")
        
        # Case sensitivity suggestions  
        if query != query.lower():
            suggestions.append(f"Try lowercase: '{query.lower()}'")
        
        # Partial match suggestions
        if len(query) > 6:
            suggestions.append(f"Try partial match: '{query[:len(query)//2]}'")
        
        # Regex suggestions for complex patterns
        if any(char in query for char in ['(', ')', '[', ']', '.', '*', '+', '?']):
            suggestions.append("Try search_type='regex' for pattern matching")
        
        # Word boundary suggestions
        if ' ' in query:
            suggestions.append("Try search_type='word' for exact word matches")
        
        # Context-based suggestions
        if context:
            if context.get('files_checked', 0) == 0:
                suggestions.append("Check if paths exist: ['src/', 'lib/', 'app/']")
            
            sample = context.get('sample_content', '')
            if sample and query.lower() not in sample.lower():
                suggestions.append("Term might not exist in files - try related terms")
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    def build_search_pattern(self, parsed_query: ParsedQuery) -> Union[str, re.Pattern]:
        """
        Build a search pattern from a parsed query for use with regex or simple matching
        
        Returns:
            Either a string for simple matching or compiled regex pattern
        """
        if parsed_query.query_type == QueryType.SIMPLE_TEXT:
            return parsed_query.original
        
        elif parsed_query.query_type == QueryType.BOOLEAN_EXPRESSION:
            # Convert boolean expression to regex alternation
            if 'OR' in parsed_query.operators:
                # OR operations become alternation
                terms = [re.escape(term) for term in parsed_query.terms]
                pattern = '|'.join(terms)
            else:
                # AND operations require all terms (positive lookahead)
                terms = [re.escape(term) for term in parsed_query.terms]
                pattern = ''.join(f'(?=.*{term})' for term in terms) + '.*'
            
            flags = 0 if parsed_query.case_sensitive else re.IGNORECASE
            return re.compile(pattern, flags)
        
        elif parsed_query.query_type == QueryType.REGEX_PATTERN:
            flags = 0 if parsed_query.case_sensitive else re.IGNORECASE
            try:
                return re.compile(parsed_query.regex_pattern, flags)
            except re.error as e:
                self.logger.warning(f"Invalid regex pattern '{parsed_query.regex_pattern}': {e}")
                # Fallback to escaped literal
                escaped = re.escape(parsed_query.regex_pattern)
                return re.compile(escaped, flags)
        
        elif parsed_query.query_type == QueryType.WORD_BOUNDARY:
            # Word boundary matching
            terms = [re.escape(term) for term in parsed_query.terms]
            if len(terms) == 1:
                pattern = rf'\b{terms[0]}\b'
            else:
                # Multiple words - all must be present as whole words
                pattern = ''.join(rf'(?=.*\b{term}\b)' for term in terms) + '.*'
            
            flags = 0 if parsed_query.case_sensitive else re.IGNORECASE
            return re.compile(pattern, flags)
        
        # Fallback
        return parsed_query.original