import pypdf

reader = pypdf.PdfReader('claude_synced_doc.pdf')
for i, page in enumerate(reader.pages):
    txt = page.extract_text() or ''
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    content_lines = [l for l in lines if not l.startswith('Robotika') and not l.isdigit()]
    start = content_lines[0] if content_lines else 'EMPTY'
    end = content_lines[-1] if len(content_lines) > 1 else ''
    print(f"Page {i+1} ({len(txt)} chars):")
    print(f"   START: {start[:70]}")
    print(f"   END:   {end[:70]}")
