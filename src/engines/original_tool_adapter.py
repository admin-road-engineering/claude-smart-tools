"""
Adapter to import and use original tool implementations as engines
"""
import sys
import os
from typing import Dict, Any
try:
    from .engine_wrapper import EngineWrapper
except ImportError:
    # Handle running as standalone script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine_wrapper import EngineWrapper


class OriginalToolAdapter:
    """
    Adapter to import tools from the original claude-gemini-mcp project
    """
    
    @staticmethod
    def get_original_tools_path():
        """Get path to original tools project"""
        # Path to the copied local gemini engines
        import os
        current_file = os.path.abspath(__file__)
        smart_tools_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        return os.path.join(smart_tools_root, "gemini-engines")
    
    @classmethod
    def import_original_implementations(cls):
        """Import original tool implementations"""
        original_path = cls.get_original_tools_path()
        original_cwd = os.getcwd()
        
        try:
            # Save current working directory
            saved_cwd = os.getcwd()
            saved_path = sys.path.copy()
            
            # Set up correct environment for imports
            os.chdir(original_path)
            sys.path.insert(0, original_path)
            
            # Import using exec to ensure proper namespace
            import_code = """
import sys
import os
# Ensure we're in the right directory
os.chdir(r'{}')
sys.path.insert(0, r'{}')

# Now do the imports
from src.services.gemini_tool_implementations import GeminiToolImplementations
from src.clients.gemini_client import GeminiClient  
from src.config import config

# Store in global namespace for retrieval
_tool_impl = GeminiToolImplementations()
_gemini_client = GeminiClient()
_config = config
""".format(original_path, original_path)
            
            # Execute in a namespace
            namespace = {}
            exec(import_code, namespace)
            
            # Retrieve the imported objects
            tool_impl = namespace.get('_tool_impl')
            gemini_client = namespace.get('_gemini_client')
            config = namespace.get('_config')
            
            # Ensure Gemini API is properly configured with environment variables
            import google.generativeai as genai
            api_key = os.environ.get('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                print(f"Configured Gemini API with key from environment: {api_key[:10]}...")
            
            # Restore paths
            os.chdir(saved_cwd)
            sys.path = saved_path
            
            return tool_impl, gemini_client, config
            
        except ImportError as e:
            import traceback
            print(f"Warning: Could not import original tools: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            print("Falling back to mock implementations for development")
            return None, None, None
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
    
    @classmethod
    def create_engine_wrappers(cls) -> Dict[str, EngineWrapper]:
        """Create engine wrappers from original tool implementations"""
        
        # Try direct import approach first
        try:
            original_path = cls.get_original_tools_path()
            saved_cwd = os.getcwd()
            saved_path = sys.path.copy()
            
            # Change to gemini-engines and import
            os.chdir(original_path)
            sys.path.insert(0, original_path)
            
            from src.services.gemini_tool_implementations import GeminiToolImplementations
            from src.clients.gemini_client import GeminiClient
            from src.config import config
            
            tool_impl = GeminiToolImplementations()
            gemini_client = GeminiClient()
            
            # Configure Gemini API
            import google.generativeai as genai
            api_key = os.environ.get('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                print(f"Configured Gemini API with key: {api_key[:10]}...")
            
            # Restore paths
            os.chdir(saved_cwd)
            
        except Exception as e:
            print(f"Direct import failed: {e}")
            # Fall back to the import_original_implementations method
            tool_impl, gemini_client, config = cls.import_original_implementations()
            
            if tool_impl is None:
                # Return mock engines for development
                return cls._create_mock_engines()
        
        # Create real engine wrappers
        engines = {}
        
        # Map of engine names to their methods and configurations
        engine_configs = {
            'analyze_code': {
                'method': tool_impl.analyze_code,
                'description': 'Comprehensive code analysis'
            },
            'search_code': {
                'method': tool_impl.search_code,
                'description': 'Semantic code search'
            },
            'check_quality': {
                'method': tool_impl.check_quality,
                'description': 'Quality analysis'
            },
            'analyze_docs': {
                'method': tool_impl.analyze_docs,
                'description': 'Documentation analysis'
            },
            'analyze_logs': {
                'method': tool_impl.analyze_logs,
                'description': 'Log file analysis'
            },
            'analyze_database': {
                'method': tool_impl.analyze_database,
                'description': 'Database schema analysis'
            },
            'performance_profiler': {
                'method': tool_impl.performance_profiler,
                'description': 'Performance profiling'
            },
            'config_validator': {
                'method': tool_impl.config_validator,
                'description': 'Configuration validation'
            },
            'api_contract_checker': {
                'method': tool_impl.api_contract_checker,
                'description': 'API contract checking'
            },
            'analyze_test_coverage': {
                'method': tool_impl.analyze_test_coverage,
                'description': 'Test coverage analysis'
            },
            'map_dependencies': {
                'method': tool_impl.map_dependencies,
                'description': 'Dependency mapping'
            },
            'interface_inconsistency_detector': {
                'method': tool_impl.interface_inconsistency_detector,
                'description': 'Interface consistency checking'
            },
            'review_output': {
                'method': tool_impl.review_output,
                'description': 'Collaborative review and dialogue'
            },
            'full_analysis': {
                'method': tool_impl.full_analysis,
                'description': 'Comprehensive multi-tool analysis'
            }
        }
        
        # Create wrappers
        for engine_name, config_data in engine_configs.items():
            engines[engine_name] = EngineWrapper(
                engine_name=engine_name,
                original_function=config_data['method'],
                description=config_data['description'],
                gemini_client=gemini_client
            )
        
        return engines
    
    @classmethod
    def _create_mock_engines(cls) -> Dict[str, EngineWrapper]:
        """Create mock engines for development when original tools aren't available"""
        
        async def mock_analyze_code(**kwargs):
            files = kwargs.get('paths', kwargs.get('files', []))
            analysis_type = kwargs.get('analysis_type', 'overview')
            question = kwargs.get('question', '')
            
            return f"""# Mock Code Analysis ({analysis_type})

**Files Analyzed**: {len(files)} files
**Question**: {question or 'General overview'}

## Architecture Overview
This is a mock analysis result. The actual implementation would:
- Analyze code structure and dependencies
- Identify architectural patterns
- Extract key components and relationships
- Provide insights based on the analysis_type: {analysis_type}

## Key Findings
- Mock finding 1: Component structure identified
- Mock finding 2: Dependencies mapped
- Mock finding 3: Architectural patterns detected

*Note: This is a mock result for development. Real implementation would use Gemini AI analysis.*"""
        
        async def mock_search_code(**kwargs):
            query = kwargs.get('query', '')
            paths = kwargs.get('paths', [])
            context_question = kwargs.get('context_question', '')
            
            return f"""# Mock Code Search Results

**Query**: {query}
**Context**: {context_question}
**Paths**: {len(paths)} paths searched

## Search Results
1. **Pattern Found**: Mock match in file1.py
   - Line 42: `{query}` usage example
   - Context: Part of main business logic

2. **Pattern Found**: Mock match in file2.py
   - Line 156: Related `{query}` implementation
   - Context: Helper utility function

## Analysis
The search found {len(query)} character patterns across the codebase. 
Real implementation would provide semantic search with AI understanding.

*Note: This is a mock result for development.*"""
        
        async def mock_analyze_docs(**kwargs):
            sources = kwargs.get('sources', [])
            synthesis_type = kwargs.get('synthesis_type', 'summary')
            
            return f"""# Mock Documentation Analysis

**Sources**: {len(sources)} documents
**Synthesis Type**: {synthesis_type}

## Document Summary
- README.md: Project overview and setup instructions
- API.md: API documentation and usage examples
- ARCHITECTURE.md: System design and component relationships

## Key Insights
- Project provides comprehensive documentation
- Clear setup and usage instructions available
- Architecture well-documented with diagrams

*Note: This is a mock result for development.*"""
        
        # Create mock engines
        mock_functions = {
            'analyze_code': mock_analyze_code,
            'search_code': mock_search_code,
            'analyze_docs': mock_analyze_docs,
        }
        
        engines = {}
        for name, func in mock_functions.items():
            engines[name] = EngineWrapper(
                engine_name=name,
                original_function=func,
                description=f'Mock {name} for development'
            )
        
        return engines