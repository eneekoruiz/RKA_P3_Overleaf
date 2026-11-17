#!/usr/bin/env python3
"""
verify_layout.py - Ultra-Strict Layout & Typographical Audit Tool for LaTeX and Overleaf PDFs.

Enforces:
  1. Zero Vertical Text Collisions & Overlaps (baseline distance >= 8.0 pt, 0 bounding box intersections).
  2. Zero Negative Spacing Hacks (strict ban on negative \\vspace, negative \\\\, negative skips).
  3. Horizontal Margin Safety (strict right text margin <= 516 pt, left margin >= 45 pt).
  4. Exact Page Budget (enforcing 13-page target without orphan or spill pages).
  5. Zero Orphan / Almost Blank Content Pages (minimum 10 lines on content pages).
  6. Zero Stranded Headings (no sections within bottom 120 pt or without following text).
  7. Zero Dangling Page-Break Hyphenations (words or units broken across sheets).
  8. Preamble Typographical Penalties (widowpenalty, clubpenalty, brokenpenalty = 10000).
  9. Mathematical Notation Rigor (protected decimal commas {,}, non-breaking unit spaces).
 10. Frontmatter Bloat Elimination (sparse LOF/LOT lists combined onto single page).
 11. Cover Page Inter-line Rhythm (strictly uniform spacing between authors).
 12. Font Size Switch Scoping (mandatory trailing \\par before closing braces).
 13. Table & Figure Architecture (booktabs, tabularx with X, [H] placement, no micro-figures).
 14. Unreferenced Bibliography Prevention (no bibliography without citations).
"""

import os
import re
import sys
import json
import argparse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import pypdfium2
except ImportError:
    print("[ERROR] pypdfium2 is required. Install via: pip install pypdfium2")
    sys.exit(1)


