@echo off
echo Merging LoRA adapter into base model...
D:\Claude\pro-stack\.venv\Scripts\python.exe D:\Claude\projects\2hao-analyst\scripts\merge_lora.py > D:\Claude\projects\2hao-analyst\benchmark\sft_training\merge.log 2>&1
echo Merge completed. Check merge.log for details.
