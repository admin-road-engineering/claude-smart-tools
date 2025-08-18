"""
Cross-Engine Correlation and Conflict Resolution Framework
Detects correlations between engine results and resolves conflicts
"""
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class CorrelationType(Enum):
    """Types of correlations between engine results"""
    CONFIRMS = "confirms"           # Results confirm each other
    COMPLEMENTS = "complements"     # Results add to each other
    CONTRADICTS = "contradicts"     # Results contradict each other
    OVERLAPS = "overlaps"          # Results partially overlap
    INDEPENDENT = "independent"     # Results are unrelated


class CorrelationStrength(Enum):
    """Strength of correlation between results"""
    STRONG = "strong"       # > 0.8 similarity
    MODERATE = "moderate"   # 0.5 - 0.8 similarity
    WEAK = "weak"          # 0.3 - 0.5 similarity
    NONE = "none"          # < 0.3 similarity


class ConflictSeverity(Enum):
    """Severity levels for conflicts"""
    CRITICAL = "critical"   # Must be resolved
    MODERATE = "moderate"   # Should be resolved
    MINOR = "minor"        # Optional to resolve


@dataclass
class Correlation:
    """Represents a correlation between two engine results"""
    source1_engine: str
    source2_engine: str
    correlation_type: CorrelationType
    strength: CorrelationStrength
    confidence: float
    description: str
    evidence: List[str]
    
    def __str__(self) -> str:
        return (f"{self.source1_engine} {self.correlation_type.value} "
                f"{self.source2_engine} ({self.strength.value}, "
                f"confidence: {self.confidence:.2f})")


@dataclass
class Conflict:
    """Represents a conflict between engine results"""
    engines: List[str]
    conflict_type: str
    severity: ConflictSeverity
    description: str
    conflicting_findings: Dict[str, Any]
    suggested_resolution: Optional[str] = None
    
    def __str__(self) -> str:
        return (f"Conflict ({self.severity.value}): {self.conflict_type} "
                f"between {', '.join(self.engines)}")


@dataclass
class Resolution:
    """Represents a resolution for a conflict"""
    conflict: Conflict
    strategy_used: str
    resolved_value: Any
    explanation: str
    confidence: float
    
    def __str__(self) -> str:
        return (f"Resolved using {self.strategy_used}: {self.resolved_value} "
                f"(confidence: {self.confidence:.2f})")


