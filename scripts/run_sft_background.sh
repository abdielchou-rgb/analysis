#!/bin/bash
# SFT Training Background Script
# Usage: script_run(script="./scripts/run_sft_background.sh")

echo "========================================"
echo "2hao-analyst SFT Training"
echo "========================================"
echo "Start time: $(date)"

cd D:/Claude/projects/2hao-analyst

# Activate virtual environment
source D:/Claude/pro-stack/.venv/Scripts/activate

# Check GPU
echo ""
echo "Checking GPU..."
python -c "import torch; print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

# Run training
echo ""
echo "Starting SFT training..."
python scripts/sft_train.py --qlora --epochs 3 --batch_size 4

echo ""
echo "End time: $(date)"
echo "Training complete!"
