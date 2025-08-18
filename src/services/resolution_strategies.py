"""
Resolution Strategies for Conflict Resolution
Provides different strategies for resolving conflicts between engine results
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ResolutionConfidence(Enum):
    """Confidence levels for resolutions"""
    HIGH = "high"          # > 0.8
    MEDIUM = "medium"      # 0.5 - 0.8
    LOW = "low"           # < 0.5


@dataclass
class ResolutionContext:
    """Context for resolution decision making"""
    conflict_type: str
    engines_involved: List[str]
    conflicting_values: Dict[str, Any]
    engine_metadata: Dict[str, Dict[str, Any]]  # Metadata about each engine
    correlation_data: Optional[Dict[str, Any]] = None
    
    
@dataclass
class ResolutionResult:
    """Result of applying a resolution strategy"""
    resolved_value: Any
    strategy_name: str
    confidence: float
    explanation: str
    supporting_engines: List[str]
    dissenting_engines: List[str]


class ResolutionStrategy(ABC):
    """Abstract base class for resolution strategies"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        
    @abstractmethod
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if this strategy can resolve the given conflict"""
        pass
    
    @abstractmethod
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Apply the resolution strategy"""
        pass
    
    def get_confidence_level(self, confidence: float) -> ResolutionConfidence:
        """Convert numerical confidence to enum"""
        if confidence > 0.8:
            return ResolutionConfidence.HIGH
        elif confidence > 0.5:
            return ResolutionConfidence.MEDIUM
        else:
            return ResolutionConfidence.LOW


