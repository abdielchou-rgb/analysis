import re

line = r'capacity_units = float(data.get("capacity_units", 50000) or 50000)'
pattern = r"\.get\([^,]+,\s*\d+"
m = re.search(pattern, line)
print("match:", m)
if m:
    print("groups:", m.groups())

# Test with the actual line from workbench_executor.py
line2 = r'capacity_units = float(data.get("capacity_units", 50000) or 50000),'
m2 = re.search(r"\.get\([^,]+,\s*\d+", line2)
print("match2:", m2)
if m2:
    print("groups2:", m2.groups())
