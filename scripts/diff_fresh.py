import difflib

with open('claude_synced_doc.txt', 'r', encoding='utf-8') as f:
    old = f.readlines()
with open('fresh_claude_doc.txt', 'r', encoding='utf-8') as f:
    new = f.readlines()

for line in difflib.unified_diff(old, new, fromfile='old', tofile='new', n=0):
    print(line.strip())