class ConsensusStrategy(ResolutionStrategy):
    """
    Resolution by consensus - uses majority agreement
    Works best when multiple engines provide similar results
    """
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Can resolve if there are 3+ engines and clear majority"""
        return len(context.engines_involved) >= 3
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Find the most common value among engines"""
        values = context.conflicting_values
        
        # Group engines by similar values
        value_groups = self._group_similar_values(values)
        
        # Find the largest group
        largest_group = max(value_groups, key=lambda g: len(g['engines']))
        
        # Calculate confidence based on majority size
        confidence = len(largest_group['engines']) / len(context.engines_involved)
        
        return ResolutionResult(
            resolved_value=largest_group['value'],
            strategy_name="ConsensusStrategy",
            confidence=confidence,
            explanation=f"Consensus from {len(largest_group['engines'])} out of "
                       f"{len(context.engines_involved)} engines",
            supporting_engines=largest_group['engines'],
            dissenting_engines=[e for e in context.engines_involved 
                              if e not in largest_group['engines']]
        )
    
    def _group_similar_values(self, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Group engines with similar values"""
        groups = []
        processed = set()
        
        for engine, value in values.items():
            if engine in processed:
                continue
            
            # Create new group
            group = {'value': value, 'engines': [engine]}
            processed.add(engine)
            
            # Find similar values
            for other_engine, other_value in values.items():
                if other_engine not in processed:
                    if self._are_values_similar(value, other_value):
                        group['engines'].append(other_engine)
                        processed.add(other_engine)
            
            groups.append(group)
        
        return groups
    
    def _are_values_similar(self, val1: Any, val2: Any) -> bool:
        """Check if two values are similar enough to group"""
        if type(val1) != type(val2):
            return False
        
        if isinstance(val1, (int, float)):
            # Numerical values within 10%
            if val1 == 0 and val2 == 0:
                return True
            if val1 == 0 or val2 == 0:
                return False
            return abs(val1 - val2) / max(abs(val1), abs(val2)) < 0.1
        
        if isinstance(val1, str):
            # String similarity
            return val1.lower().strip() == val2.lower().strip()
        
        # Default comparison
        return val1 == val2


class ExpertWeightingStrategy(ResolutionStrategy):
    """
    Resolution by expertise - weights engines by their domain expertise
    Works best when engines have known specializations
    """
    
    def __init__(self):
        super().__init__()
        
        # Define engine expertise scores for different domains
        self.expertise_matrix = {
            'check_quality': {
                'security': 0.95,
                'performance': 0.85,
                'quality': 0.90,
                'testing': 0.70,
                'architecture': 0.60
            },
            'analyze_code': {
                'architecture': 0.95,
                'quality': 0.80,
                'dependencies': 0.85,
                'security': 0.60,
                'performance': 0.50
            },
            'performance_profiler': {
                'performance': 1.0,
                'optimization': 0.95,
                'bottlenecks': 0.90,
                'quality': 0.40,
                'security': 0.30
            },
            'analyze_test_coverage': {
                'testing': 1.0,
                'quality': 0.85,
                'coverage': 0.95,
                'architecture': 0.40,
                'security': 0.50
            },
            'config_validator': {
                'configuration': 0.95,
                'security': 0.85,
                'deployment': 0.80,
                'quality': 0.60,
                'performance': 0.50
            },
            'analyze_database': {
                'database': 0.95,
                'schema': 0.90,
                'optimization': 0.85,
                'architecture': 0.70,
                'security': 0.60
            },
            'api_contract_checker': {
                'api': 0.95,
                'contracts': 0.90,
                'integration': 0.85,
                'architecture': 0.70,
                'quality': 0.65
            },
            'map_dependencies': {
                'dependencies': 0.95,
                'architecture': 0.85,
                'coupling': 0.90,
                'quality': 0.70,
                'security': 0.50
            },
            'interface_inconsistency_detector': {
                'consistency': 0.95,
                'interfaces': 0.90,
                'quality': 0.85,
                'architecture': 0.75,
                'testing': 0.60
            }
        }
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Can resolve if we have expertise data for the engines"""
        return any(engine in self.expertise_matrix 
                  for engine in context.engines_involved)
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Resolve by weighting engines based on their expertise"""
        # Determine the domain from context
        domain = self._determine_domain(context)
        
        # Calculate weighted scores for each engine
        weighted_results = {}
        total_weight = 0
        
        for engine, value in context.conflicting_values.items():
            weight = self._get_engine_weight(engine, domain)
            weighted_results[engine] = {
                'value': value,
                'weight': weight
            }
            total_weight += weight
        
        # Find the highest weighted result
        best_engine = max(weighted_results.keys(), 
                         key=lambda e: weighted_results[e]['weight'])
        
        confidence = weighted_results[best_engine]['weight'] / total_weight if total_weight > 0 else 0.5
        
        return ResolutionResult(
            resolved_value=weighted_results[best_engine]['value'],
            strategy_name="ExpertWeightingStrategy",
            confidence=confidence,
            explanation=f"Selected {best_engine} based on {domain} expertise "
                       f"(weight: {weighted_results[best_engine]['weight']:.2f})",
            supporting_engines=[best_engine],
            dissenting_engines=[e for e in context.engines_involved if e != best_engine]
        )
    
    def _determine_domain(self, context: ResolutionContext) -> str:
        """Determine the domain based on context"""
        conflict_type = context.conflict_type.lower()
        
        # Map conflict types to domains
        if 'security' in conflict_type or 'vulnerabil' in conflict_type:
            return 'security'
        elif 'performance' in conflict_type or 'speed' in conflict_type:
            return 'performance'
        elif 'test' in conflict_type or 'coverage' in conflict_type:
            return 'testing'
        elif 'architect' in conflict_type or 'structure' in conflict_type:
            return 'architecture'
        elif 'quality' in conflict_type or 'maintain' in conflict_type:
            return 'quality'
        elif 'database' in conflict_type or 'schema' in conflict_type:
            return 'database'
        elif 'api' in conflict_type or 'contract' in conflict_type:
            return 'api'
        elif 'depend' in conflict_type:
            return 'dependencies'
        else:
            return 'quality'  # Default domain
    
    def _get_engine_weight(self, engine: str, domain: str) -> float:
        """Get the expertise weight for an engine in a domain"""
        if engine in self.expertise_matrix:
            return self.expertise_matrix[engine].get(domain, 0.5)
        return 0.5  # Default weight for unknown engines


class ConfidenceBasedStrategy(ResolutionStrategy):
    """
    Resolution by confidence - prefers results with higher confidence scores
    Works when engines provide confidence metrics with their results
    """
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Can resolve if engine metadata contains confidence scores"""
        return (context.engine_metadata and 
                any('confidence' in meta or 'score' in meta 
                    for meta in context.engine_metadata.values()))
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Select result with highest confidence score"""
        engine_scores = {}
        
        for engine in context.engines_involved:
            metadata = context.engine_metadata.get(engine, {})
            
            # Extract confidence score from metadata
            score = metadata.get('confidence', 
                                metadata.get('score', 
                                           metadata.get('accuracy', 0.5)))
            
            # Adjust score based on result characteristics
            if engine in context.conflicting_values:
                value = context.conflicting_values[engine]
                score = self._adjust_confidence(score, value)
            
            engine_scores[engine] = score
        
        # Select engine with highest score
        best_engine = max(engine_scores.keys(), key=lambda e: engine_scores[e])
        best_score = engine_scores[best_engine]
        
        return ResolutionResult(
            resolved_value=context.conflicting_values[best_engine],
            strategy_name="ConfidenceBasedStrategy",
            confidence=best_score,
            explanation=f"Selected {best_engine} with highest confidence score: {best_score:.2f}",
            supporting_engines=[best_engine],
            dissenting_engines=[e for e in context.engines_involved if e != best_engine]
        )
    
    def _adjust_confidence(self, base_score: float, value: Any) -> float:
        """Adjust confidence based on value characteristics"""
        adjusted = base_score
        
        # Boost confidence for detailed results
        if isinstance(value, str) and len(value) > 500:
            adjusted *= 1.1
        
        # Boost confidence for structured results
        if isinstance(value, dict) and len(value) > 3:
            adjusted *= 1.05
        
        # Reduce confidence for empty or minimal results
        if not value or (isinstance(value, str) and len(value) < 50):
            adjusted *= 0.8
        
        return min(1.0, adjusted)


class HierarchicalStrategy(ResolutionStrategy):
    """
    Resolution by hierarchy - uses predefined engine priority
    Works when there's a clear hierarchy of trust among engines
    """
    
    def __init__(self):
        super().__init__()
        
        # Define engine hierarchy (higher index = higher priority)
        self.engine_hierarchy = [
            'review_output',           # Highest priority - AI review
            'full_analysis',          # Comprehensive analysis
            'check_quality',          # Quality checks
            'analyze_code',           # Code analysis
            'validate',               # Validation
            'analyze_test_coverage',  # Test coverage
            'performance_profiler',   # Performance
            'config_validator',       # Configuration
            'analyze_database',       # Database
            'api_contract_checker',   # API contracts
            'map_dependencies',       # Dependencies
            'interface_inconsistency_detector',  # Consistency
            'analyze_logs',          # Logs
            'search_code'            # Search
        ]
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Can resolve if any engine is in the hierarchy"""
        return any(engine in self.engine_hierarchy 
                  for engine in context.engines_involved)
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Select result from highest priority engine"""
        # Find engines in hierarchy
        engines_with_priority = []
        
        for engine in context.engines_involved:
            if engine in self.engine_hierarchy:
                priority = self.engine_hierarchy.index(engine)
                engines_with_priority.append((engine, priority))
        
        if not engines_with_priority:
            # Fallback if no engines in hierarchy
            best_engine = context.engines_involved[0]
            confidence = 0.3
        else:
            # Select highest priority engine
            engines_with_priority.sort(key=lambda x: x[1], reverse=True)
            best_engine = engines_with_priority[0][0]
            
            # Confidence based on relative priority
            max_priority = engines_with_priority[0][1]
            confidence = 0.5 + (max_priority / len(self.engine_hierarchy)) * 0.5
        
        return ResolutionResult(
            resolved_value=context.conflicting_values[best_engine],
            strategy_name="HierarchicalStrategy",
            confidence=confidence,
            explanation=f"Selected {best_engine} based on engine hierarchy",
            supporting_engines=[best_engine],
            dissenting_engines=[e for e in context.engines_involved if e != best_engine]
        )


class ManualReviewStrategy(ResolutionStrategy):
    """
    Flag conflicts for manual review when automatic resolution isn't confident
    Always available as a fallback strategy
    """
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Always available as fallback"""
        return True
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Create a comprehensive report for manual review"""
        # Prepare all conflicting values for review
        review_data = {
            'conflict_type': context.conflict_type,
            'engines_involved': context.engines_involved,
            'conflicting_values': context.conflicting_values,
            'recommendation': 'Manual review required - automatic resolution confidence too low'
        }
        
        # Add any correlation data if available
        if context.correlation_data:
            review_data['correlations'] = context.correlation_data
        
        return ResolutionResult(
            resolved_value=review_data,
            strategy_name="ManualReviewStrategy",
            confidence=0.0,  # Indicates manual review needed
            explanation="Flagged for manual review due to complex conflict",
            supporting_engines=[],
            dissenting_engines=context.engines_involved
        )


class CompositeStrategy(ResolutionStrategy):
    """
    Combines multiple strategies for more robust resolution
    Tries strategies in order and combines their results
    """
    
    def __init__(self):
        super().__init__()
        
        # Initialize component strategies
        self.strategies = [
            ExpertWeightingStrategy(),
            ConsensusStrategy(),
            ConfidenceBasedStrategy(),
            HierarchicalStrategy()
        ]
        
        # Fallback strategy
        self.fallback = ManualReviewStrategy()
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Can resolve if any component strategy can"""
        return any(strategy.can_resolve(context) for strategy in self.strategies)
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Try multiple strategies and combine results"""
        results = []
        weights = []
        
        # Try each strategy
        for strategy in self.strategies:
            if strategy.can_resolve(context):
                try:
                    result = strategy.resolve(context)
                    results.append(result)
                    weights.append(result.confidence)
                except Exception as e:
                    logger.warning(f"Strategy {strategy.name} failed: {e}")
        
        if not results:
            # Use fallback if no strategies worked
            return self.fallback.resolve(context)
        
        # If single result, return it
        if len(results) == 1:
            return results[0]
        
        # Combine multiple results
        return self._combine_results(results, weights, context)
    
    def _combine_results(self, results: List[ResolutionResult], 
                        weights: List[float], 
                        context: ResolutionContext) -> ResolutionResult:
        """Combine multiple resolution results"""
        # Find the result with highest confidence
        best_idx = weights.index(max(weights))
        best_result = results[best_idx]
        
        # Calculate combined confidence
        avg_confidence = sum(weights) / len(weights)
        agreement_factor = self._calculate_agreement(results)
        combined_confidence = (best_result.confidence * 0.6 + 
                              avg_confidence * 0.2 + 
                              agreement_factor * 0.2)
        
        # Determine supporting engines across all strategies
        all_supporting = set()
        for result in results:
            all_supporting.update(result.supporting_engines)
        
        return ResolutionResult(
            resolved_value=best_result.resolved_value,
            strategy_name="CompositeStrategy",
            confidence=combined_confidence,
            explanation=f"Combined {len(results)} strategies; "
                       f"primary: {best_result.strategy_name}",
            supporting_engines=list(all_supporting),
            dissenting_engines=[e for e in context.engines_involved 
                              if e not in all_supporting]
        )
    
    def _calculate_agreement(self, results: List[ResolutionResult]) -> float:
        """Calculate agreement factor among results"""
        if len(results) < 2:
            return 1.0
        
        # Check how many results agree on the same value
        values = [str(r.resolved_value) for r in results]
        unique_values = set(values)
        
        if len(unique_values) == 1:
            return 1.0  # Perfect agreement
        
        # Calculate agreement as inverse of diversity
        agreement = 1.0 - (len(unique_values) - 1) / len(results)
        return max(0.0, agreement)


class StrategySelector:
    """
    Selects the best resolution strategy for a given conflict
    """
    
    def __init__(self):
        self.strategies = {
            'consensus': ConsensusStrategy(),
            'expert': ExpertWeightingStrategy(),
            'confidence': ConfidenceBasedStrategy(),
            'hierarchy': HierarchicalStrategy(),
            'composite': CompositeStrategy(),
            'manual': ManualReviewStrategy()
        }
        
        # Strategy selection rules
        self.selection_rules = {
            'metric_discrepancy': ['consensus', 'expert', 'confidence'],
            'contradictory_results': ['expert', 'confidence', 'hierarchy'],
            'recommendation_conflict': ['expert', 'hierarchy', 'consensus'],
            'default': ['composite', 'manual']
        }
    
    def select_strategy(self, context: ResolutionContext) -> ResolutionStrategy:
        """Select the best strategy for the given context"""
        # Get preferred strategies for conflict type
        preferred = self.selection_rules.get(context.conflict_type, 
                                            self.selection_rules['default'])
        
        # Try preferred strategies in order
        for strategy_name in preferred:
            strategy = self.strategies[strategy_name]
            if strategy.can_resolve(context):
                logger.info(f"Selected {strategy_name} strategy for {context.conflict_type}")
                return strategy
        
        # Fallback to manual review
        logger.warning(f"No suitable strategy found, using manual review")
        return self.strategies['manual']
    
    def resolve_with_best_strategy(self, context: ResolutionContext) -> ResolutionResult:
        """Resolve using the best available strategy"""
        strategy = self.select_strategy(context)
        return strategy.resolve(context)