"""
Accessibility Checker Tool
Validates HTML/UI components for accessibility compliance
"""
import logging
import os
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from .base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)

@dataclass
class AccessibilityIssue:
    """Represents an accessibility issue found in a file"""
    file: str
    line_number: int
    issue_type: str
    severity: str  # 'error', 'warning', 'info'
    description: str
    suggestion: str

class AccessibilityChecker(BaseTool):
    """
    Accessibility validation tool for HTML/UI components
    
    Features:
    - Check for missing alt text on images
    - Validate ARIA attributes
    - Check color contrast ratios (basic)
    - Validate heading hierarchy
    - Check for keyboard navigation support
    - Validate form labels and associations
    """
    
    def __init__(self):
        """Initialize the AccessibilityChecker"""
        super().__init__("AccessibilityChecker")
        
        # Define accessibility rules
        self.rules = {
            'images': self._check_images,
            'headings': self._check_heading_hierarchy,
            'forms': self._check_form_labels,
            'aria': self._check_aria_attributes,
            'keyboard': self._check_keyboard_support,
            'contrast': self._check_color_contrast
        }
    
    def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Core accessibility checking logic
        
        Args:
            files: HTML/JSX/TSX files to check
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with accessibility findings
        """
        issues = []
        files_checked = 0
        
        # Process each file
        for file_path in files:
            # Only check relevant file types
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']:
                logger.debug(f"Skipping non-HTML/UI file: {file_path}")
                continue
            
            files_checked += 1
            
            try:
                content = self.read_file_safe(file_path)
                if content:
                    file_issues = self._analyze_file(file_path, content, **kwargs)
                    issues.extend(file_issues)
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                issues.append(AccessibilityIssue(
                    file=file_path,
                    line_number=0,
                    issue_type="error",
                    severity="error",
                    description=f"Failed to analyze file: {str(e)}",
                    suggestion="Check file encoding and syntax"
                ))
        
        # Categorize issues by severity
        errors = [i for i in issues if i.severity == 'error']
        warnings = [i for i in issues if i.severity == 'warning']
        info = [i for i in issues if i.severity == 'info']
        
        return {
            "files_checked": files_checked,
            "total_issues": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(info),
            "issues": [asdict(i) for i in issues],
            "summary": {
                "most_common_issues": self._get_most_common_issues(issues),
                "files_with_issues": len(set(i.file for i in issues)),
                "compliance_score": self._calculate_compliance_score(files_checked, issues)
            }
        }
    
    def _analyze_file(self, file_path: str, content: str, **kwargs) -> List[AccessibilityIssue]:
        """
        Analyze a single file for accessibility issues
        
        Args:
            file_path: Path to the file
            content: File content
            **kwargs: Check options
            
        Returns:
            List of accessibility issues found
        """
        issues = []
        lines = content.split('\n')
        
        # Determine which checks to run
        checks_to_run = []
        if kwargs.get('check_images', True):
            checks_to_run.append('images')
        if kwargs.get('check_headings', True):
            checks_to_run.append('headings')
        if kwargs.get('check_forms', True):
            checks_to_run.append('forms')
        if kwargs.get('check_aria', True):
            checks_to_run.append('aria')
        if kwargs.get('check_keyboard', True):
            checks_to_run.append('keyboard')
        if kwargs.get('check_contrast', False):  # Disabled by default (requires color analysis)
            checks_to_run.append('contrast')
        
        # Run selected checks
        for check_name in checks_to_run:
            if check_name in self.rules:
                check_func = self.rules[check_name]
                check_issues = check_func(file_path, content, lines)
                issues.extend(check_issues)
        
        return issues
    
    def _check_images(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Check for accessibility issues with images"""
        issues = []
        
        # Regular expression for img tags
        img_pattern = re.compile(r'<img\s+([^>]*?)/?>', re.IGNORECASE | re.DOTALL)
        
        for i, line in enumerate(lines, 1):
            for match in img_pattern.finditer(line):
                attrs = match.group(1)
                
                # Check for alt attribute
                if 'alt=' not in attrs.lower():
                    issues.append(AccessibilityIssue(
                        file=file_path,
                        line_number=i,
                        issue_type="missing_alt_text",
                        severity="error",
                        description="Image missing alt attribute",
                        suggestion="Add alt attribute with descriptive text or alt='' for decorative images"
                    ))
                elif 'alt=""' in attrs or "alt=''" in attrs:
                    # Check if this might be a meaningful image
                    if 'src=' in attrs and any(keyword in attrs.lower() for keyword in ['logo', 'icon', 'button', 'banner']):
                        issues.append(AccessibilityIssue(
                            file=file_path,
                            line_number=i,
                            issue_type="empty_alt_text",
                            severity="warning",
                            description="Potentially meaningful image has empty alt text",
                            suggestion="Consider adding descriptive alt text for this image"
                        ))
        
        # Check for background images in CSS that might need alternatives
        bg_image_pattern = re.compile(r'background-image:\s*url\([\'"]?([^\'"]+)[\'"]?\)', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if bg_image_pattern.search(line):
                issues.append(AccessibilityIssue(
                    file=file_path,
                    line_number=i,
                    issue_type="background_image",
                    severity="info",
                    description="Background image detected",
                    suggestion="Ensure decorative images are CSS backgrounds, meaningful images use <img> with alt"
                ))
        
        return issues
    
    def _check_heading_hierarchy(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Check for proper heading hierarchy"""
        issues = []
        
        # Find all headings
        heading_pattern = re.compile(r'<h([1-6])(?:\s+[^>]*)?>.*?</h\1>', re.IGNORECASE | re.DOTALL)
        headings = []
        
        for i, line in enumerate(lines, 1):
            for match in heading_pattern.finditer(line):
                level = int(match.group(1))
                headings.append((level, i))
        
        # Check heading hierarchy
        if headings:
            # Check if starts with h1
            if headings[0][0] != 1:
                issues.append(AccessibilityIssue(
                    file=file_path,
                    line_number=headings[0][1],
                    issue_type="heading_hierarchy",
                    severity="warning",
                    description=f"Document starts with h{headings[0][0]} instead of h1",
                    suggestion="Start document with h1 for proper hierarchy"
                ))
            
            # Check for skipped levels
            for i in range(1, len(headings)):
                prev_level = headings[i-1][0]
                curr_level = headings[i][0]
                
                if curr_level > prev_level + 1:
                    issues.append(AccessibilityIssue(
                        file=file_path,
                        line_number=headings[i][1],
                        issue_type="heading_skip",
                        severity="warning",
                        description=f"Heading level skipped (h{prev_level} to h{curr_level})",
                        suggestion="Use sequential heading levels without skipping"
                    ))
        
        return issues
    
    def _check_form_labels(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Check for proper form labeling"""
        issues = []
        
        # Check for inputs without labels
        input_pattern = re.compile(r'<input\s+([^>]*?)/?>', re.IGNORECASE)
        label_pattern = re.compile(r'<label\s+([^>]*?)>', re.IGNORECASE)
        
        for i, line in enumerate(lines, 1):
            for match in input_pattern.finditer(line):
                attrs = match.group(1)
                
                # Skip hidden inputs
                if 'type="hidden"' in attrs or "type='hidden'" in attrs:
                    continue
                
                # Check for id attribute
                id_match = re.search(r'id=["\']([^"\']+)["\']', attrs)
                if not id_match:
                    # Check for aria-label or aria-labelledby
                    if not ('aria-label' in attrs or 'aria-labelledby' in attrs):
                        issues.append(AccessibilityIssue(
                            file=file_path,
                            line_number=i,
                            issue_type="unlabeled_input",
                            severity="error",
                            description="Input element without label association",
                            suggestion="Add id to input and associate with label, or use aria-label"
                        ))
        
        # Check for empty labels
        empty_label_pattern = re.compile(r'<label[^>]*?>\s*</label>', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if empty_label_pattern.search(line):
                issues.append(AccessibilityIssue(
                    file=file_path,
                    line_number=i,
                    issue_type="empty_label",
                    severity="error",
                    description="Empty label element",
                    suggestion="Add descriptive text to label"
                ))
        
        return issues
    
    def _check_aria_attributes(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Check for proper ARIA attribute usage"""
        issues = []
        
        # Common ARIA attribute mistakes
        aria_pattern = re.compile(r'aria-([a-z]+)=["\']([^"\']*)["\']', re.IGNORECASE)
        
        valid_aria_attrs = {
            'label', 'labelledby', 'describedby', 'hidden', 'expanded',
            'selected', 'checked', 'pressed', 'level', 'valuemin',
            'valuemax', 'valuenow', 'valuetext', 'controls', 'live',
            'atomic', 'relevant', 'busy', 'disabled', 'invalid',
            'haspopup', 'autocomplete', 'multiline', 'multiselectable',
            'orientation', 'readonly', 'required', 'sort', 'activedescendant'
        }
        
        for i, line in enumerate(lines, 1):
            for match in aria_pattern.finditer(line):
                attr_name = match.group(1).lower()
                attr_value = match.group(2)
                
                # Check for invalid ARIA attributes
                if attr_name not in valid_aria_attrs:
                    issues.append(AccessibilityIssue(
                        file=file_path,
                        line_number=i,
                        issue_type="invalid_aria",
                        severity="error",
                        description=f"Invalid ARIA attribute: aria-{attr_name}",
                        suggestion="Use valid ARIA attributes from WAI-ARIA specification"
                    ))
                
                # Check for empty values where they shouldn't be
                if not attr_value and attr_name in ['label', 'labelledby', 'describedby']:
                    issues.append(AccessibilityIssue(
                        file=file_path,
                        line_number=i,
                        issue_type="empty_aria_value",
                        severity="error",
                        description=f"Empty value for aria-{attr_name}",
                        suggestion="Provide a value or remove the attribute"
                    ))
        
        return issues
    
    def _check_keyboard_support(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Check for keyboard navigation support"""
        issues = []
        
        # Check for click handlers without keyboard handlers
        click_pattern = re.compile(r'on[Cc]lick=["\']', re.IGNORECASE)
        
        for i, line in enumerate(lines, 1):
            if click_pattern.search(line):
                # Check if there's also a keyboard handler
                if not any(handler in line.lower() for handler in ['onkeydown', 'onkeyup', 'onkeypress']):
                    # Check if it's on a naturally keyboard-accessible element
                    if not any(elem in line.lower() for elem in ['<button', '<a ', '<input', '<select']):
                        issues.append(AccessibilityIssue(
                            file=file_path,
                            line_number=i,
                            issue_type="missing_keyboard_handler",
                            severity="warning",
                            description="Click handler without keyboard support on non-interactive element",
                            suggestion="Add keyboard event handlers or use semantic HTML elements"
                        ))
        
        # Check for positive tabindex
        tabindex_pattern = re.compile(r'tabindex=["\']([^"\']+)["\']', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            for match in tabindex_pattern.finditer(line):
                value = match.group(1)
                try:
                    if int(value) > 0:
                        issues.append(AccessibilityIssue(
                            file=file_path,
                            line_number=i,
                            issue_type="positive_tabindex",
                            severity="warning",
                            description=f"Positive tabindex value ({value}) can disrupt natural tab order",
                            suggestion="Use tabindex='0' or '-1' instead"
                        ))
                except ValueError:
                    pass
        
        return issues
    
    def _check_color_contrast(self, file_path: str, content: str, lines: List[str]) -> List[AccessibilityIssue]:
        """Basic color contrast checking (limited without actual rendering)"""
        issues = []
        
        # This is a simplified check - real contrast checking requires rendering
        # Look for potentially problematic color combinations
        style_pattern = re.compile(r'style=["\']([^"\']+)["\']', re.IGNORECASE)
        
        problematic_combinations = [
            (r'color:\s*#?[cf]{3}', r'background-color:\s*#?[cf]{3}'),  # Light on light
            (r'color:\s*#?[0-3]{3}', r'background-color:\s*#?[0-3]{3}'),  # Dark on dark
        ]
        
        for i, line in enumerate(lines, 1):
            for match in style_pattern.finditer(line):
                style = match.group(1).lower()
                
                # Check for low contrast combinations
                if 'color:' in style and 'background' in style:
                    issues.append(AccessibilityIssue(
                        file=file_path,
                        line_number=i,
                        issue_type="potential_contrast_issue",
                        severity="info",
                        description="Inline styles with color and background - verify contrast ratio",
                        suggestion="Ensure text has WCAG AA compliant contrast ratio (4.5:1 for normal text)"
                    ))
        
        return issues
    
    def _get_most_common_issues(self, issues: List[AccessibilityIssue]) -> List[Dict[str, Any]]:
        """Get the most common issue types"""
        issue_counts = {}
        for issue in issues:
            issue_counts[issue.issue_type] = issue_counts.get(issue.issue_type, 0) + 1
        
        # Sort by count and return top 5
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"type": t, "count": c} for t, c in sorted_issues[:5]]
    
    def _calculate_compliance_score(self, files_checked: int, issues: List[AccessibilityIssue]) -> float:
        """Calculate a basic compliance score"""
        if files_checked == 0:
            return 100.0
        
        # Weight issues by severity
        weights = {'error': 10, 'warning': 5, 'info': 1}
        total_weight = sum(weights[i.severity] for i in issues)
        
        # Maximum possible weight (assume 10 errors per file as worst case)
        max_weight = files_checked * 10 * weights['error']
        
        # Calculate score (100 = perfect, 0 = worst)
        score = max(0, 100 - (total_weight / max_weight * 100))
        return round(score, 2)
    
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get AI interpretation of accessibility findings
        
        Args:
            core_results: Results from core utility
            context: Optional context about the application
            
        Returns:
            AI interpretation and recommendations
        """
        if not hasattr(self, 'gemini_client') or not self.gemini_client:
            return "AI interpretation not available - Gemini client not configured"
        
        prompt = f"""
        As an accessibility expert, analyze these accessibility findings and provide recommendations.
        
        Application Context: {context or 'Web application'}
        
        Findings:
        - Files checked: {core_results['files_checked']}
        - Total issues: {core_results['total_issues']}
        - Errors: {core_results['errors']}
        - Warnings: {core_results['warnings']}
        - Compliance score: {core_results['summary']['compliance_score']}%
        
        Most common issues:
        {self._format_common_issues(core_results['summary']['most_common_issues'])}
        
        Sample issues:
        {self._format_sample_issues(core_results['issues'][:10])}
        
        Please provide:
        1. Overall accessibility assessment
        2. Priority fixes (most impactful for users)
        3. Quick wins (easy fixes with high impact)
        4. Long-term recommendations
        5. Testing suggestions
        """
        
        try:
            response, _, _ = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash",
                timeout=60
            )
            return response
        except Exception as e:
            logger.error(f"AI interpretation failed: {e}")
            return f"AI interpretation failed: {str(e)}"
    
    def _format_common_issues(self, common_issues: List[Dict]) -> str:
        """Format common issues for prompt"""
        if not common_issues:
            return "No common patterns identified"
        
        lines = []
        for issue in common_issues:
            lines.append(f"- {issue['type']}: {issue['count']} occurrences")
        return "\n".join(lines)
    
    def _format_sample_issues(self, issues: List[Dict]) -> str:
        """Format sample issues for prompt"""
        if not issues:
            return "No issues found"
        
        lines = []
        for issue in issues[:10]:  # Limit to 10 samples
            lines.append(f"- [{issue['severity']}] {issue['file']}:{issue['line_number']} - {issue['description']}")
        return "\n".join(lines)