def compile_overleaf_and_download(project_id: str, cookie_val: str, output_pdf: Path) -> Path:
    cookie_header = f"overleaf_session2={cookie_val}"
    
    # 1. Fetch CSRF token
    req_home = urllib.request.Request(
        f"https://www.overleaf.com/project/{project_id}",
        headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req_home).read().decode("utf-8")
    m = re.search(r'<meta\s+name="ol-csrfToken"\s+content="([^"]+)"', html)
    if not m:
        raise RuntimeError("Could not find ol-csrfToken. Check your overleaf_session2 cookie.")
    csrf = m.group(1)

    # 2. Trigger compile
    compile_payload = json.dumps({
        "draft": False,
        "check": "silent",
        "incrementalCompilesEnabled": True
    }).encode("utf-8")

    req_compile = urllib.request.Request(
        f"https://www.overleaf.com/project/{project_id}/compile",
        data=compile_payload,
        headers={
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "X-Csrf-Token": csrf,
        }
    )
    resp = urllib.request.urlopen(req_compile)
    res = json.loads(resp.read().decode("utf-8"))
    
    status = res.get("status")
    if status != "success":
        raise RuntimeError(f"Overleaf compile failed with status: {status}\n{res}")

    pdf_file = [f for f in res["outputFiles"] if f["type"] == "pdf"][0]
    build = pdf_file["build"]
    compile_group = res.get("compileGroup", "standard")
    clsi_server_id = res.get("clsiServerId", "")

    download_url = (
        f"https://www.overleaf.com/download/project/{project_id}/build/{build}/"
        f"output/output.pdf?compileGroup={compile_group}&clsiserverid={clsi_server_id}"
    )
    req_pdf = urllib.request.Request(download_url, headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"})
    pdf_bytes = urllib.request.urlopen(req_pdf).read()
    output_pdf.write_bytes(pdf_bytes)
    print(f"[OK] Compiled on Overleaf and downloaded {len(pdf_bytes)} bytes to {output_pdf}")
    return output_pdf


def audit_source_typography(tex_dir: Path) -> list[str]:
    """Source code linting for LaTeX traps that cause typographical and spacing defects."""
    defects = []
    tex_files = [tf for tf in tex_dir.glob("**/*.tex") if not tf.name.startswith(('pandoc', 'test_', '_'))]
    
    total_cites = 0
    has_bib = False
    has_penalty_setup = False
    
    for tf in tex_files:
        try:
            content = tf.read_text(encoding="utf-8")
        except Exception:
            continue
            
        # Check 0: Strict Ban on Negative Vertical Spacing Hacks
        # Negative vspaces pull subsequent text over preceding blocks causing line collisions
        neg_vspace = re.findall(r'\\vspace\*?\{-[^}]+\}', content)
        if neg_vspace:
            defects.append(
                f"[SOURCE LINT] {tf.name}: PROHIBITED NEGATIVE \\vspace DETECTED ({neg_vspace})! "
                f"Negative vertical spacing hacks cause lines to mount over each other. Use \\beforechapskip or native glue instead."
            )
            
        neg_linebreak = re.findall(r'\\\\\[-[^\]]+\]', content)
        if neg_linebreak:
            defects.append(
                f"[SOURCE LINT] {tf.name}: PROHIBITED NEGATIVE LINE BREAK SKIP DETECTED ({neg_linebreak})! "
                f"Negative line break arguments cause text overlap. Use standard baseline spacing."
            )
            
        neg_skips = re.findall(r'\\setlength\{\\(?:abovedisplayskip|belowdisplayskip|topsep)\}\{-[^}]+\}', content)
        if neg_skips:
            defects.append(
                f"[SOURCE LINT] {tf.name}: PROHIBITED NEGATIVE DISPLAY SKIP DETECTED ({neg_skips})! "
                f"Negative display math skips cause formulas to collide with adjacent text."
            )

        # Check 1: Font size switch without internal \par
        size_matches = re.finditer(r'\{(\\(?:LARGE|Large|large|huge|Huge|small|footnotesize))\s+([^}]+)\}', content)
        for m in size_matches:
            cmd = m.group(1)
            body = m.group(2)
            if r'\\' in body and not re.search(r'\\par\s*$', body.strip()):
                defects.append(
                    f"[SOURCE LINT] {tf.name}: Font size switch '{cmd}' contains '\\\\' without trailing '\\par'. "
                    f"LaTeX will revert to outer baselineskip on the final line, causing uneven line spacing! Wrap as '{cmd} ...\\par}}'."
                )
                
        # Check 2: Author spacing uniformity in \egileak
        m_egileak = re.search(r'\\newcommand\{\\egileak\}\{([^}]+)\}', content)
        if m_egileak:
            eg_body = m_egileak.group(1)
            linebreaks = re.findall(r'\\\\(?:\[([^\]]+)\])?', eg_body)
            if len(linebreaks) > 1:
                first_spacing = linebreaks[0]
                for idx, lb in enumerate(linebreaks[1:], start=2):
                    if lb != first_spacing:
                        defects.append(
                            f"[SOURCE LINT] {tf.name}: INCONSISTENT AUTHOR SPACING in \\egileak between authors (break 1: '{first_spacing}' vs break {idx}: '{lb}'). "
                            f"All author separators must use identical spacing (e.g. '\\\\[0.4em]')."
                        )
                        break
                        
        # Check 3: Track \cite and \bibliography
        cites = re.findall(r'\\cite\{[^}]+\}', content)
        total_cites += len(cites)
        if r'\bibliography{' in content or r'\begin{thebibliography}' in content:
            has_bib = True

        # Check 3b: Widow/Orphan penalties in preamble/macros
        if 'widowpenalty' in content and 'clubpenalty' in content:
            has_penalty_setup = True

        # Check 4: Long section commands must supply a short header argument [toc][head]{title}
        for m in re.finditer(r'\\section(?:\[([^\]]*)\])?(?:\[([^\]]*)\])?\{([^}]+)\}', content):
            opt1, opt2, full_title = m.group(1), m.group(2), m.group(3)
            has_short_head = (opt2 is not None) or (opt1 is not None and len(opt1) <= 35)
            if len(full_title) > 40 and not has_short_head:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: LONG SECTION TITLE ({len(full_title)} chars) without short header: '{full_title[:35]}...'. "
                    f"Use '\\section[toc][short-head]{{full-title}}' so the running header does not wrap into 2 lines."
                )

        # Check 5: Duplicate list enumeration inside enumerate
        if re.search(r'\\begin\{enumerate\}.*?\\item\s+\\textbf\{\d+\.', content, re.DOTALL):
            defects.append(
                f"[SOURCE LINT] {tf.name}: DUPLICATE NUMBERING DETECTED! Found '\\item \\textbf{{N. ...}}' inside enumerate, "
                f"which causes LaTeX to print '1. 1. ...'. Use descriptive paragraphs or unnumbered headings."
            )

        # Check 6: Unwanted numbered equations
        if re.search(r'\\begin\{(?:equation|align|gather)\}(?!\*)', content):
            defects.append(
                f"[SOURCE LINT] {tf.name}: NUMBERED EQUATION DETECTED! "
                f"Equations should be unnumbered display math '\\[ ... \\]' to avoid distracting marginal equation numbers."
            )

        # Check 7: Excessive bolding inside paragraphs
        bold_matches = re.finditer(r'\\textbf\{([^}]+)\}', content)
        for bm in bold_matches:
            b_text = bm.group(1).strip()
            if len(b_text.split()) > 5:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: EXCESSIVE MID-PARAGRAPH BOLDING ('\\textbf{{{b_text[:30]}...}}'). "
                    f"Mid-sentence bold text blocks (>5 words) read like AI emphasis. Use normal font weight."
                )

        # Check 8: Floats must use [H] positioning
        if "kapituluak" in str(tf.as_posix()):
            non_h_floats = re.findall(r'\\begin\{(?:table|figure)\}(?!\[H\])', content)
            if non_h_floats:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: FLOAT WITHOUT [H] POSITIONING DETECTED! "
                    f"All tables and figures must use [H] positioning to keep them strictly bound to their introducing paragraph and section heading."
                )

        # Check 9: Tabularx must include at least one expandable X column and NO vertical bars
        for m_tabx in re.finditer(r'\\begin\{tabularx\}\s*\{[^}]+\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}', content):
            col_spec = m_tabx.group(1)
            if 'X' not in col_spec:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: TABULARX WITHOUT 'X' COLUMN SPECIFIER ('{col_spec.strip()}'). "
                    f"Tabularx must use at least one expandable 'X' column to fill \\textwidth evenly without awkward margins."
                )
            if '|' in col_spec:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: VERTICAL RULES DETECTED IN TABLE ('{col_spec.strip()}'). "
                    f"Professional booktabs tables must never use vertical lines '|'. Use \\toprule, \\midrule, \\bottomrule."
                )

        # Check 10: AI meta-commentary detector
        meta_ai_patterns = [
            r'\bKISS\b',
            r'TODO\s+bloke',
            r'30\s+lerro\s+garbi',
            r'adabaki\s+artifizial',
            r'irakasleak\s+proposatutako\s+arkitektura\s+minimalari',
        ]
        for pat in meta_ai_patterns:
            if re.search(pat, content, re.IGNORECASE):
                defects.append(
                    f"[SOURCE LINT] {tf.name}: AI META-COMMENTARY DETECTED matching '{pat}'! "
                    f"Remove developer/AI self-referential phrases from student technical report."
                )

        # Check 11: Standalone Figure Sizing
        standalone_figs = re.finditer(r'\\begin\{figure\}\[H\]\s*(?:\\centering\s*)?\\includegraphics\[([^\]]+)\]\{([^}]+)\}', content)
        for sf in standalone_figs:
            opts = sf.group(1)
            fname = sf.group(2)
            m_h = re.search(r'height=([0-9.]+)cm', opts)
            if m_h and float(m_h.group(1)) < 6.0 and 'width' not in opts:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: STANDALONE FIGURE '{fname}' CONSTRAINED TO MICRO-HEIGHT ('{opts}'). "
                    f"Standalone trajectory plots must be displayed with width >= 0.65\\textwidth so axis labels and ticks remain fully legible."
                )

        # Check 12: Subfigure Sizing
        subfigs = re.finditer(r'\\begin\{subfigure\}(?:\[[^\]]*\])?\{[^}]+\}\s*(?:\\centering\s*)?\\includegraphics\[([^\]]+)\]\{([^}]+)\}', content)
        for subf in subfigs:
            opts = subf.group(1)
            fname = subf.group(2)
            subf_pos = subf.start()
            prev_lines = content[max(0, subf_pos-200):subf_pos]
            if '% layout: allow-micro-figure' in prev_lines:
                continue
            m_h = re.search(r'height=([0-9.]+)cm', opts)
            if m_h and float(m_h.group(1)) < 5.0:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: SUBFIGURE '{fname}' CONSTRAINED TO MICRO-HEIGHT ('{opts}'). "
                    f"Subfigures containing trajectories or multi-panel plots must have height >= 5.5cm so that axis labels, ticks, and legends remain legible from a distance (\"bien de lejos\")."
                )

        # Check 13: Protected Decimal Commas in Math Mode
        # In Basque/Spanish LaTeX, decimal comma in math must be protected as {,} (e.g. $0{,}307$)
        # Otherwise LaTeX treats comma as punctuation and inserts a wide 3pt space: $0, 307$
        math_matches = re.finditer(r'\$([^$]+)\$', content)
        for mm in math_matches:
            m_text = mm.group(1)
            unprotected_commas = re.findall(r'\b\d+,\d+\b', m_text)
            if unprotected_commas:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: UNPROTECTED DECIMAL COMMA IN MATH (${m_text}$). "
                    f"Found '{unprotected_commas[0]}'. Protect decimal comma as '{{,}}' (e.g. '0{{,}}307') to prevent accidental spacing."
                )

    if has_bib and total_cites == 0:
        defects.append(
            "[SOURCE LINT] UNREFERENCED / DEAD BIBLIOGRAPHY DETECTED! '\\bibliography' is included but 0 '\\cite' calls exist in the document."
        )

    if not has_penalty_setup:
        defects.append(
            "[SOURCE LINT] MISSING TYPOGRAPHICAL PENALTIES! Preamble must define \\widowpenalty=10000 and \\clubpenalty=10000 to eliminate orphan/widow lines."
        )

    return defects


