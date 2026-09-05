@echo off
echo Installing PyTorch with CUDA support...
D:\Claude\pro-stack\.venv\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 --quiet --no-cache-dir
echo Installation complete.
echo Check with: D:\Claude\pro-stack\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
