@echo off
REM Wrapper script to ensure environment variables are set for MCP server

REM Set the API keys directly from system environment
set GOOGLE_API_KEY=%GOOGLE_API_KEY%
set GOOGLE_API_KEY2=%GOOGLE_API_KEY2%

REM Run the Python MCP server with the environment variables
C:\Users\Admin\miniconda3\python.exe C:\Users\Admin\claude-smart-tools\src\smart_mcp_server.py