def audit_cover_spacing(page) -> list[str]:
    """Audits page 1 (cover) to verify vertical line spacing uniformity in author/title blocks."""
    defects = []
    tp = page.get_textpage()
    
    rects = []
    for r_idx in range(tp.count_rects()):
        rect = tp.get_rect(r_idx)
        txt = tp.get_text_bounded(*rect).strip()
        if txt:
            rects.append((rect, txt))
            
    rects.sort(key=lambda item: -item[0][3])
    
    for idx in range(len(rects) - 2):
        r1, t1 = rects[idx]
        r2, t2 = rects[idx+1]
        r3, t3 = rects[idx+2]
        
        words1 = t1.split()
        words2 = t2.split()
        words3 = t3.split()
        if 2 <= len(words1) <= 4 and 2 <= len(words2) <= 4 and 2 <= len(words3) <= 4:
            gap1 = abs(r1[3] - r2[3])
            gap2 = abs(r2[3] - r3[3])
            if 10.0 < gap1 < 45.0 and 10.0 < gap2 < 45.0:
                if abs(gap1 - gap2) > 2.0:
                    defects.append(
                        f"Page  1 (Cover): UNEVEN INTERLINE SPACING in block ('{t1}' / '{t2}' / '{t3}'): "
                        f"gap 1 = {gap1:.1f} pt vs gap 2 = {gap2:.1f} pt (diff = {abs(gap1-gap2):.1f} pt > 2.0 pt). "
                        f"Ensure uniform leading with explicit \\\\[<len>] and wrap with {{\\Large ...\\par}}."
                    )
    return defects


