with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix line 399 (0-indexed: 399)
lines[399] = '            "_check_llm_data_verification",\n'

# Fix line 431 (0-indexed: 431) - duplicate
lines[431] = '            "_check_llm_data_verification",\n'

with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed")
