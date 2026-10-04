@echo off
setlocal
cd /d "%~dp0"

if exist "C:\Users\hakot\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "C:\Users\hakot\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" main.py
) else (
    python main.py
)
