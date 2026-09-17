# Fix indentation issues in iron_gate.py
with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix _llm_check_names tuple indentation
for i, line in enumerate(lines):
    if "_llm_check_names = (" in line and i > 420:
        # Fix the opening line - should be 8 spaces
        if line.strip() == "_llm_check_names = (":
            lines[i] = "        _llm_check_names = (\n"
        break

# Fix the tuple elements - they should be 12 spaces (8 for method + 4 for continuation)
for i, line in enumerate(lines):
    if "_check_llm_data_verification" in line and line.startswith("            "):
        lines[i] = line.replace("            ", "            ")  # already 12 spaces
    elif "_check_human_impossible_dimension" in line and line.startswith("            "):
        lines[lines.index(line)] = '            "_check_human_impossible_dimension",\n'

with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed")
