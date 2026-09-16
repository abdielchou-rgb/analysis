import re

line = r'capacity_units = float(data.get("capacity_units", 50000) or 50000),'
pattern = r'\.get\((["\'])([^"\']+)\1\s*,\s*(\d+(?:\.\d+)?)'
m = re.search(pattern, line)
print('match:', m)
if m:
    print('groups:', m.groups())

# Test with various patterns
test_lines = [
    'capacity_units = float(data.get("capacity_units", 50000) or 50000),',
    'unit_price = float(data.get("unit_price", 2000))',
    'variable_cost = data.get("variable_cost", 1400)',
    'fixed_capex = data.get("fixed_capex", 30000000)',
    'revenue = data.get("revenue", 50000000)',
    'price = data.get("price", 0)',
]

for line in test_lines:
    m = re.search(r'\.get\((["\'])([^"\']+)\1\s*,\s*(\d+(?:\.\d+)?)', line)
    if m:
        print(f'MATCH: {m.group(2)} = {m.group(3)}')
    else:
        print(f'NO MATCH: {line[:60]}')