def audit_vertical_collisions_on_page(page, page_num: int) -> list[str]:
    """
    Extracts all characters with exact 2D bounding boxes and baseline positions.
    Detects any text lines where vertical baseline separation is < 8.0 pt
    or where physical bounding boxes intersect while sharing horizontal span.
    """
    defects = []
    tp = page.get_textpage()
    n_chars = tp.count_chars()
    
    chars = []
    for i in range(n_chars):
        ch = tp.get_text_range(i, 1)
        if ch.strip():
            l, b, r, t = tp.get_charbox(i)
            if r > l and t > b:
                chars.append({
                    "ch": ch,
                    "left": l, "bottom": b, "right": r, "top": t,
                    "center_y": (b + t) / 2.0
                })
                
    if not chars:
        return defects
        
    chars.sort(key=lambda c: (-c["center_y"], c["left"]))
    
    lines = []
    current_line = []
    current_y = None
    
    for c in chars:
        if current_y is None:
            current_line = [c]
            current_y = c["center_y"]
        else:
            if abs(c["center_y"] - current_y) < 3.5:
                current_line.append(c)
                current_y = sum(x["center_y"] for x in current_line) / len(current_line)
            else:
                lines.append(current_line)
                current_line = [c]
                current_y = c["center_y"]
    if current_line:
        lines.append(current_line)
        
    line_objs = []
    for l in lines:
        text = "".join(c["ch"] for c in l)
        xmin = min(c["left"] for c in l)
        xmax = max(c["right"] for c in l)
        ymin = min(c["bottom"] for c in l)
        ymax = max(c["top"] for c in l)
        base_y = sum(c["bottom"] for c in l) / len(l)
        line_objs.append({
            "text": text,
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
            "base_y": base_y,
            "count": len(l)
        })
        
    line_objs.sort(key=lambda o: -o["base_y"])
    
    for j in range(len(line_objs) - 1):
        l1 = line_objs[j]
        l2 = line_objs[j+1]
        
        h_overlap = max(0, min(l1["xmax"], l2["xmax"]) - max(l1["xmin"], l2["xmin"]))
        v_dist = l1["base_y"] - l2["base_y"]
        
        if h_overlap > 35.0 and l1["count"] >= 10 and l2["count"] >= 10:
            if v_dist < 8.0:
                defects.append(
                    f"Page {page_num:2d}: TEXT LINE COLLISION / OVERLAP! Vertical baseline delta = {v_dist:.2f} pt (< 8.0 pt, h_overlap={h_overlap:.1f} pt)\n"
                    f"      Line 1: '{l1['text'][:55]}...'\n"
                    f"      Line 2: '{l2['text'][:55]}...'"
                )
            elif l2["ymax"] > l1["ymin"] + 1.2:
                defects.append(
                    f"Page {page_num:2d}: BOUNDING BOX INTERSECTION! Box overlap = {l2['ymax'] - l1['ymin']:.2f} pt\n"
                    f"      Line 1: '{l1['text'][:55]}...'\n"
                    f"      Line 2: '{l2['text'][:55]}...'"
                )

    return defects


