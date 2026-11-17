import pypdf

reader = pypdf.PdfReader('overleaf_downloaded.pdf')

for i, page in enumerate(reader.pages):
    items = []
    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            # tm[4] is x, tm[5] is y
            items.append((tm[5], tm[4], font_size, text.strip()))
    
    page.extract_text(visitor_text=visitor)
    
    # Sort items by y descending (top to bottom), then x ascending
    items.sort(key=lambda it: (-it[0], it[1]))
    
    # Check vertical distances between lines
    overlaps = []
    for j in range(len(items) - 1):
        y1, x1, fs1, t1 = items[j]
        y2, x2, fs2, t2 = items[j+1]
        dy = abs(y1 - y2)
        # If dy is very small (< 4 pt) and they share similar x or overlap in x
        if 0.1 < dy < 6.0 and fs1 > 5:
            overlaps.append((y1, y2, dy, t1, t2))
            
    if overlaps:
        print(f"Page {i+1} has {len(overlaps)} suspicious vertical overlaps:")
        for y1, y2, dy, t1, t2 in overlaps[:10]:
            print(f"   dy={dy:.2f}pt | '{t1[:30]}' OVERLAPS WITH '{t2[:30]}'")
    else:
        print(f"Page {i+1}: OK (no vertical overlaps detected)")
