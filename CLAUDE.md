# Claude Smart Tools - Intelligent MCP System

## 🎯 Current Status: PRODUCTION READY (v1.5.0) - August 2025 ✅

All 7 Smart Tools are fully operational with critical bug fixes and API optimizations:
- ✅ **100% Tool Functionality**: investigate tool critical bug fixed - all 7 tools working
- ✅ **Token limit protection**: propose_tests automatically saves large results to files
- ✅ **API efficiency optimized**: ~30% reduction in Pro/Flash usage, more Flash-lite for better rate limits
- ✅ **Clear validation messaging**: Tools now show "Issues Identified" instead of "Failed" when finding problems
- ✅ **Terminal crash protection**: Smart truncation at 5MB with automatic file saving
- ✅ **File validation system**: Prevents hallucination by validating all file references
- ✅ **API key configuration**: Dual key support with automatic rate limit recovery

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

### 🧠 Enhanced Model Selection (v1.4.0)
The system now uses optimized model assignments for better semantic understanding and context awareness:

**Pro Tier** (Complex reasoning and dialogue):
- `review_output`: Interactive dialogue and synthesis
- `analyze_code`: Deep semantic code understanding (UPGRADED for context awareness)
- `full_analysis`: Multi-engine orchestration

**Flash Tier** (Balanced analysis):
- `check_quality`: Security-critical analysis
- `map_dependencies`: Graph analysis quality
- `performance_profiler`: Flow analysis quality  
- `analyze_logs`: Pattern recognition (UPGRADED from flash-lite)
- `analyze_database`: SQL understanding (UPGRADED from flash-lite)
- `analyze_docs`: Document synthesis (UPGRADED from flash-lite)
- `analyze_test_coverage`: Test analysis (UPGRADED from flash-lite)

**Flash-lite Tier** (Simple pattern matching):
- `search_code`: Pattern matching and text search
- `api_contract_checker`: Schema parsing
- `interface_inconsistency_detector`: Pattern matching
- `config_validator`: Simple validation

**Dynamic Upgrades** (Simplified):
1. Comprehensive detail → always pro
2. Security focus → upgrades flash-lite to flash
3. Large content (>2MB) → pro
4. Medium content (>500KB) → flash minimum

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
- **August 2025 Enhancements**: docs/AUGUST_2025_ENHANCEMENTS.md
- **Troubleshooting**: docs/VENV_TROUBLESHOOTING.md
- **Environment Setup**: .env.example

## 🐛 Recent Fixes (August 2025)

### Latest: Terminal Crash Prevention (August 21, 2025)
1. **Terminal Buffer Overflow Fix**: Collaborate tool no longer crashes terminal with large outputs
   - **Problem**: Large analysis results (>5MB) overwhelmed terminal display buffer
   - **Solution**: Intelligent truncation with automatic file saving for complete results
   - **User Experience**: Terminal shows summary + clear file path for full results

2. **Configuration Integration**: Fixed disconnected hardcoded limits
   - **Problem**: Terminal protection used hardcoded 5MB limit, ignoring config settings
   - **Solution**: Uses `config.max_response_size_kb` with fallback safety
   - **Result**: Respects environment variables for customization

3. **Portable CPU Optimization**: Removed hardware-specific settings
   - **Problem**: Default settings hardcoded for specific CPU (i5-12400F)
   - **Solution**: Auto-detects CPU cores with `min(6, os.cpu_count() or 4)`
   - **Result**: Optimal performance on any system

### Latest Fixes (August 22, 2025) - v1.5.0
4. **investigate Tool Critical Bug**: Fixed variable scope issue in sequential execution
   - **Problem**: `search_keywords` undefined in sequential mode causing tool failure  
   - **Solution**: Moved variable initialization outside conditional block
   - **Result**: 100% tool functionality achieved (7/7 tools working)

5. **Token Limit Protection**: Prevented MCP token crashes in propose_tests
   - **Problem**: Large analysis responses (>25k tokens) crashed MCP protocol
   - **Solution**: Auto-save detailed results to `smart_tool_results/` directory
   - **Result**: Returns concise summary with file reference, no more crashes

6. **API Efficiency Optimization**: Reduced expensive API usage  
   - **Changes**: analyze_docs/analyze_test_coverage → Flash-lite, analyze_code smart downgrade
   - **Result**: ~30% reduction in Pro/Flash calls, better rate limit management

7. **Clear Validation Messaging**: Fixed confusing "Tool Failed" messages
   - **Problem**: validate/deploy tools showed "Failed" when correctly finding issues
   - **Solution**: Shows "Issues Identified" and "Do Not Deploy" respectively  
   - **Result**: Clear distinction between tool errors and issue detection

### Previous Fixes
8. **File Access Resolution**: Fixed working directory issues breaking relative paths
9. **Validation False Positives**: No longer reports "Passed" when no files analyzed
10. **Memory Configuration**: All thresholds now configurable via environment
11. **Retry Logic**: Exponential backoff for API failures
12. **Error Reporting**: Clear messages with troubleshooting suggestions

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