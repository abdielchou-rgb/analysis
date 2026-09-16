# Fix the _llm_check_names tuple indentation
with open(r'D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the _llm_check_names line
for i, line in enumerate(lines):
    if '_llm_check_names = (' in line and i > 420:
        lines[i] = '        _llm_check_names = (\n'
        break

# Fix the tuple elements
for i, line in enumerate(lines):
    if '_check_llm_data_verification' in line and line.strip().startswith('"'):
        lines[i] = '            "_check_llm_data_verification",\n'
    elif '_check_human_impossible_dimension' in line and '_check_human_impossible_dimension' in line:
        # Find the exact line
        for j, l in enumerate(lines):
            if '_check_human_impossible_dimension' in l and l.strip().startswith('_check_human_impossible_dimension'):
                lines[j] = '            "_check_human_impossible_dimension",\n'
                break

with open(r'D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed')