import pypdf

reader = pypdf.PdfReader('overleaf_downloaded.pdf')

for page_idx, page in enumerate(reader.pages):
    lines_by_y = {}
    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            y = round(tm[5], 1)
            lines_by_y.setdefault(y, []).append((tm[4], text))
    
    page.extract_text(visitor_text=visitor)
    
    # Check if multiple full words/phrases are placed at the exact same or nearly identical y coordinate with overlapping x ranges
    sorted_y = sorted(lines_by_y.keys(), reverse=True)
    for i in range(len(sorted_y) - 1):
        y1 = sorted_y[i]
        y2 = sorted_y[i+1]
        diff = y1 - y2
        if 0 < diff < 8.0:
            # Check if this is just subscript or actual overlapping text lines
            txt1 = " ".join([t for x, t in lines_by_y[y1]])
            txt2 = " ".join([t for x, t in lines_by_y[y2]])
            if len(txt1) > 15 and len(txt2) > 15:
                print(f"[OVERLAP COLLISION] Page {page_idx+1}: diff={diff}pt")
                print(f"   Line 1 (y={y1}): {txt1}")
                print(f"   Line 2 (y={y2}): {txt2}")
