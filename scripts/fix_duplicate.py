# Fix the duplicate _check_llm_data_verification line
with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "rb") as f:
    content = f.read()

# Find the duplicate
idx = content.find(b'_check_llm_data_verification",\r\n')
if idx >= 0:
    idx2 = content.find(b"_check_llm_data_verification", idx + 30)
    if idx2 > 0:
        # Remove the duplicate line (from idx2 to next newline)
        end_idx = content.find(b"\n", idx2)
        if end_idx >= 0:
            content = content[:idx2] + content[end_idx + 1 :]
            with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "wb") as f:
                f.write(content)
            print("Removed duplicate line")
        else:
            print("Could not find end of duplicate line")
    else:
        print("Duplicate not found")
