import pypdf
reader = pypdf.PdfReader('overleaf_downloaded.pdf')
print('=== PAGE 4 ===')
print(reader.pages[3].extract_text()[:400])
print('=== PAGE 5 ===')
print(reader.pages[4].extract_text()[:400])
print('=== PAGE 6 ===')
print(reader.pages[5].extract_text()[:400])
