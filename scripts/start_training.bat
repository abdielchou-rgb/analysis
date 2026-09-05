@echo off
echo Starting SFT training...
echo Log: D:\Claude\projects\2hao-analyst\benchmark\sft_training\train.log
D:\Claude\pro-stack\.venv\Scripts\python.exe D:\Claude\projects\2hao-analyst\scripts\sft_train_cpu.py > D:\Claude\projects\2hao-analyst\benchmark\sft_training\train.log 2>&1
echo Training completed. Check log for details.
