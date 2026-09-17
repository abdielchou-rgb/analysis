# Fix line 431 indentation
with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Line 431 (0-indexed: 431) should have exactly 12 spaces before the quote
lines[431] = '            "_check_llm_data_verification",\n'

with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed line 431")
