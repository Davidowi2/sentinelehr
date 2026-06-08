"""Delete lines 2656-2934 (the orphaned duplicate export default function AppV2) from AppV2.jsx."""
path = r'c:\Users\GTHub\OneDrive\Desktop\Tool 22\dashboard\src\AppV2.jsx'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

total = len(lines)
print(f"Total lines before: {total}")

# Line numbers are 1-indexed; delete lines 2656 through 2934 inclusive
# That is index 2655 through 2933 in 0-indexed
del_start = 2655  # 0-indexed, inclusive
del_end   = 2933  # 0-indexed, inclusive

deleted = lines[del_start:del_end+1]
print(f"Deleting {len(deleted)} lines ({del_start+1}-{del_end+1})")
print(f"First deleted line: {deleted[0][:80].strip()}")
print(f"Last  deleted line: {deleted[-1][:80].strip()}")

kept = lines[:del_start] + lines[del_end+1:]
print(f"Total lines after: {len(kept)}")

# Verify the join point looks right
print(f"Line before deletion block: {lines[del_start-1][:80].strip()}")
print(f"Line after  deletion block: {lines[del_end+1][:80].strip()}")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(kept)

print("Done.")
