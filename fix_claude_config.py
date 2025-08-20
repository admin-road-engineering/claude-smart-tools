#!/usr/bin/env python3
"""
Fix the claude-smart-tools configuration in .claude.json
"""
import json
import os
import shutil

# File paths
CLAUDE_CONFIG = r"C:\Users\Admin\.claude.json"
BACKUP_CONFIG = r"C:\Users\Admin\.claude.json.backup"

def fix_config():
    """Fix the claude-smart-tools configuration"""
    
    # Create backup
    shutil.copy2(CLAUDE_CONFIG, BACKUP_CONFIG)
    print(f"Created backup: {BACKUP_CONFIG}")
    
    # Read current config
    with open(CLAUDE_CONFIG, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Find and update claude-smart-tools in mcpServers
    if 'mcpServers' in config:
        if 'claude-smart-tools' in config['mcpServers']:
            print("Found claude-smart-tools configuration, updating...")
            
            # Update configuration
            config['mcpServers']['claude-smart-tools'] = {
                "type": "stdio",
                "command": "C:\\Users\\Admin\\claude-smart-tools\\test-venv\\Scripts\\python.exe",
                "args": [
                    "C:\\Users\\Admin\\claude-smart-tools\\smart_mcp_venv.py"
                ],
                "env": {
                    "GOOGLE_API_KEY": "AIzaSyCr5hlw9b9-SpbVo5i7F_lqV3kRilYfvj8",
                    "GOOGLE_API_KEY2": "AIzaSyD4mKAzVJ7ZSN_5SF8u7tdFmgxesvMk4f4"
                }
            }
            
            print("✅ Updated claude-smart-tools configuration")
        else:
            print("❌ claude-smart-tools not found in mcpServers")
    else:
        print("❌ mcpServers section not found")
    
    # Write updated config
    with open(CLAUDE_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Updated configuration written to {CLAUDE_CONFIG}")
    print("🔄 Please restart Claude Code to apply changes")

if __name__ == "__main__":
    fix_config()