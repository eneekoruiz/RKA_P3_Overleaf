import zipfile
import re
import sys
from pathlib import Path

docx_file = Path("Praktika_Txostena_RKA_P3.docx")

with zipfile.ZipFile(docx_file) as z:
    xml = z.read("word/document.xml").decode("utf-8")

defects = []

# 1. Check raw LaTeX commands
latex_commands = [
    r"\beta", r"\qquad", r"\implies", r"\dot", r"\noindent",
    r"\begin", r"\newline", r"\addlinespace", r"\frac", r"\arctan",
    r"\cos", r"\sin", r"\theta", r"\omega", r"\alpha", r"\times"
]
print("--- 1. Raw LaTeX Commands Audit ---")
for cmd in latex_commands:
    count = xml.count(cmd)
    if count > 0:
        defects.append(f"Raw LaTeX command found: {cmd} ({count} times)")
    print(f"  {cmd}: {count}")

# 2. Check for raw LaTeX table spec remnants like '@ l' or 'arraybackslash'
print("\n--- 2. Raw Table Specs Audit ---")
for spec in ["@ l", "@ >", "arraybackslash", "tabularx"]:
    count = xml.count(spec)
    if count > 0:
        defects.append(f"Raw table spec found: '{spec}' ({count} times)")
    print(f"  '{spec}': {count}")

# 3. Check OMML equations
omml_count = xml.count("<m:oMath>")
print("\n--- 3. OMML Native Word Equations ---")
print(f"  Total native equations (<m:oMath>): {omml_count}")
if omml_count < 100:
    defects.append(f"Too few OMML equations ({omml_count})")

# 4. Check Tables
tbl_count = xml.count("<w:tbl>")
print("\n--- 4. Tables ---")
print(f"  Total tables: {tbl_count}")

# 5. Check Images
img_count = xml.count("<a:blip")
print("\n--- 5. Embedded Images ---")
print(f"  Total images embedded: {img_count}")

# 6. Check text for broken un-prefixed references ("1 taulan" without 3. or 4.)
print("\n--- 6. Reference Checks ---")
texts = re.findall(r'<w:t[^>]*>([^<]+)</w:t>', xml)
full_text = " ".join(texts)

isolated = re.findall(r'(?<![\d\.])([1-9]\s+taulan|[1-9]\s+irudian)', full_text)
if isolated:
    defects.append(f"Unprefixed references found: {isolated}")
print(f"  Unprefixed references: {len(isolated)}")

for good_ref in ["3.1 taula", "3.2 taula", "3.3 taula", "3.4 taula", "4.1 taula", "3.1 irudia", "3.2 irudia", "3.3 irudia", "3.4 irudia", "3.5 irudia"]:
    count = full_text.count(good_ref)
    print(f"  Found '{good_ref}': {count} times")

print("\n" + "=" * 50)
if defects:
    print(f"[FAIL] {len(defects)} defect(s) detected in DOCX:")
    for d in defects:
        print(f"  - {d}")
    sys.exit(1)
else:
    print("[PASS] DOCX audit clean! 0 raw LaTeX commands, 0 table specs, all OMML native.")
    sys.exit(0)