class CorrelationFramework:
    """
    Main framework for detecting correlations and resolving conflicts
    between multiple engine results
    """
    
    def __init__(self, use_cache: bool = True):
        self.correlations: List[Correlation] = []
        self.conflicts: List[Conflict] = []
        self.resolutions: List[Resolution] = []
        
        # Correlation detection thresholds
        self.similarity_threshold = 0.3
        self.strong_correlation_threshold = 0.8
        self.moderate_correlation_threshold = 0.5
        
        # Initialize cache if enabled
        self.use_cache = use_cache
        self._cache = None
        if use_cache:
            try:
                from .correlation_cache import get_correlation_cache
                self._cache = get_correlation_cache()
                logger.info("Correlation caching enabled")
            except ImportError:
                logger.warning("Correlation cache not available, proceeding without cache")
                self.use_cache = False
        
        # Pattern matching for common findings
        self.security_patterns = [
            r'vulnerability|exploit|injection|xss|csrf|security',
            r'authentication|authorization|token|password|secret',
            r'encryption|crypto|ssl|tls|certificate'
        ]
        
        self.performance_patterns = [
            r'slow|latency|bottleneck|performance|speed',
            r'memory|cpu|resource|leak|consumption',
            r'optimization|cache|index|query'
        ]
        
        self.quality_patterns = [
            r'bug|error|issue|problem|defect',
            r'quality|maintainability|readability|complexity',
            r'test|coverage|assertion|mock'
        ]
        
        logger.info("Correlation Framework initialized")
    
    def analyze(self, engine_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for correlation analysis
        
        Args:
            engine_results: Dictionary of engine names to their results
            
        Returns:
            Analysis results including correlations, conflicts, and resolutions
        """
        # Check cache first if enabled
        if self.use_cache and self._cache:
            cached_result = self._cache.get(engine_results)
            if cached_result:
                logger.info("Using cached correlation results")
                return cached_result
        
        # Reset for new analysis
        self.correlations = []
        self.conflicts = []
        self.resolutions = []
        
        # Extract patterns from results
        patterns = self._extract_patterns(engine_results)
        
        # Detect correlations
        self.correlations = self._detect_correlations(patterns)
        
        # Identify conflicts
        self.conflicts = self._identify_conflicts(patterns, self.correlations)
        
        # Resolve conflicts
        for conflict in self.conflicts:
            resolution = self._resolve_conflict(conflict, engine_results)
            if resolution:
                self.resolutions.append(resolution)
        
        result = {
            'correlations': self.correlations,
            'conflicts': self.conflicts,
            'resolutions': self.resolutions,
            'summary': self._generate_summary()
        }
        
        # Cache the result if caching is enabled
        if self.use_cache and self._cache:
            self._cache.put(engine_results, result)
        
        return result
    
    def _extract_patterns(self, engine_results: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Extract standardized patterns from engine results
        """
        patterns = {}
        
        for engine_name, result in engine_results.items():
            patterns[engine_name] = {
                'raw_result': result,
                'text_content': self._extract_text(result),
                'metrics': self._extract_metrics(result),
                'findings': self._extract_findings(result),
                'recommendations': self._extract_recommendations(result),
                'categories': self._categorize_content(result)
            }
        
        return patterns
    
    def _extract_text(self, result: Any) -> str:
        """Extract text content from result"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            # Recursively extract text from dict
            texts = []
            for value in result.values():
                extracted = self._extract_text(value)
                if extracted:
                    texts.append(extracted)
            return ' '.join(texts)
        elif isinstance(result, list):
            # Extract text from list items
            texts = []
            for item in result:
                extracted = self._extract_text(item)
                if extracted:
                    texts.append(extracted)
            return ' '.join(texts)
        else:
            return str(result)
    
    def _extract_metrics(self, result: Any) -> Dict[str, float]:
        """Extract numerical metrics from result"""
        metrics = {}
        text = self._extract_text(result)
        
        # Look for common metric patterns
        patterns = {
            'coverage': r'coverage[:\s]+(\d+(?:\.\d+)?)\s*%',
            'performance': r'(\d+(?:\.\d+)?)\s*ms',
            'memory': r'(\d+(?:\.\d+)?)\s*[MG]B',
            'cpu': r'cpu[:\s]+(\d+(?:\.\d+)?)\s*%',
            'errors': r'(\d+)\s+errors?',
            'warnings': r'(\d+)\s+warnings?'
        }
        
        for metric_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    metrics[metric_name] = float(match.group(1))
                except ValueError:
                    pass
        
        return metrics
    
    def _extract_findings(self, result: Any) -> List[str]:
        """Extract specific findings or issues from result"""
        findings = []
        text = self._extract_text(result).lower()
        
        # Look for issue indicators
        issue_patterns = [
            r'found\s+(\d+)\s+issues?',
            r'detected\s+(\d+)\s+problems?',
            r'(\d+)\s+vulnerabilit(?:y|ies)',
            r'(\d+)\s+errors?\s+found'
        ]
        
        for pattern in issue_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                findings.append(match.group(0))
        
        # Extract bullet points or numbered lists
        bullet_pattern = r'[•\-\*]\s+(.+?)(?:\n|$)'
        matches = re.finditer(bullet_pattern, text)
        for match in matches:
            finding = match.group(1).strip()
            if len(finding) > 10:  # Filter out very short items
                findings.append(finding)
        
        return findings
    
    def _extract_recommendations(self, result: Any) -> List[str]:
        """Extract recommendations from result"""
        recommendations = []
        text = self._extract_text(result).lower()
        
        # Look for recommendation indicators
        rec_patterns = [
            r'recommend(?:ation)?s?:?\s*(.+?)(?:\n\n|$)',
            r'suggest(?:ion)?s?:?\s*(.+?)(?:\n\n|$)',
            r'should\s+(.+?)(?:\.|$)',
            r'consider\s+(.+?)(?:\.|$)'
        ]
        
        for pattern in rec_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                rec = match.group(1).strip()
                if len(rec) > 15:  # Filter out very short recommendations
                    recommendations.append(rec)
        
        return recommendations
    
    def _categorize_content(self, result: Any) -> Set[str]:
        """Categorize content based on patterns"""
        categories = set()
        text = self._extract_text(result).lower()
        
        # Check security patterns
        for pattern in self.security_patterns:
            if re.search(pattern, text):
                categories.add('security')
                break
        
        # Check performance patterns
        for pattern in self.performance_patterns:
            if re.search(pattern, text):
                categories.add('performance')
                break
        
        # Check quality patterns
        for pattern in self.quality_patterns:
            if re.search(pattern, text):
                categories.add('quality')
                break
        
        # Check for architecture-related content
        if re.search(r'architecture|design|pattern|structure|component', text):
            categories.add('architecture')
        
        # Check for testing-related content
        if re.search(r'test|coverage|unit|integration|e2e', text):
            categories.add('testing')
        
        return categories
    
    def _detect_correlations(self, patterns: Dict[str, Dict[str, Any]]) -> List[Correlation]:
        """
        Detect correlations between engine results
        """
        correlations = []
        engine_names = list(patterns.keys())
        
        # Compare each pair of engines
        for i in range(len(engine_names)):
            for j in range(i + 1, len(engine_names)):
                engine1 = engine_names[i]
                engine2 = engine_names[j]
                
                # Calculate similarity
                similarity = self._calculate_similarity(
                    patterns[engine1], 
                    patterns[engine2]
                )
                
                if similarity > self.similarity_threshold:
                    # Determine correlation type and strength
                    corr_type = self._determine_correlation_type(
                        patterns[engine1], 
                        patterns[engine2]
                    )
                    
                    strength = self._determine_strength(similarity)
                    
                    # Create correlation
                    correlation = Correlation(
                        source1_engine=engine1,
                        source2_engine=engine2,
                        correlation_type=corr_type,
                        strength=strength,
                        confidence=similarity,
                        description=self._describe_correlation(
                            engine1, engine2, corr_type, patterns
                        ),
                        evidence=self._gather_evidence(
                            patterns[engine1], 
                            patterns[engine2]
                        )
                    )
                    
                    correlations.append(correlation)
        
        return correlations
    
    def _calculate_similarity(self, pattern1: Dict[str, Any], 
                            pattern2: Dict[str, Any]) -> float:
        """
        Calculate similarity between two patterns
        """
        similarities = []
        
        # Text similarity
        text1 = pattern1.get('text_content', '')
        text2 = pattern2.get('text_content', '')
        if text1 and text2:
            text_sim = SequenceMatcher(None, text1[:500], text2[:500]).ratio()
            similarities.append(text_sim)
        
        # Category overlap
        cat1 = pattern1.get('categories', set())
        cat2 = pattern2.get('categories', set())
        if cat1 and cat2:
            cat_sim = len(cat1 & cat2) / len(cat1 | cat2) if (cat1 | cat2) else 0
            similarities.append(cat_sim)
        
        # Metric correlation
        metrics1 = pattern1.get('metrics', {})
        metrics2 = pattern2.get('metrics', {})
        common_metrics = set(metrics1.keys()) & set(metrics2.keys())
        if common_metrics:
            metric_sims = []
            for metric in common_metrics:
                val1 = metrics1[metric]
                val2 = metrics2[metric]
                if val1 > 0 or val2 > 0:
                    metric_sim = 1 - abs(val1 - val2) / max(val1, val2)
                    metric_sims.append(metric_sim)
            if metric_sims:
                similarities.append(sum(metric_sims) / len(metric_sims))
        
        # Finding overlap
        findings1 = set(pattern1.get('findings', []))
        findings2 = set(pattern2.get('findings', []))
        if findings1 and findings2:
            finding_sim = len(findings1 & findings2) / len(findings1 | findings2)
            similarities.append(finding_sim)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _determine_correlation_type(self, pattern1: Dict[str, Any], 
                                   pattern2: Dict[str, Any]) -> CorrelationType:
        """
        Determine the type of correlation between patterns
        """
        # Check for contradictions
        if self._has_contradiction(pattern1, pattern2):
            return CorrelationType.CONTRADICTS
        
        # Check for confirmation
        if self._has_confirmation(pattern1, pattern2):
            return CorrelationType.CONFIRMS
        
        # Check for overlap
        findings1 = set(pattern1.get('findings', []))
        findings2 = set(pattern2.get('findings', []))
        if findings1 and findings2:
            overlap = len(findings1 & findings2) / min(len(findings1), len(findings2))
            if overlap > 0.5:
                return CorrelationType.OVERLAPS
        
        # Check for complementary information
        cat1 = pattern1.get('categories', set())
        cat2 = pattern2.get('categories', set())
        if cat1 and cat2 and not (cat1 & cat2):
            return CorrelationType.INDEPENDENT
        
        return CorrelationType.COMPLEMENTS
    
    def _has_contradiction(self, pattern1: Dict[str, Any], 
                          pattern2: Dict[str, Any]) -> bool:
        """
        Check if patterns contradict each other
        """
        # Check for contradictory metrics
        metrics1 = pattern1.get('metrics', {})
        metrics2 = pattern2.get('metrics', {})
        
        for metric in set(metrics1.keys()) & set(metrics2.keys()):
            val1 = metrics1[metric]
            val2 = metrics2[metric]
            # If values differ by more than 50%, consider it a contradiction
            if val1 > 0 and val2 > 0:
                diff_ratio = abs(val1 - val2) / max(val1, val2)
                if diff_ratio > 0.5:
                    return True
        
        # Check for contradictory findings
        text1 = pattern1.get('text_content', '').lower()
        text2 = pattern2.get('text_content', '').lower()
        
        contradiction_pairs = [
            ('no issues', 'issues found'),
            ('secure', 'vulnerable'),
            ('fast', 'slow'),
            ('good coverage', 'poor coverage'),
            ('no errors', 'errors detected')
        ]
        
        for pos, neg in contradiction_pairs:
            if (pos in text1 and neg in text2) or (neg in text1 and pos in text2):
                return True
        
        return False
    
    def _has_confirmation(self, pattern1: Dict[str, Any], 
                         pattern2: Dict[str, Any]) -> bool:
        """
        Check if patterns confirm each other
        """
        # Similar findings indicate confirmation
        findings1 = set(pattern1.get('findings', []))
        findings2 = set(pattern2.get('findings', []))
        
        if findings1 and findings2:
            overlap = len(findings1 & findings2) / min(len(findings1), len(findings2))
            if overlap > 0.7:
                return True
        
        # Similar metrics indicate confirmation
        metrics1 = pattern1.get('metrics', {})
        metrics2 = pattern2.get('metrics', {})
        
        common_metrics = set(metrics1.keys()) & set(metrics2.keys())
        if len(common_metrics) >= 2:
            similar_count = 0
            for metric in common_metrics:
                val1 = metrics1[metric]
                val2 = metrics2[metric]
                if val1 > 0 and val2 > 0:
                    diff_ratio = abs(val1 - val2) / max(val1, val2)
                    if diff_ratio < 0.2:  # Within 20% of each other
                        similar_count += 1
            
            if similar_count >= len(common_metrics) * 0.7:
                return True
        
        return False
    
    def _determine_strength(self, similarity: float) -> CorrelationStrength:
        """
        Determine correlation strength based on similarity score
        """
        if similarity > self.strong_correlation_threshold:
            return CorrelationStrength.STRONG
        elif similarity > self.moderate_correlation_threshold:
            return CorrelationStrength.MODERATE
        elif similarity > self.similarity_threshold:
            return CorrelationStrength.WEAK
        else:
            return CorrelationStrength.NONE
    
    def _describe_correlation(self, engine1: str, engine2: str, 
                            corr_type: CorrelationType, 
                            patterns: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate human-readable description of correlation
        """
        if corr_type == CorrelationType.CONFIRMS:
            return f"{engine1} and {engine2} confirm similar findings"
        elif corr_type == CorrelationType.CONTRADICTS:
            return f"{engine1} and {engine2} have contradictory results"
        elif corr_type == CorrelationType.OVERLAPS:
            return f"{engine1} and {engine2} have overlapping findings"
        elif corr_type == CorrelationType.COMPLEMENTS:
            return f"{engine1} and {engine2} provide complementary information"
        else:
            return f"{engine1} and {engine2} provide independent analyses"
    
    def _gather_evidence(self, pattern1: Dict[str, Any], 
                        pattern2: Dict[str, Any]) -> List[str]:
        """
        Gather evidence for the correlation
        """
        evidence = []
        
        # Common categories
        cat1 = pattern1.get('categories', set())
        cat2 = pattern2.get('categories', set())
        common_cats = cat1 & cat2
        if common_cats:
            evidence.append(f"Both analyze: {', '.join(common_cats)}")
        
        # Similar metrics
        metrics1 = pattern1.get('metrics', {})
        metrics2 = pattern2.get('metrics', {})
        for metric in set(metrics1.keys()) & set(metrics2.keys()):
            val1 = metrics1[metric]
            val2 = metrics2[metric]
            evidence.append(f"{metric}: {val1:.2f} vs {val2:.2f}")
        
        # Common findings (first 3)
        findings1 = set(pattern1.get('findings', []))
        findings2 = set(pattern2.get('findings', []))
        common_findings = list(findings1 & findings2)[:3]
        for finding in common_findings:
            evidence.append(f"Both found: {finding[:50]}...")
        
        return evidence
    
    def _identify_conflicts(self, patterns: Dict[str, Dict[str, Any]], 
                          correlations: List[Correlation]) -> List[Conflict]:
        """
        Identify conflicts from correlations and patterns
        """
        conflicts = []
        
        # Find contradictory correlations
        for correlation in correlations:
            if correlation.correlation_type == CorrelationType.CONTRADICTS:
                conflict = Conflict(
                    engines=[correlation.source1_engine, correlation.source2_engine],
                    conflict_type="contradictory_results",
                    severity=self._determine_conflict_severity(correlation),
                    description=f"Contradictory findings between {correlation.source1_engine} "
                              f"and {correlation.source2_engine}",
                    conflicting_findings={
                        correlation.source1_engine: patterns[correlation.source1_engine],
                        correlation.source2_engine: patterns[correlation.source2_engine]
                    }
                )
                conflicts.append(conflict)
        
        # Find metric discrepancies
        metric_conflicts = self._find_metric_conflicts(patterns)
        conflicts.extend(metric_conflicts)
        
        # Find recommendation conflicts
        rec_conflicts = self._find_recommendation_conflicts(patterns)
        conflicts.extend(rec_conflicts)
        
        return conflicts
    
    def _determine_conflict_severity(self, correlation: Correlation) -> ConflictSeverity:
        """
        Determine severity of a conflict
        """
        if correlation.strength == CorrelationStrength.STRONG:
            return ConflictSeverity.CRITICAL
        elif correlation.strength == CorrelationStrength.MODERATE:
            return ConflictSeverity.MODERATE
        else:
            return ConflictSeverity.MINOR
    
    def _find_metric_conflicts(self, patterns: Dict[str, Dict[str, Any]]) -> List[Conflict]:
        """
        Find conflicts in metrics between engines
        """
        conflicts = []
        
        # Collect all metrics across engines
        all_metrics = {}
        for engine, pattern in patterns.items():
            metrics = pattern.get('metrics', {})
            for metric_name, value in metrics.items():
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = {}
                all_metrics[metric_name][engine] = value
        
        # Check for discrepancies
        for metric_name, engine_values in all_metrics.items():
            if len(engine_values) > 1:
                values = list(engine_values.values())
                max_val = max(values)
                min_val = min(values)
                
                if max_val > 0 and (max_val - min_val) / max_val > 0.3:
                    conflict = Conflict(
                        engines=list(engine_values.keys()),
                        conflict_type="metric_discrepancy",
                        severity=ConflictSeverity.MODERATE,
                        description=f"Discrepancy in {metric_name} metric",
                        conflicting_findings=engine_values
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _find_recommendation_conflicts(self, patterns: Dict[str, Dict[str, Any]]) -> List[Conflict]:
        """
        Find conflicting recommendations between engines
        """
        conflicts = []
        
        # Collect recommendations
        engine_recs = {}
        for engine, pattern in patterns.items():
            recs = pattern.get('recommendations', [])
            if recs:
                engine_recs[engine] = recs
        
        # Check for contradictory recommendations
        if len(engine_recs) > 1:
            engines = list(engine_recs.keys())
            for i in range(len(engines)):
                for j in range(i + 1, len(engines)):
                    engine1 = engines[i]
                    engine2 = engines[j]
                    
                    # Simple contradiction detection
                    recs1_text = ' '.join(engine_recs[engine1]).lower()
                    recs2_text = ' '.join(engine_recs[engine2]).lower()
                    
                    if self._has_contradictory_recommendations(recs1_text, recs2_text):
                        conflict = Conflict(
                            engines=[engine1, engine2],
                            conflict_type="recommendation_conflict",
                            severity=ConflictSeverity.MODERATE,
                            description=f"Conflicting recommendations between {engine1} and {engine2}",
                            conflicting_findings={
                                engine1: engine_recs[engine1],
                                engine2: engine_recs[engine2]
                            }
                        )
                        conflicts.append(conflict)
        
        return conflicts
    
    def _has_contradictory_recommendations(self, recs1: str, recs2: str) -> bool:
        """
        Check if recommendations are contradictory
        """
        contradictions = [
            ('increase', 'decrease'),
            ('add', 'remove'),
            ('enable', 'disable'),
            ('optimize', 'simplify'),
            ('expand', 'reduce')
        ]
        
        for word1, word2 in contradictions:
            if (word1 in recs1 and word2 in recs2) or (word2 in recs1 and word1 in recs2):
                return True
        
        return False
    
    def _resolve_conflict(self, conflict: Conflict, 
                         engine_results: Dict[str, Any]) -> Optional[Resolution]:
        """
        Resolve a conflict using appropriate strategy
        """
        # Choose resolution strategy based on conflict type
        if conflict.conflict_type == "contradictory_results":
            return self._resolve_by_confidence(conflict, engine_results)
        elif conflict.conflict_type == "metric_discrepancy":
            return self._resolve_by_consensus(conflict, engine_results)
        elif conflict.conflict_type == "recommendation_conflict":
            return self._resolve_by_expertise(conflict, engine_results)
        else:
            return None
    
    def _resolve_by_confidence(self, conflict: Conflict, 
                              engine_results: Dict[str, Any]) -> Resolution:
        """
        Resolve by choosing the result with higher confidence
        Uses a multi-factor confidence calculation
        """
        best_engine = None
        best_score = 0
        
        for engine in conflict.engines:
            result = engine_results.get(engine, "")
            
            # Calculate multi-factor confidence score
            score = self._calculate_engine_confidence(engine, result, conflict)
            
            if score > best_score:
                best_score = score
                best_engine = engine
        
        return Resolution(
            conflict=conflict,
            strategy_used="confidence_based",
            resolved_value=engine_results.get(best_engine),
            explanation=f"Selected {best_engine} with confidence score: {best_score:.2f}",
            confidence=best_score
        )
    
    def _calculate_engine_confidence(self, engine: str, result: Any, conflict: Conflict) -> float:
        """
        Calculate confidence score for an engine result
        Combines multiple factors for robust scoring
        """
        confidence_factors = []
        
        # Factor 1: Result completeness (0.0 - 1.0)
        result_str = str(result)
        if len(result_str) > 1000:
            completeness = 1.0
        elif len(result_str) > 500:
            completeness = 0.8
        elif len(result_str) > 100:
            completeness = 0.6
        else:
            completeness = 0.3
        confidence_factors.append(('completeness', completeness, 0.3))
        
        # Factor 2: Result structure (0.0 - 1.0)
        if isinstance(result, dict) and len(result) > 2:
            structure = 0.9
        elif isinstance(result, (list, dict)):
            structure = 0.7
        elif isinstance(result, str) and '\n' in result:
            structure = 0.5
        else:
            structure = 0.3
        confidence_factors.append(('structure', structure, 0.2))
        
        # Factor 3: Specific findings present (0.0 - 1.0)
        findings_keywords = ['found', 'detected', 'identified', 'discovered', 'analyzed']
        findings_score = sum(1 for kw in findings_keywords if kw in result_str.lower()) / len(findings_keywords)
        confidence_factors.append(('findings', findings_score, 0.2))
        
        # Factor 4: Metrics present (0.0 - 1.0)
        import re
        metrics_pattern = r'\d+(?:\.\d+)?%|\d+\s+(?:ms|errors?|warnings?|issues?)'
        metrics_found = len(re.findall(metrics_pattern, result_str))
        metrics_score = min(1.0, metrics_found / 5)  # Cap at 5 metrics
        confidence_factors.append(('metrics', metrics_score, 0.15))
        
        # Factor 5: Engine reliability (hardcoded for now, could be learned)
        engine_reliability = {
            'check_quality': 0.9,
            'analyze_code': 0.85,
            'performance_profiler': 0.85,
            'analyze_test_coverage': 0.9,
            'config_validator': 0.8,
            'analyze_database': 0.8,
            'api_contract_checker': 0.85,
            'map_dependencies': 0.85,
            'interface_inconsistency_detector': 0.8,
            'analyze_logs': 0.75,
            'search_code': 0.7,
            'analyze_docs': 0.75
        }
        reliability = engine_reliability.get(engine, 0.5)
        confidence_factors.append(('reliability', reliability, 0.15))
        
        # Calculate weighted confidence score
        total_confidence = 0.0
        for factor_name, score, weight in confidence_factors:
            total_confidence += score * weight
            logger.debug(f"Confidence factor {factor_name}: {score:.2f} (weight: {weight})")
        
        logger.debug(f"Total confidence for {engine}: {total_confidence:.2f}")
        return min(1.0, max(0.0, total_confidence))  # Clamp to [0.0, 1.0]
    
    def _resolve_by_consensus(self, conflict: Conflict, 
                            engine_results: Dict[str, Any]) -> Resolution:
        """
        Resolve by finding consensus among results
        """
        # For metric discrepancies, use median value
        values = list(conflict.conflicting_findings.values())
        if all(isinstance(v, (int, float)) for v in values):
            median_value = sorted(values)[len(values) // 2]
            return Resolution(
                conflict=conflict,
                strategy_used="consensus_median",
                resolved_value=median_value,
                explanation=f"Used median value from {len(values)} engines",
                confidence=0.8
            )
        
        # For other cases, use majority if possible
        return Resolution(
            conflict=conflict,
            strategy_used="consensus",
            resolved_value=conflict.conflicting_findings,
            explanation="No clear consensus, presenting all views",
            confidence=0.5
        )
    
    def _resolve_by_expertise(self, conflict: Conflict, 
                             engine_results: Dict[str, Any]) -> Resolution:
        """
        Resolve by weighting engines based on their expertise
        """
        # Engine expertise mapping (could be configurable)
        expertise_weights = {
            'check_quality': {'security': 0.9, 'performance': 0.8, 'quality': 0.9},
            'analyze_code': {'architecture': 0.9, 'quality': 0.7},
            'performance_profiler': {'performance': 1.0},
            'config_validator': {'security': 0.8, 'configuration': 0.9},
            'analyze_test_coverage': {'testing': 1.0, 'quality': 0.7}
        }
        
        # Find the engine with highest expertise for this conflict
        best_engine = None
        best_weight = 0
        
        # Determine conflict domain
        conflict_domain = 'general'
        if 'security' in conflict.description.lower():
            conflict_domain = 'security'
        elif 'performance' in conflict.description.lower():
            conflict_domain = 'performance'
        elif 'quality' in conflict.description.lower():
            conflict_domain = 'quality'
        
        for engine in conflict.engines:
            weight = expertise_weights.get(engine, {}).get(conflict_domain, 0.5)
            if weight > best_weight:
                best_weight = weight
                best_engine = engine
        
        return Resolution(
            conflict=conflict,
            strategy_used="expertise_weighted",
            resolved_value=conflict.conflicting_findings.get(best_engine),
            explanation=f"Selected {best_engine} based on {conflict_domain} expertise (weight: {best_weight})",
            confidence=best_weight
        )
    
    def _generate_summary(self) -> str:
        """
        Generate a summary of the correlation analysis
        """
        summary_parts = []
        
        # Correlation summary
        if self.correlations:
            strong_corr = sum(1 for c in self.correlations 
                            if c.strength == CorrelationStrength.STRONG)
            moderate_corr = sum(1 for c in self.correlations 
                              if c.strength == CorrelationStrength.MODERATE)
            
            summary_parts.append(f"Found {len(self.correlations)} correlations: "
                               f"{strong_corr} strong, {moderate_corr} moderate")
            
            # Confirmation vs contradiction
            confirmations = sum(1 for c in self.correlations 
                              if c.correlation_type == CorrelationType.CONFIRMS)
            contradictions = sum(1 for c in self.correlations 
                               if c.correlation_type == CorrelationType.CONTRADICTS)
            
            summary_parts.append(f"Results show {confirmations} confirmations and "
                               f"{contradictions} contradictions")
        
        # Conflict summary
        if self.conflicts:
            critical = sum(1 for c in self.conflicts 
                         if c.severity == ConflictSeverity.CRITICAL)
            summary_parts.append(f"Identified {len(self.conflicts)} conflicts, "
                               f"{critical} critical")
        
        # Resolution summary
        if self.resolutions:
            high_conf = sum(1 for r in self.resolutions if r.confidence > 0.8)
            summary_parts.append(f"Resolved {len(self.resolutions)} conflicts, "
                               f"{high_conf} with high confidence")
        
        if not summary_parts:
            return "No significant correlations or conflicts detected"
        
        return "; ".join(summary_parts)