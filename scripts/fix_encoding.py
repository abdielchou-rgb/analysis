# Fix encoding issues in iron_gate.py
with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix line 399 (0-indexed: 399)
lines[399] = "            # R68 (2026-08-04 全量修复): 覆盖完整性与实体验证 - 解决品牌覆盖代替实体覆盖、\n"

# Fix line 401 (0-indexed: 400)
lines[400] = (
    "            # R68 (2026-08-04 全量修复): 覆盖完整性与实体验证 - 解决品牌覆盖代替实体覆盖、上市公司偏见等系统性问题，数据底座: data/unlisted_players.json + brand_entity_mapping.json\n"
)

with open(r"D:\Claude\projects\2hao-analyst\pipeline\iron_gate.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed encoding issues")
