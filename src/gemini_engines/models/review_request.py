"""
Review request data model for consolidating review parameters.

This model addresses the architectural issue of ambiguous content parameters
and massive parameter lists in ReviewService and ResilientReviewService.
"""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from pathlib import Path


class ReviewRequest(BaseModel):
    """
    Consolidated review request parameters.
    
    Addresses architectural issues:
    - Ambiguous content parameters in ReviewService
    - Interface bloat in ResilientReviewService 
    - Massive parameter lists causing tight coupling
    """
    
    # Core review parameters
    output: Optional[str] = Field(None, description="Direct content to review")
    is_plan: bool = Field(True, description="Whether content is a plan (true) or code (false)")
    focus: str = Field("all", description="Review focus area")
    context: Optional[str] = Field(None, description="Additional context for review")
    detail_level: str = Field("detailed", description="Level of detail in review")
    response_style: str = Field("detailed", description="Response verbosity: concise, detailed, executive")
    
    # Content source alternatives
    file_path: Optional[str] = Field(None, description="Path to file containing content to review")
    content_chunks: Optional[List[Dict[str, Any]]] = Field(None, description="Pre-chunked content")
    content_summary: Optional[str] = Field(None, description="Summary of content to review")
    
    # Dialogue parameters
    claude_response: Optional[str] = Field(None, description="Claude's previous response for dialogue")
    is_first_review: bool = Field(False, description="Whether this is the first review in a session")
    task_id: Optional[str] = Field(None, description="Task identifier for session tracking")
    requested_files: Optional[List[str]] = Field(None, description="Specific files requested for review")
    dialogue_focus: str = Field("general", description="Focus area for dialogue")
    max_dialogue_rounds: int = Field(3, description="Maximum dialogue rounds")
    
    # Context from other tools
    analysis_context: Optional[List[Dict[str, Any]]] = Field(None, description="Context from full_analysis or other tools")
    
    class Config:
        """Pydantic configuration"""
        validate_assignment = True
        extra = "forbid"  # Prevent unknown parameters
        
    @model_validator(mode='after')
    def validate_content_source(self):
        """
        Ensure exactly one content source is provided.
        
        This addresses the ambiguous content parameters issue by enforcing
        clear precedence rules and preventing conflicting inputs.
        """
        content_sources = [
            'output',
            'file_path', 
            'content_chunks',
            'content_summary'
        ]
        
        provided_sources = [
            source for source in content_sources 
            if getattr(self, source) is not None
        ]
        
        if len(provided_sources) == 0:
            raise ValueError("At least one content source must be provided")
        
        if len(provided_sources) > 1:
            raise ValueError(
                f"Only one content source allowed. Provided: {provided_sources}. "
                f"Use file_path for files, output for direct content, "
                f"content_chunks for pre-processed content, or content_summary for summaries."
            )
            
        return self
    
    @property
    def content_source_type(self) -> str:
        """Identify which content source is being used"""
        if self.output is not None:
            return "direct"
        elif self.file_path is not None:
            return "file"
        elif self.content_chunks is not None:
            return "chunks"
        elif self.content_summary is not None:
            return "summary"
        else:
            return "none"
    
    def get_content(self) -> str:
        """
        Resolve the actual content to be reviewed.
        
        This method implements clear precedence rules, resolving the
        ambiguous content parameters issue.
        """
        if self.output is not None:
            return self.output
        
        elif self.file_path is not None:
            # File content will be read by the service
            # This is a placeholder that signals file reading is needed
            return f"<FILE_CONTENT:{self.file_path}>"
        
        elif self.content_chunks is not None:
            # Combine chunks into single content
            if isinstance(self.content_chunks, list):
                return "\n".join(str(chunk) for chunk in self.content_chunks)
            else:
                return str(self.content_chunks)
        
        elif self.content_summary is not None:
            return self.content_summary
        
        else:
            raise ValueError("No content source available")
    
    def __str__(self) -> str:
        """String representation for logging and debugging"""
        return (
            f"ReviewRequest(source={self.content_source_type}, "
            f"focus={self.focus}, detail={self.detail_level}, "
            f"is_plan={self.is_plan})"
        )