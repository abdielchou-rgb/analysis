@echo off
cd /d D:\Claude\projects\2hao-analyst
.venv\Scripts\python.exe scripts\monitor_free_models.py >> output\monitor.log 2>> output\monitor_err.log
