@echo off
setlocal
if exist "C:\qwen2.5-0.5b-instruct-q4_k_m.gguf" (
    start "" "%~dp0bin\TokenScope.exe" --model "C:\qwen2.5-0.5b-instruct-q4_k_m.gguf"
) else (
    start "" "%~dp0bin\TokenScope.exe"
)
