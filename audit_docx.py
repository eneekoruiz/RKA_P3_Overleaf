import zipfile
import re
from pathlib import Path

docx_file = Path("Praktika_Txostena_RKA_P3.docx")

with zipfile.ZipFile(docx_file) as z:
    xml = z.read("word/document.xml").decode("utf-8")

# 1. Check raw LaTeX commands
latex_commands = [
    r"\beta", r"\qquad", r"\implies", r"\dot", r"\noindent",
    r"\begin", r"\newline", r"\addlinespace", r"\frac", r"\arctan",
    r"\cos", r"\sin", r"\theta", r"\omega", r"\alpha", r"\times"
]
print("--- 1. Raw LaTeX Commands Audit ---")
for cmd in latex_commands:
    count = xml.count(cmd)
    print(f"  {cmd}: {count}")

# 2. Check OMML equations
omml_count = xml.count("<m:oMath>")
print("\n--- 2. OMML Native Word Equations ---")
print(f"  Total native equations (<m:oMath>): {omml_count}")

# 3. Check Tables
tbl_count = xml.count("<w:tbl>")
print("\n--- 3. Tables ---")
print(f"  Total tables: {tbl_count}")

# 4. Check Images
img_count = xml.count("<a:blip")
print("\n--- 4. Embedded Images ---")
print(f"  Total images embedded: {img_count}")

# 5. Check text for broken references ("1 taulan", "1 irudian")
print("\n--- 5. Reference Checks ---")
# Extract plain text runs outside OMML
# Find all text within <w:t>
texts = re.findall(r'<w:t[^>]*>([^<]+)</w:t>', xml)
full_text = " ".join(texts)
for ref_search in ["1 taulan", "1 irudian", "2 taulan", "2 irudian", "3 taulan", "3 irudian", "4 taulan", "4 irudian"]:
    count = full_text.count(ref_search)
    if count > 0:
        print(f"  Found '{ref_search}': {count} times")

for good_ref in ["3.1 taula", "3.2 taula", "3.3 taula", "3.4 taula", "4.1 taula", "3.1 irudia", "3.2 irudia", "3.3 irudia", "3.4 irudia", "3.5 irudia"]:
    count = full_text.count(good_ref)
    print(f"  Found '{good_ref}': {count} times")
