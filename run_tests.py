#!/usr/bin/env python3
"""
Simple test runner for local development
Just run: python run_tests.py
"""
import subprocess
import sys
import os

def run_tests():
    """Run tests with coverage for local development"""
    
    print("🧪 Running Smart Tools Tests...")
    print("=" * 50)
    
    # Change to project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Run the working tests
        cmd = [
            sys.executable, '-m', 'pytest',
            'tests/test_path_utils.py',
            'tests/unit/test_simple_integration.py',
            '-v',
            '--cov=src/smart_tools',
            '--cov=src/utils', 
            '--cov=src/services',
            '--cov-report=term-missing'
        ]
        
        result = subprocess.run(cmd, capture_output=False)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
            print("\n💡 To run tests manually:")
            print("   python -m pytest tests/test_path_utils.py tests/unit/test_simple_integration.py -v")
            print("\n🔧 To run specific test:")
            print("   python -m pytest tests/test_path_utils.py::TestNormalizePaths::test_normalize_paths_with_none -v")
        else:
            print("\n❌ Some tests failed. Check output above.")
            
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)