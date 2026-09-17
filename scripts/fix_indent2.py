# Fix indentation issues in iron_gate.py
with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the _llm_check_names tuple indentation
content = content.replace(
    '        _llm_check_names = (\r\n            "_check_llm_data_verificat',
    '        _llm_check_names = (\n            "',
)

# Fix the tuple elements
content = content.replace('            "_check_llm_data_verificat', '            "_check_llm_data_verification"')

with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed")
