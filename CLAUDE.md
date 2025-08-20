# Claude Smart Tools - Intelligent MCP System

## 🎯 Current Status: PRODUCTION READY (v1.2.0)

All 7 Smart Tools are fully operational with API key configuration fixes and dual key support for rate limiting.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API key
export GOOGLE_API_KEY=your_gemini_api_key

# Run tests
python run_tests.py

# Start the MCP server
python src/smart_mcp_server.py
```

## 📋 The 7 Smart Tools

### 1. `understand` - Deep Code Comprehension
```python
understand(files=["src/auth/"], question="How does authentication work?")
```
Routes to: analyze_code + search_code + analyze_docs + map_dependencies

### 2. `investigate` - Problem Solving & Debugging  
```python
investigate(files=["src/api/"], problem="API responses are slow")
```
Routes to: search_code + check_quality + analyze_logs + performance_profiler

### 3. `validate` - Quality & Security Checks
```python
validate(files=["src/"], validation_type="security")
```
Routes to: check_quality + config_validator + interface_inconsistency_detector

### 4. `collaborate` - Code Reviews & Discussion
```python
collaborate(content="implementation", discussion_type="review")
```
Enhanced review_output with executive synthesis

### 5. `full_analysis` - Comprehensive Analysis
```python
full_analysis(files=["src/"], focus="architecture", autonomous=false)
```
Orchestrates multiple smart tools with cross-tool synthesis

### 6. `propose_tests` - Test Coverage & Generation
```python
propose_tests(files=["src/"], test_type="unit", coverage_threshold=0.8)
```
Routes to: analyze_code + analyze_test_coverage + search_code

### 7. `deploy` - Pre-deployment Validation
```python
deploy(files=["config/", "src/"], deployment_stage="production")
```
Routes to: config_validator + api_contract_checker + check_quality

## 🏗️ Architecture

```
Smart Tools Layer (7 tools)
    ↓
Routing & Coordination Layer  
    ↓
Engine Layer (14 Gemini engines)
    ↓
Executive Synthesis (Gemini 2.5 Flash-Lite)
```

### Key Features
- **Intent-based routing**: Choose tools by purpose, not technical names
- **Multi-engine coordination**: Automatic orchestration of multiple engines
- **Executive synthesis**: Transforms technical analysis into actionable insights
- **Performance optimized**: 75-85% faster with parallel execution
- **Memory safeguards**: Adaptive parallelism prevents crashes
- **File caching**: Reduces redundant I/O operations
- **Error handling**: Comprehensive error categorization and retry logic

## ⚙️ Configuration

Key environment variables (see `.env.example` for full list):
```bash
GOOGLE_API_KEY=your_primary_api_key
GOOGLE_API_KEY2=your_secondary_api_key  # Optional: For rate limit recovery
ENGINE_MAX_RETRIES=3
INVESTIGATE_MEMORY_FALLBACK_THRESHOLD=85
ENABLE_FILE_CACHE=true
```

### 🔑 API Key Configuration
The system supports dual API key configuration for optimal rate limit handling:
- **Single Key**: Basic functionality with rate limiting
- **Dual Keys**: Automatic failover and 2x API capacity

**Claude Desktop Configuration** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "claude-smart-tools": {
      "command": "path/to/venv/python.exe",
      "args": ["path/to/smart_mcp_venv.py"],
      "env": {
        "GOOGLE_API_KEY": "your_primary_key",
        "GOOGLE_API_KEY2": "your_secondary_key"
      }
    }
  }
}
```

## 📊 Project Status

### ✅ Completed
- All 7 Smart Tools operational
- Executive synthesis for actionable insights
- Parallel execution with memory safeguards
- Comprehensive error handling
- Path normalization (WindowsPath bug fixed)
- File access issues resolved
- **API Key Configuration Fix**: Dual key support with automatic failover
- **Rate Limit Recovery**: 2x API capacity with smart key switching
- Environment variable validation and diagnostics
- Test coverage: 33 core tests + 44 new tests
- Environment documentation complete

### 📈 Metrics
- **Performance**: 1-4 minutes for full analysis (was 13+ minutes)
- **Test Coverage**: 89% on critical utilities
- **Stability**: Zero crashes with CPU throttling
- **Accuracy**: No false positives in validation

## 🔒 Security

- All API keys use environment variables
- File validation and safety checks
- No hardcoded secrets
- Path validation for all file operations
- Comprehensive error handling prevents information leakage

## 📚 Documentation

- **User Guide**: See README.md
- **API Reference**: docs/SMART_TOOLS_CHEAT_SHEET.md
- **Architecture**: docs/SMART_TOOLS_ARCHITECTURE.md
- **Troubleshooting**: docs/VENV_TROUBLESHOOTING.md
- **Environment Setup**: .env.example

## 🐛 Recent Fixes (August 2025)

1. **File Access Resolution**: Fixed working directory issues breaking relative paths
2. **Validation False Positives**: No longer reports "Passed" when no files analyzed
3. **Memory Configuration**: All thresholds now configurable via environment
4. **Retry Logic**: Exponential backoff for API failures
5. **Error Reporting**: Clear messages with troubleshooting suggestions

## 🚀 Next Steps

For production deployment:
1. Set up environment variables from `.env.example`
2. Run test suite: `python run_tests.py`
3. Configure MCP in Claude Desktop
4. Monitor logs for any issues

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: docs/ directory
- **Tests**: tests/ directory

---

*Built on the proven claude-gemini-mcp foundation with enhanced smart tool routing.*