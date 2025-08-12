"""
Intent analysis for smart tool routing
"""
import re
from typing import Dict, List, Tuple
from enum import Enum


class ToolIntent(Enum):
    UNDERSTAND = "understand"
    INVESTIGATE = "investigate" 
    VALIDATE = "validate"
    COLLABORATE = "collaborate"
    COMPREHENSIVE = "full_analysis"


class IntentAnalyzer:
    """Analyzes user intent to route to appropriate smart tool"""
    
    # Intent patterns for routing decisions
    INTENT_PATTERNS = {
        ToolIntent.UNDERSTAND: [
            r'\b(understand|comprehend|learn|explain|overview|architecture|structure|how does|what is)\b',
            r'\b(analyze code|code analysis|codebase|system design)\b',
            r'\b(documentation|docs|readme)\b'
        ],
        ToolIntent.INVESTIGATE: [
            r'\b(debug|problem|issue|error|bug|trace|find|search|investigate)\b',
            r'\b(why|root cause|troubleshoot|diagnose)\b',
            r'\b(performance|slow|bottleneck|memory|cpu)\b',
            r'\b(logs|logging|crash|failure)\b'
        ],
        ToolIntent.VALIDATE: [
            r'\b(security|vulnerability|secure|audit|validate|check|verify)\b',
            r'\b(quality|standards|best practices|consistency)\b',
            r'\b(config|configuration|settings|environment)\b',
            r'\b(test coverage|testing|tests)\b'
        ],
        ToolIntent.COLLABORATE: [
            r'\b(review|feedback|discuss|dialogue|opinion|suggestion)\b',
            r'\b(what do you think|recommendations|advice)\b',
            r'\b(plan|strategy|approach|design)\b'
        ],
        ToolIntent.COMPREHENSIVE: [
            r'\b(comprehensive|complete|full analysis|everything|all aspects)\b',
            r'\b(multi-tool|orchestrate|coordinate|multiple)\b',
            r'\b(end-to-end|thorough|detailed analysis)\b'
        ]
    }
    
    @classmethod
    def analyze_intent(cls, user_input: str, context: Dict = None) -> Tuple[ToolIntent, float]:
        """
        Analyze user intent from input text
        Returns (intent, confidence_score)
        """
        if not user_input:
            return ToolIntent.UNDERSTAND, 0.0
        
        user_input_lower = user_input.lower()
        intent_scores = {}
        
        # Score each intent based on pattern matches
        for intent, patterns in cls.INTENT_PATTERNS.items():
            score = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, user_input_lower, re.IGNORECASE))
                score += matches * 0.3  # Each match adds 0.3 to score
            
            intent_scores[intent] = score
        
        # Context-based adjustments
        if context:
            cls._apply_context_adjustments(intent_scores, context)
        
        # Find best intent
        if not intent_scores or max(intent_scores.values()) == 0:
            return ToolIntent.UNDERSTAND, 0.0
        
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        confidence = min(intent_scores[best_intent], 1.0)  # Cap at 1.0
        
        return best_intent, confidence
    
    @classmethod
    def _apply_context_adjustments(cls, scores: Dict[ToolIntent, float], context: Dict):
        """Apply context-based score adjustments"""
        
        # If files mentioned, boost appropriate intents
        if context.get('files'):
            file_paths = context['files']
            
            # Config files → validate
            if any('config' in f.lower() or f.endswith(('.env', '.yaml', '.json', '.toml')) 
                   for f in file_paths):
                scores[ToolIntent.VALIDATE] += 0.2
            
            # Log files → investigate  
            if any('log' in f.lower() or f.endswith('.log') for f in file_paths):
                scores[ToolIntent.INVESTIGATE] += 0.2
            
            # Test files → validate
            if any('test' in f.lower() or f.endswith('_test.py') for f in file_paths):
                scores[ToolIntent.VALIDATE] += 0.2
            
            # Documentation → understand
            if any(f.lower().endswith(('.md', '.rst', '.txt')) for f in file_paths):
                scores[ToolIntent.UNDERSTAND] += 0.2
        
        # Focus parameter adjustments
        if context.get('focus'):
            focus = context['focus'].lower()
            if 'security' in focus:
                scores[ToolIntent.VALIDATE] += 0.3
            elif 'performance' in focus:
                scores[ToolIntent.INVESTIGATE] += 0.3  
            elif 'architecture' in focus:
                scores[ToolIntent.UNDERSTAND] += 0.3
    
    @classmethod
    def get_engine_recommendations(cls, intent: ToolIntent, context: Dict = None) -> List[str]:
        """Get recommended engines for an intent"""
        
        recommendations = {
            ToolIntent.UNDERSTAND: ['analyze_code', 'search_code', 'analyze_docs'],
            ToolIntent.INVESTIGATE: ['search_code', 'check_quality', 'analyze_logs', 'performance_profiler'],  
            ToolIntent.VALIDATE: ['check_quality', 'config_validator', 'interface_inconsistency_detector'],
            ToolIntent.COLLABORATE: ['review_output'],
            ToolIntent.COMPREHENSIVE: ['analyze_code', 'check_quality', 'config_validator']
        }
        
        base_engines = recommendations.get(intent, ['analyze_code'])
        
        # Context-based engine additions
        if context:
            if context.get('files'):
                file_paths = context['files']
                
                # Add specific engines based on file types
                if any('log' in f.lower() for f in file_paths):
                    base_engines.append('analyze_logs')
                if any(f.endswith(('.sql', '.db')) for f in file_paths):
                    base_engines.append('analyze_database')
                if any('test' in f.lower() for f in file_paths):
                    base_engines.append('analyze_test_coverage')
        
        return list(set(base_engines))  # Remove duplicates