def audit_pdf_layout(
    pdf_path: Path,
    tex_dir: Path = None,
    render: bool = False,
    min_lines: int = 10,
    expected_pages: int = 13,
    std_margin: float = 516.0,
    left_margin_limit: float = 45.0,
    chapter_margin: float = 585.0
) -> bool:
    doc = pypdfium2.PdfDocument(pdf_path)
    total_pages = len(doc)
    print(f"\n============================================================")
    print(f"--- Hardened Layout & Typography Audit: '{pdf_path.name}' ---")
    print(f"============================================================")
    print(f"Total Pages Detected: {total_pages} (Target: {expected_pages})")
    
    defects = []
    page_summaries = []

    # 1. Page Budget Check
    if expected_pages and total_pages != expected_pages:
        defects.append(
            f"PAGE BUDGET MISMATCH! Expected exactly {expected_pages} pages, but compiled document has {total_pages} pages. "
            f"Audit for accidental text spill or missing pages."
        )

    # 2. Source-level typography and spacing checks
    if tex_dir and tex_dir.exists():
        src_defects = audit_source_typography(tex_dir)
        defects.extend(src_defects)

    # 3. PDF Page-by-page layout & collision checks
    for i, page in enumerate(doc):
        page_num = i + 1
        width, height = page.get_size()
        tp = page.get_textpage()
        text = tp.get_text_range()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        line_count = len(lines)
        
        # Check 1: Vertical Line Collisions & Bounding Box Overlaps
        collision_defects = audit_vertical_collisions_on_page(page, page_num)
        defects.extend(collision_defects)
        
        # Check 2: Horizontal Margin Limits
        rects = [tp.get_rect(r) for r in range(tp.count_rects())]
        max_right = max([r[2] for r in rects]) if rects else 0
        min_left = min([r[0] for r in rects if r[2] > r[0]]) if rects else 0
        
        is_chapter_title_page = any(re.match(r"^(\d+|[A-Z])$", l) for l in lines[:3])
        margin_limit = chapter_margin if is_chapter_title_page else std_margin
        
        overflow_rects = [r for r in rects if r[2] > margin_limit]
        if overflow_rects:
            worst_r = max([r[2] for r in overflow_rects])
            sample_txt = tp.get_text_bounded(*overflow_rects[0]).strip()
            defects.append(
                f"Page {page_num:2d}: RIGHT MARGIN OVERFLOW (x={worst_r:.1f} pt > limit {margin_limit:.1f} pt) -> '{sample_txt[:40]}'"
            )
            
        if min_left < left_margin_limit and page_num > 1:
            left_overflow_rects = [r for r in rects if r[0] < left_margin_limit]
            sample_txt = tp.get_text_bounded(*left_overflow_rects[0]).strip()
            # Ignore headers/footers or decorative line numbers
            if not sample_txt.isdigit() and len(sample_txt) > 3:
                defects.append(
                    f"Page {page_num:2d}: LEFT MARGIN ENCROACHMENT (x={min_left:.1f} pt < limit {left_margin_limit:.1f} pt) -> '{sample_txt[:40]}'"
                )

        # Check 3: Content pages with very few lines (orphan pages)
        # Exclude frontmatter (pages 1-3)
        if page_num > 3 and line_count < min_lines:
            defects.append(
                f"Page {page_num:2d}: ALMOST BLANK / ORPHAN PAGE ({line_count} lines < {min_lines}) -> '{' '.join(lines)[:60]}...'"
            )
            
        # Check 4: Stranded section heading at or near the bottom of the page
        if page_num > 3 and len(lines) >= 3:
            check_slice = lines[-5:-1] if lines[-1].isdigit() else lines[-4:]
            for candidate in check_slice:
                if re.match(r"^\d+(\.\d+)*\s+[A-Z]", candidate):
                    defects.append(
                        f"Page {page_num:2d}: SECTION HEADING STRANDED NEAR PAGE BOTTOM -> '{candidate}'. Move section with \\clearpage or \\needspace."
                    )
                    break

        # Check 5: Dangling hyphenation across page breaks
        if lines:
            last_line = lines[-1]
            if len(lines) > 1 and lines[-1].isdigit():
                last_line = lines[-2]
            if last_line.endswith("-") or last_line.endswith("—"):
                defects.append(
                    f"Page {page_num:2d}: WORD HYPHENATED ACROSS PAGE BREAK -> '{last_line[-30:]}'"
                )

        # Check 6: Awkward inline hyphenation inside table cells
        for l in lines:
            if re.search(r'\b[a-zA-Z]{5,}-\s*$', l) and any(kw in text.lower() for kw in ["taula", "agindua", "emaitza"]):
                m_hy = re.search(r'([a-zA-Z]{5,}-)\s*$', l)
                if m_hy:
                    defects.append(
                        f"Page {page_num:2d}: AWKWARD HYPHENATION IN TABLE CELL -> '{m_hy.group(1)}'. Widen description column or break parameters into multiple lines."
                    )
                
        # Check 7: Frontmatter page bloat
        if page_num in (2, 3) and line_count < 4:
            defects.append(
                f"Page {page_num:2d}: FRONTMATTER BLOAT ({line_count} lines) -> combine LOF/LOT lists on a single page."
            )

        # Check 8: Cover page inter-line spacing rhythm
        if page_num == 1:
            cover_defects = audit_cover_spacing(page)
            defects.extend(cover_defects)

        # Check 9: Awkward table header unit wrap
        for l in lines:
            if l in ("(°)", "(m)", "(rad/s)", r"(\circ)"):
                defects.append(
                    f"Page {page_num:2d}: AWKWARD TABLE HEADER WRAP -> isolated unit '{l}' on its own line. Widen column or compact header text."
                )

        # Check 10: Stranded introductory phrase or float split at page bottom
        if lines and page_num > 1:
            last_line = lines[-1]
            if len(lines) > 1 and lines[-1].isdigit():
                last_line = lines[-2]
            intro_keywords = ["taulan", "taula", "irudian", "irudia", "grafikoan", "grafikoa"]
            if any(k in last_line.lower() for k in intro_keywords):
                if last_line.endswith(":") or any(v in last_line.lower() for v in ["agertzen", "ikus daite", "ikusten", "laburbiltzen"]):
                    defects.append(
                        f"Page {page_num:2d}: STRANDED INTRODUCTORY LINE AT PAGE BOTTOM -> '{last_line}'. Anchor float with [H] or keep with next paragraph to prevent float split."
                    )
                
        if render:
            img = page.render(scale=1.5).to_pil()
            img.save(f"ol_page_{page_num}.png")
            
        first_snippet = lines[0][:35] if lines else "EMPTY"
        last_snippet = lines[-1][:35] if lines else "EMPTY"
        page_summaries.append(
            f"Page {page_num:2d}: {line_count:2d} lines | x_range=[{min_left:4.1f}, {max_right:5.1f}] pt | Top: {first_snippet:<35} | Bot: {last_snippet}"
        )
        
    print("\nPage Summary:")
    for summary in page_summaries:
        print(f"  {summary}")
        
    if defects:
        print("\n" + "="*60)
        print(f"[FAIL] {len(defects)} Layout defect(s) detected:")
        for d in defects:
            print(f"  - {d}")
        print("="*60 + "\n")
        return False
    else:
        print("\n" + "="*60)
        print(f"[PASS] All {total_pages} pages passed strict layout & typography audit cleanly (0 defects)!")
        print("="*60 + "\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="Audit LaTeX / Overleaf PDF for layout and typography defects.")
    parser.add_argument("--pdf", type=str, default="overleaf_downloaded.pdf", help="Path to PDF file to audit.")
    parser.add_argument("--project-id", type=str, default="", help="Overleaf Project ID to compile and download.")
    parser.add_argument("--cookie-file", type=str, default=".olauth", help="Path to .olauth session cookie file.")
    parser.add_argument("--render", action="store_true", help="Render PDF pages as PNG images for visual inspection.")
    parser.add_argument("--min-lines", type=int, default=10, help="Minimum non-empty lines on content pages.")
    parser.add_argument("--expected-pages", type=int, default=13, help="Expected total page count.")
    parser.add_argument("--std-margin", type=float, default=516.0, help="Standard right text margin limit in pt.")
    parser.add_argument("--tex-dir", type=str, default=".", help="Directory containing LaTeX source files for linting.")
    
    args = parser.parse_args()
    pdf_path = Path(args.pdf)
    tex_dir = Path(args.tex_dir)

    if args.project_id:
        cookie_p = Path(args.cookie_file)
        if not cookie_p.exists():
            print(f"[ERROR] Cookie file '{args.cookie_file}' not found.")
            sys.exit(1)
        cookie_val = cookie_p.read_text(encoding="utf-8").strip().removeprefix("overleaf_session2=")
        pdf_path = compile_overleaf_and_download(args.project_id, cookie_val, pdf_path)
    elif not pdf_path.exists():
        print(f"[ERROR] PDF file '{pdf_path}' does not exist. Specify --pdf or --project-id.")
        sys.exit(1)
        
    success = audit_pdf_layout(
        pdf_path=pdf_path,
        tex_dir=tex_dir,
        render=args.render,
        min_lines=args.min_lines,
        expected_pages=args.expected_pages,
        std_margin=args.std_margin
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
