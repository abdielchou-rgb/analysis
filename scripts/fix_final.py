with open(r'D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py', 'rb') as f:
    content = f.read()

idx = content.find(b'_check_llm_data_verification')
if idx >= 0:
    # Find line start
    line_start = content.rfind(b'\n', 0, idx) + 1
    line_end = content.find(b'\n', idx)
    if line_end == -1:
        line_end = len(content)
    
    # Replace with correct indentation (12 spaces)
    fixed_line = b'            "_check_llm_data_verification",\n'
    
    new_content = content[:idx] + b'            "_check_llm_data_verification",\n' + content[content.find(b'\n', idx)+1:]
    
    with open(r'D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py', 'wb') as f:
        f.write(new_content)
    print('Fixed')