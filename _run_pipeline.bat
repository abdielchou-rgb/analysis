@echo off
cd /d D:\2hao-analyst
python -u _run_xinlian.py > output\_xinlian_stdout.log 2>&1
echo EXIT CODE: %ERRORLEVEL% >> output\_xinlian_stdout.log
