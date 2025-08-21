# ✅ Terminal Crash Fix - Quick Reference

## What Was Fixed (August 21, 2025)
- **Problem**: Collaborate tool crashed terminal with large outputs
- **Solution**: Smart truncation + automatic file saving
- **Result**: Zero crashes, no data loss

## How It Works Now

### Large Outputs (>5MB)
- **Terminal**: Shows first 5MB with truncation warning
- **File**: Complete results saved to `temp_results/collaborate_[timestamp].md`
- **Notification**: Clear file path displayed

### Normal Outputs (<5MB)  
- **Terminal**: Full display as before
- **No Changes**: Works exactly the same

## Settings You Can Customize

```bash
# .env file or environment variables
MAX_RESPONSE_SIZE_KB=5000          # Terminal display limit (default: 5MB)
MEMORY_LIMIT_MB=8000               # Memory limit (default: 8GB)
MAX_CONCURRENT_REVIEWS=6           # Auto-detects CPU cores
```

## For Your System (32GB RAM, i5-12400F)
Current optimal settings are automatically applied:
- ✅ **5MB terminal limit** - Prevents crashes
- ✅ **8GB memory limit** - 25% of your 32GB RAM
- ✅ **6 concurrent reviews** - Half your 12 CPU cores  
- ✅ **85% CPU usage** - High performance threshold

## File Locations
- **Large Results**: `temp_results/collaborate_[timestamp].md`
- **Config**: `gemini-engines/src/config.py`
- **Examples**: `gemini-engines/.env.example`

## If You Need Different Limits

### More Aggressive (High-End System)
```bash
MAX_RESPONSE_SIZE_KB=10000         # 10MB terminal
MEMORY_LIMIT_MB=16000              # 16GB memory
```

### More Conservative (Slower Terminal)
```bash
MAX_RESPONSE_SIZE_KB=2000          # 2MB terminal
MEMORY_LIMIT_MB=4000               # 4GB memory
```

## Status: ✅ FULLY RESOLVED
- Zero crashes in testing
- No functionality lost
- Automatic system optimization
- Production ready