"""
Intent parsing service for natural language understanding in dialogue.
Provides robust two-stage parsing with Gemini AI fallback for complex intents.
"""
import ast
import json
import logging
import re
from typing import Dict, List, Any, Optional

from ..tools.interfaces import IIntentParser, IntentParserConfig
from ..clients.gemini_client import GeminiClient
from ..models.dialogue_models import IntentResult, IntentAction, SessionContext

logger = logging.getLogger(__name__)


class IntentParser(IIntentParser):
    """
    Two-stage intent parser that handles user responses in comprehensive review dialogue.
    Stage 1: Fast keyword detection for common actions
    Stage 2: Gemini AI for complex intent extraction with safe JSON parsing
    """
    
    def __init__(self, 
                 gemini_client: GeminiClient = None, 
                 config: IntentParserConfig = None):
        """
        Initialize IntentParser with AI client and configuration.
        
        Args:
            gemini_client: Gemini client for AI parsing
            config: Parser configuration
        """
        self.gemini_client = gemini_client or GeminiClient()
        self.config = config or IntentParserConfig()
        
        # Common tool name mappings for fuzzy matching
        self.tool_name_mappings = {
            'config': 'config_validator',
            'configuration': 'config_validator',
            'security': 'config_validator',
            'dependency': 'dependency_mapper',
            'dependencies': 'dependency_mapper',
            'deps': 'dependency_mapper',
            'test': 'test_coverage_analyzer',
            'testing': 'test_coverage_analyzer',
            'coverage': 'test_coverage_analyzer',
            'api': 'api_contract_checker',
            'contract': 'api_contract_checker',
            'interface': 'interface_inconsistency_detector',
            'consistency': 'interface_inconsistency_detector',
            'performance': 'performance_profiler',
            'perf': 'performance_profiler',
            'accessibility': 'accessibility_checker',
            'a11y': 'accessibility_checker'
        }
    
    async def _is_technical_response_llm(self, user_response: str, session_context: SessionContext = None) -> Dict[str, Any]:
        """
        Use LLM classification to detect technical responses with high accuracy.
        
        This is more robust than pattern matching and adapts to diverse expressions.
        
        Args:
            user_response: User's input text
            session_context: Optional session context for better classification
            
        Returns:
            Dictionary with classification results
        """
        try:
            # Build context-aware prompt
            context_info = ""
            if session_context:
                context_summary = session_context.get_context_summary()
                if context_summary != "New session":
                    context_info = f"\n**Session Context**: {context_summary}"
            
            classification_prompt = f"""You are a dialogue intent classifier for a technical code review system. 

The user has just received an AI-generated code review and analysis. Classify their response.

{context_info}

**User Response**:
"{user_response}"

**Classification Task**:
Is this user response:
A) A **new command** (like "run config", "synthesize", "help", "done")
B) A **technical continuation** of the discussion (analysis, questions, debugging insights, code references)

**Instructions**:
- Technical continuation includes: code analysis, debugging insights, questions about findings, references to functions/files/errors, architectural discussion
- New commands are explicit instructions like "run [tool]", "synthesize", "help", "done"
- Ambiguous cases should favor "CONTINUE_DIALOGUE" for better user experience

Respond with ONLY a JSON object:
{{"classification": "CONTINUE_DIALOGUE" or "NEW_COMMAND", "confidence": 0.0-1.0, "detected_topics": ["topic1", "topic2"], "reasoning": "brief explanation"}}"""
            
            # Call Gemini with fast model for quick classification
            response, model_used, attempts = await self.gemini_client.generate_content(
                classification_prompt,
                model_name='flash',  # Fast model for classification
                timeout=15  # Quick timeout for responsiveness
            )
            
            # Parse response
            classification = self._safe_json_loads(response)
            
            if classification and 'classification' in classification:
                return {
                    'is_technical': classification['classification'] == 'CONTINUE_DIALOGUE',
                    'confidence': classification.get('confidence', 0.8),
                    'detected_topics': classification.get('detected_topics', []),
                    'reasoning': classification.get('reasoning', ''),
                    'method': 'llm_classification',
                    'model_used': model_used
                }
            else:
                # Fallback if parsing failed
                logger.warning(f"LLM classification failed to parse response: {response[:100]}")
                return self._fallback_technical_detection(user_response)
                
        except Exception as e:
            logger.error(f"LLM technical response detection failed: {e}")
            return self._fallback_technical_detection(user_response)
    
    def _fallback_technical_detection(self, user_response: str) -> Dict[str, Any]:
        """
        Fallback technical response detection using pattern matching.
        
        Used when LLM classification fails or is unavailable.
        """
        response_lower = user_response.lower()
        
        # Technical indicators with scoring
        technical_patterns = [
            # Code structure indicators
            (r'`[^`]+`', 2),  # Inline code
            (r'```', 3),  # Code blocks
            (r'\bclass\s+\w+', 2),  # Class references
            (r'\bdef\s+\w+', 2),  # Function definitions
            (r'\w+\(\)', 2),  # Function calls
            
            # File and path indicators
            (r'src/\w+', 2),  # Source paths
            (r'\w+\.py', 2),  # Python files
            (r'line\s+\d+', 2),  # Line references
            
            # Technical discussion
            (r'\b(root cause|debugging|analysis|implementation|architecture)', 2),
            (r'\b(error|exception|traceback|stack trace)', 2),
            (r'\b(api|database|schema|endpoint)', 1),
            (r'\b(bug|issue|problem|solution)', 1),
            
            # Specific technical terms
            (r'\b(authentication|authorization|jwt|token)', 2),
            (r'\b(credentials|secrets|config)', 2),
            (r'\b(function|method|variable|class)', 1)
        ]
        
        # Calculate technical score
        technical_score = 0
        detected_patterns = []
        
        for pattern, weight in technical_patterns:
            matches = re.findall(pattern, user_response, re.IGNORECASE)
            if matches:
                technical_score += weight * len(matches)
                detected_patterns.append(pattern)
        
        # Length bonus for substantial responses
        if len(user_response) > 100:
            technical_score += 1
        
        # Simple command detection (overrides technical detection)
        simple_commands = ['help', 'done', 'synthesize', 'retry', 'explain', 'continue']
        is_simple_command = any(cmd in response_lower for cmd in simple_commands)
        
        if is_simple_command:
            is_technical = False
            confidence = 0.9
        else:
            # Technical threshold
            is_technical = technical_score >= 3
            confidence = min(technical_score / 10.0, 0.9)  # Max 0.9 confidence for pattern matching
        
        return {
            'is_technical': is_technical,
            'confidence': confidence,
            'detected_topics': ['general_technical'] if is_technical else [],
            'reasoning': f'Pattern matching: score={technical_score}, patterns={len(detected_patterns)}',
            'method': 'pattern_matching',
            'technical_score': technical_score
        }
    
    async def parse_user_intent(self, user_response: str, session_context: SessionContext = None) -> IntentResult:
        """
        Parse user's natural language response into structured intent.
        
        Args:
            user_response: User's text input
            
        Returns:
            IntentResult with structured intent data and confidence
        """
        if not user_response or not user_response.strip():
            return IntentResult(
                action=IntentAction.UNKNOWN,
                confidence=0.0,
                parsing_method="validation_error",
                raw_user_input=user_response or "",
                clarification_needed=True,
                suggested_actions=["Please provide a valid input or command"]
            )
        
        logger.debug(f"Parsing intent from: {user_response[:100]}...")
        
        # Stage 1: Fast keyword detection
        primary_action = self._detect_primary_action(user_response)
        
        # Stage 2: Check for technical response continuation (NEW)
        if primary_action == 'unknown' and len(user_response) > 50:
            # Use LLM-based technical response detection for unknown intents
            technical_result = await self._is_technical_response_llm(user_response, session_context)
            
            if technical_result['is_technical'] and technical_result['confidence'] > 0.6:
                # Treat as technical dialogue continuation
                return IntentResult(
                    action=IntentAction.CONTINUE_DIALOGUE,
                    confidence=technical_result['confidence'],
                    parsing_method=technical_result['method'],
                    raw_user_input=user_response,
                    extracted_entities={
                        'detected_topics': technical_result.get('detected_topics', []),
                        'reasoning': technical_result.get('reasoning', ''),
                        'is_technical_response': True,
                        'model_used': technical_result.get('model_used', 'pattern_matching')
                    }
                )
        
        # Stage 3: AI-powered parsing for complex intents (existing logic)
        if primary_action in ['run_tool', 'specify_files', 'unknown']:
            return await self._ai_enhanced_parsing(user_response, primary_action)
        else:
            # Simple intents don't need AI parsing
            return IntentResult(
                action=self._string_to_intent_action(primary_action),
                confidence=0.9,
                parsing_method="keyword_detection",
                raw_user_input=user_response
            )
    
    def _detect_primary_action(self, response: str) -> str:
        """
        Stage 1: Fast keyword-based action detection.
        
        Args:
            response: User response text
            
        Returns:
            Primary action string
        """
        response_lower = response.lower().strip()
        
        # Action detection patterns (order matters - more specific first)
        action_patterns = [
            (['run', 'execute', 'analyze', 'check'], 'run_tool'),
            (['explain', 'clarify', 'tell me more', 'what about', 'details'], 'explain'),
            (['synthesize', 'summary', 'final report', 'overall', 'combine'], 'synthesize'),
            (['done', 'finish', 'end', 'complete', 'stop', 'exit'], 'end_session'),
            (['retry', 'try again', 'run again'], 'retry_failed'),
            (['continue', 'proceed', 'next'], 'continue'),
            (['help', 'options', 'what can'], 'help'),
            (['files=', 'directories=', 'paths='], 'specify_files')
        ]
        
        for keywords, action in action_patterns:
            if any(keyword in response_lower for keyword in keywords):
                return action
        
        return 'unknown'
    
    async def _ai_enhanced_parsing(self, response: str, primary_action: str) -> IntentResult:
        """
        Stage 2: Use Gemini AI for complex intent extraction.
        
        Args:
            response: User response text
            primary_action: Primary action from stage 1
            
        Returns:
            IntentResult with enhanced parsing from AI
        """
        try:
            # Build extraction prompt
            extraction_prompt = self._build_extraction_prompt(response, primary_action)
            
            # Call Gemini for structured extraction
            structured_intent_str, _, _ = await self.gemini_client.generate_content(
                prompt=extraction_prompt,
                model_name=self.config.model_name,
                timeout=self.config.timeout_seconds
            )
            
            # Parse JSON response safely
            parsed_intent = self._safe_json_loads(structured_intent_str)
            
            if parsed_intent:
                # Enhance with fuzzy tool name matching
                parsed_intent = self._enhance_tool_names(parsed_intent)
                confidence = min(parsed_intent.get('confidence', 0.8), 1.0)
                
                return IntentResult(
                    action=self._string_to_intent_action(parsed_intent.get('action', primary_action)),
                    confidence=confidence,
                    tool_name=parsed_intent.get('tool_name'),
                    files=parsed_intent.get('files', []),
                    directories=parsed_intent.get('directories', []),
                    parsing_method="ai_enhanced",
                    raw_user_input=response,
                    extracted_entities={
                        'parameters': parsed_intent.get('parameters', {}),
                        'reasoning': parsed_intent.get('reasoning', ''),
                        'tool_name_matched': parsed_intent.get('tool_name_matched', False),
                        'original_tool_name': parsed_intent.get('original_tool_name')
                    }
                )
            else:
                # Fallback if JSON parsing failed
                return await self._fallback_parsing(response, primary_action)
                
        except Exception as e:
            logger.error(f"AI-enhanced parsing failed: {e}")
            return await self._fallback_parsing(response, primary_action, str(e))
    
    def _build_extraction_prompt(self, response: str, primary_action: str) -> str:
        """Build prompt for Gemini intent extraction"""
        
        tool_names = list(self.tool_name_mappings.values())
        unique_tools = list(set(tool_names))
        
        prompt = f"""Extract structured information from this user request for a comprehensive code review system.

User Request: "{response}"
Detected Primary Action: {primary_action}

Available Tools: {', '.join(unique_tools)}

Return JSON with these fields:
- action: the intended action ({primary_action} or refined version)
- tool_name: specific tool name from available tools (if running a tool)
- files: array of file paths mentioned (extract from patterns like "src/", "*.py", "config.json")
- directories: array of directory paths mentioned
- parameters: object with any tool-specific parameters
- confidence: confidence level 0.0-1.0
- reasoning: brief explanation of parsing decisions

Examples:
Input: "Run config validator on src/config.py"
Output: {{"action": "run_tool", "tool_name": "config_validator", "files": ["src/config.py"], "confidence": 0.9}}

Input: "Check dependencies in the src directory"
Output: {{"action": "run_tool", "tool_name": "dependency_mapper", "directories": ["src/"], "confidence": 0.85}}

Input: "files=['app.py', 'utils.py']"
Output: {{"action": "specify_files", "files": ["app.py", "utils.py"], "confidence": 0.95}}

Response (JSON only):"""
        
        return prompt
    
    def _safe_json_loads(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON from Gemini response, handling common LLM errors.
        
        Args:
            text: Potentially malformed JSON text
            
        Returns:
            Parsed dictionary or None if parsing fails
        """
        if not text:
            return None
        
        try:
            # Try to find JSON block within code fences
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            
            # Look for JSON object boundaries
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                text = text[json_start:json_end + 1]
            
            # Clean up common JSON issues
            # Remove trailing commas before closing braces/brackets
            text = re.sub(r',\s*([\}\]])', r'\1', text)
            
            # Remove comments (not valid JSON)
            text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
            
            # Parse the cleaned JSON
            result = json.loads(text)
            
            # Validate required fields
            if isinstance(result, dict) and 'action' in result:
                return result
            else:
                logger.warning("Parsed JSON missing required 'action' field")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}. Text: {text[:200]}...")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in JSON parsing: {e}")
            return None
    
    def _enhance_tool_names(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance tool names using fuzzy matching against known tools.
        
        Args:
            intent: Parsed intent dictionary
            
        Returns:
            Intent with enhanced tool name matching
        """
        tool_name = intent.get('tool_name', '')
        if not tool_name:
            return intent
        
        tool_name_lower = tool_name.lower()
        
        # Direct mapping
        if tool_name_lower in self.tool_name_mappings:
            intent['tool_name'] = self.tool_name_mappings[tool_name_lower]
            intent['tool_name_matched'] = True
            return intent
        
        # Partial matching
        for key, mapped_name in self.tool_name_mappings.items():
            if key in tool_name_lower or tool_name_lower in key:
                intent['tool_name'] = mapped_name
                intent['tool_name_matched'] = True
                intent['original_tool_name'] = tool_name
                break
        
        return intent
    
    async def _fallback_parsing(self, response: str, primary_action: str, error: str = None) -> IntentResult:
        """
        Fallback parsing when AI extraction fails.
        Uses regex patterns and heuristics.
        
        Args:
            response: User response
            primary_action: Detected primary action
            error: Error that caused fallback
            
        Returns:
            IntentResult from fallback parsing
        """
        logger.info(f"Using fallback parsing for: {response[:50]}...")
        
        # Start with basic intent data
        confidence = 0.6  # Lower confidence for fallback
        extracted_files = set()  # Use set to avoid duplicates
        extracted_directories = set()  # Use set to avoid duplicates
        tool_name = None
        
        # Extract file patterns with regex
        file_patterns = [
            r'files?\s*=\s*\[(.*?)\]',  # files=['file1', 'file2']
            r'(?:analyze|check|run)\s+(?:on\s+)?([\w\./]+\.[\w]+)',  # "analyze config.py"
            r'(?:in|from)\s+([\w\./\\-]+/?)',  # "in src/" or "from tests"
            r'([\w\./\\-]+/)',  # Directory paths ending with /
            r'([\w\./]+\.(?:py|js|json|yaml|yml|env))',  # Direct file mentions
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ''
                
                # Special handling for list pattern: files=['file1', 'file2']
                if pattern == r'files?\s*=\s*\[(.*?)\]' and match:
                    try:
                        # Use ast.literal_eval for safe and accurate parsing of Python list literals
                        file_list = ast.literal_eval(f"[{match}]")
                        if not isinstance(file_list, list):
                            raise ValueError("Parsed result is not a list")
                        
                        # Process each item in the safely parsed list
                        for item in file_list:
                            item_str = str(item).strip()
                            if not item_str:
                                continue
                            
                            if item_str.endswith('/'):
                                extracted_directories.add(item_str)
                            else:
                                extracted_files.add(item_str)
                                
                    except (ValueError, SyntaxError) as e:
                        logger.warning(f"Could not parse file list `files=[{match}]`. Error: {e}. Falling back to simple split.")
                        # Fallback to simple comma splitting if ast.literal_eval fails
                        file_items = [f.strip('\'"` ') for f in match.split(',')]
                        for item in file_items:
                            if item:
                                if item.endswith('/'):
                                    extracted_directories.add(item)
                                else:
                                    extracted_files.add(item)
                else:
                    # Regular pattern matching
                    match = match.strip('\'"` ')
                    if match:
                        if match.endswith('/'):
                            extracted_directories.add(match)
                        elif '.' in match or match.endswith('.py'):
                            extracted_files.add(match)
        
        # Try to extract tool name from response
        for keyword, mapped_tool_name in self.tool_name_mappings.items():
            if keyword in response.lower():
                tool_name = mapped_tool_name
                confidence = 0.7  # Slightly higher confidence
                break
        
        # Build suggested actions for low confidence results
        suggested_actions = []
        if confidence < 0.5:
            suggested_actions.extend([
                "Please clarify your intent",
                "Specify which files to analyze",
                "Choose from available tools: config_validator, dependency_mapper, test_coverage_analyzer"
            ])
        
        return IntentResult(
            action=self._string_to_intent_action(primary_action),
            confidence=confidence,
            tool_name=tool_name,
            files=list(extracted_files),  # Convert set back to list
            directories=list(extracted_directories),  # Convert set back to list
            parsing_method="fallback_regex",
            raw_user_input=response,
            clarification_needed=confidence < 0.5,
            suggested_actions=suggested_actions,
            extracted_entities={
                'fallback_reason': error or 'AI parsing not available',
                'extraction_method': 'regex_patterns'
            }
        )
    
    def get_supported_actions(self) -> List[str]:
        """Get list of all supported actions"""
        return [
            'run_tool',
            'explain', 
            'synthesize',
            'end_session',
            'retry_failed',
            'continue',
            'help',
            'specify_files',
            'unknown'
        ]
    
    def get_tool_mappings(self) -> Dict[str, str]:
        """Get current tool name mappings"""
        return self.tool_name_mappings.copy()
    
    def _string_to_intent_action(self, action_str: str) -> IntentAction:
        """Convert string action to IntentAction enum"""
        action_mapping = {
            'run_tool': IntentAction.RUN_TOOL,
            'synthesize': IntentAction.SYNTHESIZE,
            'retry_failed': IntentAction.RETRY_FAILED,
            'specify_files': IntentAction.SPECIFY_FILES,
            'explain': IntentAction.EXPLAIN,
            'help': IntentAction.HELP,
            'end_session': IntentAction.END_SESSION,
            'continue': IntentAction.CONTINUE,
            'continue_dialogue': IntentAction.CONTINUE_DIALOGUE,
            'unknown': IntentAction.UNKNOWN
        }
        return action_mapping.get(action_str, IntentAction.UNKNOWN)