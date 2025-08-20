"""
Unit tests for UnderstandTool routing logic and functionality
Tests the understand tool's engine selection and routing decisions
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import os

# Import the class to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from smart_tools.understand_tool import UnderstandTool


class TestUnderstandToolRouting:
    """Test UnderstandTool routing logic"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_engines = {
            'analyze_code': AsyncMock(return_value="Mock code analysis"),
            'search_code': AsyncMock(return_value="Mock search results"),
            'analyze_docs': AsyncMock(return_value="Mock doc analysis"),
            'map_dependencies': AsyncMock(return_value="Mock dependency map")
        }
        self.tool = UnderstandTool(self.mock_engines)
    
    def test_routing_with_no_question(self):
        """Test routing strategy when no specific question is provided"""
        strategy = self.tool.get_routing_strategy(files=['src/test.py'])
        
        assert 'engines' in strategy
        assert 'analyze_code' in strategy['engines']
        assert strategy['strategy'] == 'sequential'
        assert 'architectural analysis' in strategy['reason'].lower()
    
    def test_routing_with_specific_question(self):
        """Test routing strategy when specific question is provided"""
        strategy = self.tool.get_routing_strategy(
            files=['src/test.py'], 
            question="How does authentication work?"
        )
        
        assert 'engines' in strategy
        assert 'analyze_code' in strategy['engines']
        assert 'search_code' in strategy['engines']
        assert 'specific question' in strategy['reason'].lower()
    
    def test_routing_with_docs_present(self):
        """Test routing includes docs analysis when README or docs found"""
        # Mock the _find_documentation method
        with patch.object(self.tool, '_find_documentation', return_value=['README.md']):
            strategy = self.tool.get_routing_strategy(files=['src/test.py'])
            
            assert 'analyze_docs' in strategy['engines']
            assert 'documentation analysis' in strategy['reason'].lower()
    
    def test_routing_for_architecture_focus(self):
        """Test routing strategy for architecture-focused analysis"""
        strategy = self.tool.get_routing_strategy(
            files=['src/'], 
            focus='architecture'
        )
        
        assert 'engines' in strategy
        assert 'analyze_code' in strategy['engines']
        assert 'map_dependencies' in strategy['engines']
        assert 'architectural understanding' in strategy['reason'].lower()
    
    def test_routing_excludes_unavailable_engines(self):
        """Test that routing only includes available engines"""
        # Create tool with limited engines
        limited_engines = {
            'analyze_code': AsyncMock(return_value="Mock analysis")
        }
        tool = UnderstandTool(limited_engines)
        
        strategy = tool.get_routing_strategy(files=['src/test.py'])
        
        assert 'analyze_code' in strategy['engines']
        assert 'search_code' not in strategy['engines']  # Not available
        assert 'analyze_docs' not in strategy['engines']  # Not available


class TestUnderstandToolExecution:
    """Test UnderstandTool execution logic"""
    
    def setup_method(self):
        """Set up test fixtures with comprehensive mocks"""
        self.mock_engines = {
            'analyze_code': AsyncMock(return_value="# Code Analysis\nTest analysis result"),
            'search_code': AsyncMock(return_value="# Search Results\nFound relevant patterns"),
            'analyze_docs': AsyncMock(return_value="# Documentation\nProject overview"),
            'map_dependencies': AsyncMock(return_value="# Dependencies\nDependency structure")
        }
        self.tool = UnderstandTool(self.mock_engines)
    
    @pytest.mark.asyncio
    async def test_basic_understanding_execution(self):
        """Test basic understanding execution without question"""
        result = await self.tool.execute(files=['src/test.py'])
        
        assert result.success is True
        assert result.tool_name == 'understand'
        assert 'analyze_code' in result.engines_used
        assert len(result.result) > 0
        assert 'architectural analysis' in result.routing_decision.lower()
    
    @pytest.mark.asyncio
    async def test_understanding_with_question(self):
        """Test understanding execution with specific question"""
        result = await self.tool.execute(
            files=['src/auth.py'], 
            question="How does user authentication work?"
        )
        
        assert result.success is True
        assert 'analyze_code' in result.engines_used
        assert 'search_code' in result.engines_used
        assert 'authentication' in result.metadata.get('question', '').lower()
    
    @pytest.mark.asyncio
    async def test_parallel_execution_mode(self):
        """Test that parallel execution works correctly"""
        # Mock parallel execution
        with patch.object(self.tool, '_run_parallel_analysis') as mock_parallel:
            mock_parallel.return_value = {
                'analyze_code': "Mock analysis",
                'search_code': "Mock search"
            }
            
            result = await self.tool.execute(files=['src/'], performance_mode='parallel')
            
            assert result.success is True
            mock_parallel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_documentation_integration(self):
        """Test that documentation is properly integrated when found"""
        # Mock finding documentation
        with patch.object(self.tool, '_find_documentation', return_value=['README.md', 'docs/guide.md']):
            result = await self.tool.execute(files=['src/'])
            
            assert 'analyze_docs' in result.engines_used
            assert 'documentation' in result.routing_decision.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_execution(self):
        """Test error handling during execution"""
        # Make one engine fail
        self.mock_engines['analyze_code'].side_effect = Exception("Analysis failed")
        
        result = await self.tool.execute(files=['src/test.py'])
        
        # Should still succeed with other engines
        assert result.success is True
        # Should have error information in metadata
        assert 'errors' in result.metadata or 'Error' in result.result


