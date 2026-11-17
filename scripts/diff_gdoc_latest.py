import difflib

with open('claude_synced_doc.txt', 'r', encoding='utf-8') as f:
    old = f.readlines()
with open('gdoc_latest.txt', 'r', encoding='utf-8') as f:
    new = f.readlines()

diff = list(difflib.unified_diff(old, new, fromfile='claude_synced_doc.txt', tofile='gdoc_latest.txt', n=1))
print(f'Total diff lines: {len(diff)}')
for line in diff:
    print(line.rstrip())
