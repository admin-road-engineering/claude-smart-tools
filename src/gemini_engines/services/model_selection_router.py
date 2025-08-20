"""
Model Selection Router for Gemini MCP Tools
Implements intelligent model selection based on tool type, complexity, and user intent
"""
import logging
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class GeminiModel(Enum):
    """Available Gemini models with their characteristics"""
    PRO = "pro"              # Most capable, deep reasoning, higher cost
    FLASH = "flash"          # Balanced, good for structured analysis
    FLASH_LITE = "flash-lite"  # Fast, efficient, simple tasks
    
    @classmethod
    def validate(cls, model_name: str) -> bool:
        """Validate if model name is valid"""
        return model_name in [m.value for m in cls]
    
    @classmethod
    def get_upgrade_path(cls, current_model: str) -> str:
        """Get the next higher model in the hierarchy"""
        if current_model == cls.FLASH_LITE.value:
            return cls.FLASH.value
        elif current_model == cls.FLASH.value:
            return cls.PRO.value
        return cls.PRO.value  # Already at highest


class ModelSelectionRouter:
    """
    Simplified model selection following GEMINI.md principles:
    1. Pro for collaborative dialogue only
    2. Flash for security-critical or quality analysis  
    3. Flash-lite for everything else (cost-conscious)
    """
    
    # Balanced three-tier model mapping (Gemini's refined recommendation)
    DEFAULT_MODELS = {
        # Pro Tier: Multi-turn, complex reasoning
        "review_output": GeminiModel.PRO.value,
        
        # Flash Tier: Requires nuanced analysis
        "check_quality": GeminiModel.FLASH.value,             # Security-critical analysis
        "map_dependencies": GeminiModel.FLASH.value,          # Graph analysis quality
        "performance_profiler": GeminiModel.FLASH.value,      # Flow analysis quality  
        "analyze_code": GeminiModel.FLASH.value,              # Code understanding quality
        
        # Flash-lite Tier: Simple, fast tasks
        "search_code": GeminiModel.FLASH_LITE.value,          # Pattern matching
        "analyze_docs": GeminiModel.FLASH_LITE.value,         # Summarization
        "analyze_logs": GeminiModel.FLASH_LITE.value,         # Pattern recognition
        "analyze_database": GeminiModel.FLASH_LITE.value,     # Schema analysis
        "api_contract_checker": GeminiModel.FLASH_LITE.value, # Schema parsing
        "analyze_test_coverage": GeminiModel.FLASH_LITE.value,# Pattern-based
        "interface_inconsistency_detector": GeminiModel.FLASH_LITE.value, # Pattern matching
        "config_validator": GeminiModel.FLASH_LITE.value,     # Simple validation
    }
    
    def __init__(self):
        """Initialize the model selection router"""
        self.logger = logging.getLogger(__name__)
    
    def select_model(self,
                    tool_name: str,
                    user_prompt: Optional[str] = None,
                    verbose: bool = False,
                    analysis_type: Optional[str] = None,
                    check_type: Optional[str] = None,
                    focus: Optional[str] = None,
                    detail_level: Optional[str] = None,
                    content_size: Optional[int] = None,
                    file_paths: Optional[List[str]] = None) -> str:
        """
        Simplified model selection following GEMINI.md principles
        
        Args:
            tool_name: Name of the tool being executed
            focus: Focus area (security triggers Flash upgrade)
            detail_level: Level of detail (comprehensive triggers Pro upgrade)
            content_size: Size of content in bytes (triggers model upgrades)
            file_paths: File paths for size estimation
            
        Returns:
            Selected model name (pro, flash, or flash-lite)
        """
        # Rule 1: Pro for collaborative dialogue (the core feature)
        if tool_name == "review_output":
            self.logger.info(f"review_output uses pro model for collaborative dialogue")
            return GeminiModel.PRO.value
        
        # Rule 2: Security-critical tools or focus get Flash (strengthened default)
        # check_quality gets Flash regardless of focus for quality baseline
        if tool_name == "check_quality" or focus == "security":
            self.logger.info(f"Security-critical analysis detected, using flash model")
            return GeminiModel.FLASH.value
        
        # Rule 3: Comprehensive detail level gets Pro upgrade
        if detail_level == "comprehensive":
            self.logger.info(f"Comprehensive detail requested, upgrading to pro")
            return GeminiModel.PRO.value
        
        # Rule 4: Dynamic model upgrading based on content size
        default_model = self.DEFAULT_MODELS.get(tool_name, GeminiModel.FLASH_LITE.value)
        selected_model = default_model
        
        # Estimate content size if not provided
        if content_size is None and file_paths:
            content_size = self._estimate_content_size(file_paths)
        
        # Upgrade model based on content size (especially for data-intensive tools)
        if content_size:
            if content_size > 2_000_000:  # 2MB+ → Pro model
                if selected_model == GeminiModel.FLASH_LITE.value:
                    selected_model = GeminiModel.PRO.value
                    self.logger.info(f"Upgraded {tool_name} from {default_model} to pro due to large content ({content_size/1000000:.1f}MB)")
                elif selected_model == GeminiModel.FLASH.value:
                    selected_model = GeminiModel.PRO.value
                    self.logger.info(f"Upgraded {tool_name} from {default_model} to pro due to large content ({content_size/1000000:.1f}MB)")
            elif content_size > 500_000:  # 500KB+ → Flash model
                if selected_model == GeminiModel.FLASH_LITE.value:
                    selected_model = GeminiModel.FLASH.value
                    self.logger.info(f"Upgraded {tool_name} from {default_model} to flash due to medium content ({content_size/1000:.0f}KB)")
        
        # Special handling for analyze_logs (was problematic with flash-lite)
        if tool_name == "analyze_logs" and selected_model == GeminiModel.FLASH_LITE.value:
            selected_model = GeminiModel.FLASH.value  # Minimum flash for log analysis
            self.logger.info(f"Upgraded analyze_logs from flash-lite to flash (minimum for log processing)")
        
        self.logger.info(f"Selected model '{selected_model}' for tool '{tool_name}' (default: {default_model})")
        return selected_model
    
    def _estimate_content_size(self, file_paths: List[str]) -> int:
        """Estimate total content size from file paths"""
        import os
        total_size = 0
        for path_str in file_paths:
            try:
                from pathlib import Path
                path = Path(path_str)
                if path.is_file():
                    total_size += path.stat().st_size
                elif path.is_dir():
                    # Estimate directory size (first 50 files to avoid long scans)
                    count = 0
                    for file_path in path.rglob("*"):
                        if file_path.is_file() and count < 50:
                            total_size += file_path.stat().st_size
                            count += 1
                        elif count >= 50:
                            # Extrapolate based on first 50 files
                            total_files = sum(1 for _ in path.rglob("*") if _.is_file())
                            total_size = int(total_size * (total_files / 50))
                            break
            except (OSError, PermissionError):
                continue  # Skip files we can't access
        
        return total_size
    
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a model"""
        if not GeminiModel.validate(model_name):
            raise ValueError(f"Invalid model name: {model_name}")
        
        model_info = {
            GeminiModel.PRO.value: {
                "name": "Gemini Pro",
                "description": "Most capable model for complex reasoning and analysis",
                "use_cases": ["Security analysis", "Architecture review", "Complex refactoring"],
                "relative_cost": 3,
                "relative_speed": 1,
            },
            GeminiModel.FLASH.value: {
                "name": "Gemini Flash", 
                "description": "Balanced model for standard analysis tasks",
                "use_cases": ["Code search", "Documentation", "Pattern matching"],
                "relative_cost": 2,
                "relative_speed": 2,
            },
            GeminiModel.FLASH_LITE.value: {
                "name": "Gemini Flash Lite",
                "description": "Fast, efficient model for simple tasks",
                "use_cases": ["Config validation", "Simple checks", "Quick lookups"],
                "relative_cost": 1,
                "relative_speed": 3,
            }
        }
        
        return model_info.get(model_name, {})
    
    def estimate_cost_performance(self, tool_name: str, model_name: str) -> Dict[str, Any]:
        """Estimate relative cost and performance for a tool-model combination"""
        model_info = self.get_model_info(model_name)
        
        return {
            "tool": tool_name,
            "model": model_name,
            "relative_cost": model_info.get("relative_cost", 2),
            "relative_speed": model_info.get("relative_speed", 2),
            "optimal": model_name == self.DEFAULT_MODELS.get(tool_name, GeminiModel.FLASH.value),
        }