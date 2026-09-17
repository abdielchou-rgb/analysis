import re

line = r'capacity_units = float(data.get("capacity_units", 50000) or 50000),'

# Fixed pattern with capturing groups for key and value
pattern = r'\.get\((["\'])([^"\']+)\1\s*,\s*(\d+)'

m = re.search(pattern, line)
print("match:", m)
if m:
    print("groups:", m.groups())
    print("key:", m.group(1))
    print("value:", m.group(3))

# Test with the actual line from workbench_executor.py
line2 = r'capacity_units = float(data.get("capacity_units", 50000) or 50000),'
m2 = re.search(r'\.get\((["\'])([^"\']+)\1\s*,\s*(\d+)', line2)
print("match2:", m2)
if m2:
    print("groups2:", m2.groups())
    print("key:", m2.group(2))
    print("value:", m2.group(3))