class TestUnderstandToolHelperMethods:
    """Test UnderstandTool helper methods"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_engines = {
            'analyze_code': AsyncMock(return_value="Mock analysis")
        }
        self.tool = UnderstandTool(self.mock_engines)
    
    def test_find_documentation_in_file_list(self):
        """Test finding documentation files in provided file list"""
        files = ['src/main.py', 'README.md', 'docs/api.md', 'test.py']
        docs = self.tool._find_documentation(files)
        
        assert 'README.md' in docs
        assert 'docs/api.md' in docs
        assert 'src/main.py' not in docs
    
    def test_find_documentation_empty_list(self):
        """Test finding documentation with empty file list"""
        docs = self.tool._find_documentation([])
        assert docs == []
    
    def test_find_documentation_no_docs(self):
        """Test finding documentation when none present"""
        files = ['src/main.py', 'src/utils.py', 'test.py']
        docs = self.tool._find_documentation(files)
        assert docs == []
    
    def test_question_influences_routing(self):
        """Test that different questions influence routing differently"""
        # Architecture question
        arch_strategy = self.tool.get_routing_strategy(
            files=['src/'], 
            question="What is the system architecture?"
        )
        
        # Implementation question
        impl_strategy = self.tool.get_routing_strategy(
            files=['src/'], 
            question="How is authentication implemented?"
        )
        
        # Both should include basic engines, but may have different priorities
        assert 'analyze_code' in arch_strategy['engines']
        assert 'analyze_code' in impl_strategy['engines']
        assert 'search_code' in impl_strategy['engines']
    
    def test_synthesis_with_multiple_results(self):
        """Test synthesis of multiple engine results"""
        engine_results = {
            'analyze_code': "System has MVC architecture with clear separation",
            'search_code': "Found authentication patterns in auth.py",
            'analyze_docs': "Documentation describes REST API design"
        }
        
        # Test the synthesis logic (this tests the private method if accessible)
        # Or test it through the public execute method
        synthesis = self.tool._synthesize_understanding_results(
            engine_results, 
            question="How does the system work?"
        )
        
        assert len(synthesis) > 0
        assert isinstance(synthesis, str)


class TestUnderstandToolConfiguration:
    """Test UnderstandTool configuration and setup"""
    
    def test_understand_tool_initialization(self):
        """Test proper initialization of UnderstandTool"""
        engines = {'analyze_code': Mock()}
        tool = UnderstandTool(engines)
        
        assert tool.tool_name == 'understand'
        assert tool.engines == engines
        assert hasattr(tool, 'context_reader')
        assert hasattr(tool, 'cpu_throttler')
    
    def test_available_engines_detection(self):
        """Test detection of available engines"""
        engines = {
            'analyze_code': Mock(),
            'search_code': Mock(),
            'map_dependencies': Mock()
        }
        tool = UnderstandTool(engines)
        
        available = tool.get_available_engines()
        assert 'analyze_code' in available
        assert 'search_code' in available
        assert 'map_dependencies' in available
        assert 'nonexistent_engine' not in available
    
    def test_engine_selection_priorities(self):
        """Test that engine selection follows correct priorities"""
        # Test with all engines available
        full_engines = {
            'analyze_code': Mock(),
            'search_code': Mock(),
            'analyze_docs': Mock(),
            'map_dependencies': Mock()
        }
        tool = UnderstandTool(full_engines)
        
        strategy = tool.get_routing_strategy(files=['src/'])
        
        # analyze_code should always be first priority for understanding
        assert strategy['engines'][0] == 'analyze_code'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])